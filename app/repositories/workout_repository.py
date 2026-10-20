from datetime import date
from uuid import UUID

from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.user import User
from app.models.workout import Workout, WorkoutExercise, WorkoutSet
from app.models.workout_result import SetResult, WorkoutResult


class WorkoutRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _detail_options(self) -> tuple:
        return (
            joinedload(Workout.coach),
            selectinload(Workout.workout_exercises).joinedload(WorkoutExercise.exercise),
            selectinload(Workout.workout_exercises).selectinload(WorkoutExercise.workout_sets),
        )

    async def get_today_workout(self, athlete_id: UUID, today: date) -> Workout | None:
        stmt = (
            select(Workout)
            .where(
                Workout.athlete_id == athlete_id,
                Workout.scheduled_for == today,
                Workout.status.in_(("planned", "active")),
            )
            .options(*self._detail_options())
            .order_by(Workout.created_at.desc().nullslast(), Workout.id)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_workout_detail(self, workout_id: UUID) -> Workout | None:
        stmt = select(Workout).where(Workout.id == workout_id).options(*self._detail_options())
        return await self.session.scalar(stmt)

    async def get_workout_set(self, set_id: UUID) -> WorkoutSet | None:
        stmt = (
            select(WorkoutSet)
            .where(WorkoutSet.id == set_id)
            .options(joinedload(WorkoutSet.workout_exercise).joinedload(WorkoutExercise.workout))
        )
        return await self.session.scalar(stmt)

    async def result_exists(self, workout_id: UUID, athlete_id: UUID) -> bool:
        stmt = select(WorkoutResult.id).where(
            WorkoutResult.workout_id == workout_id,
            WorkoutResult.athlete_id == athlete_id,
        )
        return await self.session.scalar(stmt) is not None

    async def add_workout_result(self, result: WorkoutResult) -> WorkoutResult:
        self.session.add(result)
        await self.session.flush()
        return result

    async def add_set_results(self, results: list[SetResult]) -> None:
        self.session.add_all(results)
        await self.session.flush()

    async def mark_workout_completed(self, workout_id: UUID) -> None:
        await self.session.execute(
            update(Workout).where(Workout.id == workout_id).values(status="completed")
        )

    async def history_total(self, athlete_id: UUID) -> int:
        stmt = select(func.count()).select_from(WorkoutResult).where(WorkoutResult.athlete_id == athlete_id)
        return int(await self.session.scalar(stmt) or 0)

    async def get_history(self, athlete_id: UUID, page: int, per_page: int) -> list[tuple]:
        completed_sets = func.count(SetResult.id).filter(SetResult.completed.is_(True)).label("completed_sets")
        total_sets = (
            select(func.count(WorkoutSet.id))
            .join(WorkoutExercise, WorkoutExercise.id == WorkoutSet.workout_exercise_id)
            .where(WorkoutExercise.workout_id == Workout.id)
            .correlate(Workout)
            .scalar_subquery()
        )
        stmt: Select = (
            select(
                WorkoutResult.id,
                WorkoutResult.workout_id,
                Workout.title,
                Workout.category,
                Workout.focus,
                WorkoutResult.completed_at,
                completed_sets,
                total_sets.label("total_sets"),
                WorkoutResult.notes,
            )
            .join(Workout, Workout.id == WorkoutResult.workout_id)
            .outerjoin(SetResult, SetResult.workout_result_id == WorkoutResult.id)
            .where(WorkoutResult.athlete_id == athlete_id)
            .group_by(
                WorkoutResult.id,
                WorkoutResult.workout_id,
                Workout.title,
                Workout.category,
                Workout.focus,
                WorkoutResult.completed_at,
                WorkoutResult.notes,
                Workout.id,
            )
            .order_by(WorkoutResult.completed_at.desc(), WorkoutResult.id)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return list((await self.session.execute(stmt)).all())

    async def get_history_sets(self, workout_result_ids: list[UUID]) -> list[tuple]:
        if not workout_result_ids:
            return []
        stmt = (
            select(
                SetResult.workout_result_id,
                SetResult.workout_exercise_id.label("prescription_id"),
                WorkoutExercise.exercise_id,
                SetResult.workout_set_id.label("set_id"),
                WorkoutSet.set_number,
                SetResult.actual_reps,
                SetResult.actual_weight,
                SetResult.weight_unit,
                SetResult.rpe,
                SetResult.completed,
                SetResult.athlete_notes.label("notes"),
                WorkoutExercise.exercise_order,
            )
            .join(WorkoutExercise, WorkoutExercise.id == SetResult.workout_exercise_id)
            .join(WorkoutSet, WorkoutSet.id == SetResult.workout_set_id)
            .where(SetResult.workout_result_id.in_(workout_result_ids))
            .order_by(SetResult.workout_result_id, WorkoutExercise.exercise_order, WorkoutSet.set_number)
        )
        return list((await self.session.execute(stmt)).all())

    async def progress_totals(self, athlete_id: UUID) -> tuple[int, int, int]:
        workouts = select(func.count(WorkoutResult.id)).where(WorkoutResult.athlete_id == athlete_id).scalar_subquery()
        completed = (select(func.count(SetResult.id))
            .join(WorkoutResult, WorkoutResult.id == SetResult.workout_result_id)
            .where(WorkoutResult.athlete_id == athlete_id, SetResult.completed.is_(True)).scalar_subquery())
        prescribed = (select(func.count(WorkoutSet.id))
            .join(WorkoutExercise, WorkoutExercise.id == WorkoutSet.workout_exercise_id)
            .join(WorkoutResult, WorkoutResult.workout_id == WorkoutExercise.workout_id)
            .where(WorkoutResult.athlete_id == athlete_id).scalar_subquery())
        row = (await self.session.execute(select(workouts, completed, prescribed))).one()
        return tuple(int(value) for value in row)
