from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.workouts import get_workout_service
from app.main import app


ATHLETE_ID = UUID("22222222-2222-4222-8222-222222222222")
OTHER_ATHLETE_ID = UUID("33333333-3333-4333-8333-333333333333")
COACH_ID = UUID("11111111-1111-4111-8111-111111111111")
WORKOUT_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
FOREIGN_WORKOUT_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
UNKNOWN_WORKOUT_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
FOREIGN_SET_ID = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class FakeRepository:
    def __init__(self, fail_set_insert: bool = False) -> None:
        self.session = FakeSession()
        self.fail_set_insert = fail_set_insert
        self.results = []
        self.set_results = []
        self.exercises = [
            self._workout_exercise("Back Squat", "back-squat", 1, 4),
            self._workout_exercise("Bench Press", "bench-press", 2, 3),
            self._workout_exercise("Romanian Deadlift", "romanian-deadlift", 3, 3),
        ]
        self.workout = SimpleNamespace(
            id=WORKOUT_ID,
            athlete_id=ATHLETE_ID,
            coach_id=COACH_ID,
            title="Today's Workout",
            category="Strength",
            focus="Lower Body",
            scheduled_for=date.today(),
            status="active",
            coach=SimpleNamespace(id=COACH_ID, full_name="Demo Coach"),
            workout_exercises=self.exercises,
        )
        self.foreign_workout = SimpleNamespace(**{**self.workout.__dict__, "id": FOREIGN_WORKOUT_ID, "athlete_id": OTHER_ATHLETE_ID})

    def _workout_exercise(self, name: str, slug: str, order: int, set_count: int) -> SimpleNamespace:
        exercise_id = uuid4()
        workout_exercise_id = uuid4()
        return SimpleNamespace(
            id=workout_exercise_id,
            workout_id=WORKOUT_ID,
            exercise=SimpleNamespace(id=exercise_id, slug=slug, name=name),
            exercise_order=order,
            coaching_note=None,
            workout_sets=[
                SimpleNamespace(
                    id=uuid4(),
                    workout_exercise_id=workout_exercise_id,
                    set_number=set_number,
                    target_reps=8,
                    target_weight=80,
                    weight_unit="kg",
                    workout_exercise=None,
                )
                for set_number in range(1, set_count + 1)
            ],
        )

    async def get_today_workout(self, athlete_id, today):
        return self.workout if athlete_id == ATHLETE_ID else None

    async def get_workout_detail(self, workout_id):
        if workout_id == WORKOUT_ID:
            return self.workout
        if workout_id == FOREIGN_WORKOUT_ID:
            return self.foreign_workout
        return None

    async def get_workout_set(self, set_id):
        if set_id == FOREIGN_SET_ID:
            return SimpleNamespace(
                id=FOREIGN_SET_ID,
                workout_exercise_id=uuid4(),
                workout_exercise=SimpleNamespace(workout_id=FOREIGN_WORKOUT_ID),
            )
        for exercise in self.exercises:
            for workout_set in exercise.workout_sets:
                if workout_set.id == set_id:
                    workout_set.workout_exercise = SimpleNamespace(workout_id=WORKOUT_ID)
                    return workout_set
        return None

    async def result_exists(self, workout_id, athlete_id):
        return any(result.workout_id == workout_id and result.athlete_id == athlete_id for result in self.results)

    async def add_workout_result(self, result):
        self.results.append(result)
        return result

    async def add_set_results(self, results):
        if self.fail_set_insert:
            self.results.clear()
            raise RuntimeError("insert failed")
        self.set_results.extend(results)

    async def history_total(self, athlete_id):
        return 1 if self.results else 0

    async def get_history(self, athlete_id, page, per_page):
        if not self.results:
            return []
        result = self.results[0]
        return [
            SimpleNamespace(
                id=result.id,
                workout_id=result.workout_id,
                title="Today's Workout",
                category="Strength",
                focus="Lower Body",
                completed_at=result.completed_at,
                completed_sets=sum(1 for item in self.set_results if item.completed),
                total_sets=10,
                notes=result.notes,
            )
        ]


@pytest.fixture()
def fake_repository():
    return FakeRepository()


@pytest.fixture()
def client(fake_repository):
    from app.services.workout_service import WorkoutService

    app.dependency_overrides[get_workout_service] = lambda: WorkoutService(fake_repository)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def valid_result_payload(fake_repository):
    sets = [
        {
            "set_id": str(workout_set.id),
            "actual_reps": 8,
            "actual_weight": 82.5,
            "weight_unit": "kg",
            "rpe": 8,
            "completed": True,
            "notes": None,
        }
        for exercise in fake_repository.exercises
        for workout_set in exercise.workout_sets
    ]
    return {
        "completed_at": datetime(2026, 10, 13, 12, 45, 30, tzinfo=UTC).isoformat(),
        "notes": "Felt strong today.",
        "sets": sets,
    }
