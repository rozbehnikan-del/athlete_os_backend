from datetime import UTC, date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from app.api.errors import ApiError
from app.models.user import CoachProfile
from app.models.workout import Workout, WorkoutSet
from app.models.workout_result import SetResult, WorkoutResult
from app.repositories.workout_repository import WorkoutRepository
from app.schemas.history import WorkoutHistoryItem, WorkoutHistoryResponse
from app.schemas.workout import (
    CoachSummary,
    ExerciseSummary,
    WorkoutDetailResponse,
    WorkoutExerciseResponse,
    WorkoutSetResponse,
)
from app.schemas.workout_result import WorkoutResultCreate, WorkoutResultResponse


class WorkoutService:
    def __init__(self, repository: WorkoutRepository) -> None:
        self.repository = repository

    async def get_today_workout(self, athlete_id: UUID) -> WorkoutDetailResponse | None:
        workout = await self.repository.get_today_workout(athlete_id, date.today())
        return self._to_workout_detail(workout) if workout else None

    async def get_workout_for_athlete(self, workout_id: UUID, athlete_id: UUID) -> WorkoutDetailResponse:
        workout = await self.repository.get_workout_detail(workout_id)
        if not workout:
            raise ApiError(404, "WORKOUT_NOT_FOUND", "Workout not found.")
        if workout.athlete_id != athlete_id:
            raise ApiError(403, "FORBIDDEN", "You do not have permission to access this workout.")
        return self._to_workout_detail(workout)

    async def submit_result(
        self,
        workout_id: UUID,
        athlete_id: UUID,
        payload: WorkoutResultCreate,
    ) -> WorkoutResultResponse:
        workout = await self.repository.get_workout_detail(workout_id)
        if not workout:
            raise ApiError(404, "WORKOUT_NOT_FOUND", "Workout not found.")
        if workout.athlete_id != athlete_id:
            raise ApiError(403, "FORBIDDEN", "You do not have permission to access this workout.")
        if await self.repository.result_exists(workout_id, athlete_id):
            raise ApiError(409, "WORKOUT_ALREADY_COMPLETED", "Workout has already been completed.")

        resolved_sets: list[WorkoutSet] = []
        seen_set_ids: set[UUID] = set()
        for incoming_set in payload.sets:
            if incoming_set.set_id in seen_set_ids:
                raise ApiError(400, "INVALID_SET", "Each set_id may only be submitted once.")
            seen_set_ids.add(incoming_set.set_id)
            workout_set = await self.repository.get_workout_set(incoming_set.set_id)
            if not workout_set or workout_set.workout_exercise.workout_id != workout_id:
                raise ApiError(400, "INVALID_SET", "Set does not belong to the requested workout.")
            resolved_sets.append(workout_set)

        completed_at = payload.completed_at
        if completed_at.tzinfo is None:
            completed_at = completed_at.replace(tzinfo=UTC)

        result = WorkoutResult(
            id=uuid4(),
            workout_id=workout_id,
            athlete_id=athlete_id,
            completed_at=completed_at,
            notes=payload.notes,
        )
        try:
            async with self.repository.session.begin_nested():
                await self.repository.add_workout_result(result)
                set_results = [
                    SetResult(
                        id=uuid4(),
                        workout_result_id=result.id,
                        workout_exercise_id=workout_set.workout_exercise_id,
                        workout_set_id=incoming_set.set_id,
                        actual_reps=incoming_set.actual_reps,
                        actual_weight=Decimal(str(incoming_set.actual_weight)),
                        weight_unit=incoming_set.weight_unit,
                        rpe=Decimal(str(incoming_set.rpe)) if incoming_set.rpe is not None else None,
                        completed=incoming_set.completed,
                        athlete_notes=incoming_set.notes,
                    )
                    for incoming_set, workout_set in zip(payload.sets, resolved_sets, strict=True)
                ]
                await self.repository.add_set_results(set_results)
            await self.repository.session.commit()
        except IntegrityError as exc:
            await self.repository.session.rollback()
            raise ApiError(409, "WORKOUT_ALREADY_COMPLETED", "Workout has already been completed.") from exc

        return WorkoutResultResponse(id=result.id, workout_id=result.workout_id, completed_at=result.completed_at)

    async def get_history(self, athlete_id: UUID, page: int, per_page: int) -> WorkoutHistoryResponse:
        total = await self.repository.history_total(athlete_id)
        rows = await self.repository.get_history(athlete_id, page, per_page)
        return WorkoutHistoryResponse(
            data=[
                WorkoutHistoryItem(
                    id=row.id,
                    workout_id=row.workout_id,
                    workout_title=row.title,
                    category=row.category,
                    focus=row.focus,
                    completed_at=row.completed_at,
                    completed_sets=row.completed_sets,
                    total_sets=row.total_sets,
                    notes=row.notes,
                )
                for row in rows
            ],
            meta={"page": page, "per_page": per_page, "total": total},
        )

    def _coach_summary(self, coach: CoachProfile | None) -> CoachSummary | None:
        if not coach:
            return None
        return CoachSummary(id=coach.id, name=coach.user.full_name if coach.user else None)

    def _to_workout_detail(self, workout: Workout) -> WorkoutDetailResponse:
        return WorkoutDetailResponse(
            id=workout.id,
            title=workout.title,
            category=workout.category,
            focus=workout.focus,
            scheduled_for=workout.scheduled_for,
            status=workout.status,
            coach=self._coach_summary(workout.coach),
            exercises=[
                WorkoutExerciseResponse(
                    prescription_id=workout_exercise.id,
                    exercise=ExerciseSummary.model_validate(workout_exercise.exercise),
                    order=workout_exercise.exercise_order,
                    coaching_note=workout_exercise.coaching_note,
                    sets=[
                        WorkoutSetResponse(
                            id=workout_set.id,
                            set_number=workout_set.set_number,
                            target_reps=workout_set.target_reps,
                            target_weight=float(workout_set.target_weight)
                            if workout_set.target_weight is not None
                            else None,
                            weight_unit=workout_set.weight_unit,
                        )
                        for workout_set in sorted(workout_exercise.workout_sets, key=lambda item: item.set_number)
                    ],
                )
                for workout_exercise in sorted(
                    workout.workout_exercises,
                    key=lambda item: item.exercise_order,
                )
            ],
        )
