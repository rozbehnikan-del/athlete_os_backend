from datetime import UTC
from decimal import Decimal
from math import isfinite
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from app.api.errors import ApiError
from app.core.scheduling import scheduling_date
from app.models.crossfit import WodResult
from app.models.user import User
from app.models.workout import Workout, WorkoutSet
from app.models.workout_result import SetResult, WorkoutResult
from app.repositories.workout_repository import WorkoutRepository
from app.schemas.history import (
    WorkoutHistoryItem,
    WorkoutHistoryResponse,
    WorkoutHistorySet,
)
from app.schemas.progress import ProgressSummary, WorkoutActivity
from app.schemas.workout import (
    CoachSummary,
    ExerciseSummary,
    TrainingBlockResponse,
    TrainingSessionResponse,
    WodResponse,
    WorkoutDetailResponse,
    WorkoutExerciseResponse,
    WorkoutSetResponse,
)
from app.schemas.workout_result import (
    WorkoutResultCreate,
    WorkoutResultResponse,
)


class WorkoutService:
    def __init__(self, repository: WorkoutRepository) -> None:
        self.repository = repository

    async def get_today_workout(
        self,
        athlete_id: UUID,
    ) -> WorkoutDetailResponse | None:
        workout = await self.repository.get_today_workout(
            athlete_id,
            scheduling_date(),
        )

        return (
            self._to_workout_detail(workout)
            if workout
            else None
        )

    async def get_workout_for_athlete(
        self,
        workout_id: UUID,
        athlete_id: UUID,
    ) -> WorkoutDetailResponse:
        workout = await self.repository.get_workout_detail(
            workout_id
        )

        if not workout:
            raise ApiError(
                404,
                "WORKOUT_NOT_FOUND",
                "Workout not found.",
            )

        if workout.athlete_id != athlete_id:
            raise ApiError(
                403,
                "FORBIDDEN",
                (
                    "You do not have permission to access "
                    "this workout."
                ),
            )

        return self._to_workout_detail(workout)

    async def submit_result(
        self,
        workout_id: UUID,
        athlete_id: UUID,
        payload: WorkoutResultCreate,
    ) -> WorkoutResultResponse:
        workout = await self.repository.get_workout_detail(
            workout_id
        )

        if not workout:
            raise ApiError(
                404,
                "WORKOUT_NOT_FOUND",
                "Workout not found.",
            )

        if workout.athlete_id != athlete_id:
            raise ApiError(
                403,
                "FORBIDDEN",
                (
                    "You do not have permission to access "
                    "this workout."
                ),
            )

        if await self.repository.result_exists(
            workout_id,
            athlete_id,
        ):
            raise ApiError(
                409,
                "WORKOUT_ALREADY_COMPLETED",
                "Workout has already been completed.",
            )

        resolved_sets: list[WorkoutSet] = []
        seen_set_ids: set[UUID] = set()

        for incoming_set in payload.sets:
            if incoming_set.set_id in seen_set_ids:
                raise ApiError(
                    400,
                    "INVALID_SET",
                    "Each set_id may only be submitted once.",
                )

            seen_set_ids.add(incoming_set.set_id)

            workout_set = await self.repository.get_workout_set(
                incoming_set.set_id
            )

            if (
                not workout_set
                or workout_set.workout_exercise.workout_id
                != workout_id
            ):
                raise ApiError(
                    400,
                    "INVALID_SET",
                    (
                        "Set does not belong to the "
                        "requested workout."
                    ),
                )

            resolved_sets.append(workout_set)

        resolved_wods = []

        for incoming_wod in payload.wods:
            wod = await self.repository.get_wod(
                incoming_wod.wod_id
            )

            if (
                not wod
                or not wod.block
                or not wod.block.session
                or wod.block.session.workout_id != workout_id
            ):
                raise ApiError(
                    400,
                    "INVALID_WOD",
                    (
                        "WOD does not belong to the "
                        "requested workout."
                    ),
                )

            if incoming_wod.score.type != wod.score_type:
                raise ApiError(
                    400,
                    "INVALID_WOD_SCORE",
                    (
                        "Submitted score type does not match "
                        "the prescribed WOD."
                    ),
                )

            if (
                getattr(wod, "format", None) == "emom"
                and incoming_wod.score.type == "intervals"
            ):
                targets = (getattr(wod, "score_config", None) or {}).get(
                    "minute_targets"
                )
                if targets is not None:
                    values = incoming_wod.score.values
                    if (
                        len(values) != len(targets)
                        or any(
                            not isfinite(value)
                            or value < 0
                            or not value.is_integer()
                            for value in values
                        )
                    ):
                        raise ApiError(
                            400,
                            "INVALID_EMOM_MINUTE_RESULTS",
                            "Provide one nonnegative integer result per EMOM minute.",
                        )

            allowed_scaling = set(
                wod.scaling_options or []
            )

            if (
                allowed_scaling
                and incoming_wod.scaling not in allowed_scaling
            ):
                raise ApiError(
                    400,
                    "INVALID_SCALING",
                    (
                        "Submitted scaling is not allowed "
                        "for this WOD."
                    ),
                )

            resolved_wods.append(wod)

        completed_at = payload.completed_at

        if completed_at.tzinfo is None:
            completed_at = completed_at.replace(
                tzinfo=UTC
            )

        result = WorkoutResult(
            id=uuid4(),
            workout_id=workout_id,
            athlete_id=athlete_id,
            completed_at=completed_at,
            notes=payload.notes,
        )

        try:
            await self.repository.add_workout_result(result)

            set_results = [
                SetResult(
                    id=uuid4(),
                    workout_result_id=result.id,
                    workout_exercise_id=(
                        workout_set.workout_exercise_id
                    ),
                    workout_set_id=incoming_set.set_id,
                    actual_reps=incoming_set.actual_reps,
                    actual_weight=Decimal(
                        str(incoming_set.actual_weight)
                    ),
                    weight_unit=incoming_set.weight_unit,
                    rpe=(
                        Decimal(str(incoming_set.rpe))
                        if incoming_set.rpe is not None
                        else None
                    ),
                    completed=incoming_set.completed,
                    athlete_notes=incoming_set.notes,
                )
                for incoming_set, workout_set in zip(
                    payload.sets,
                    resolved_sets,
                    strict=True,
                )
            ]

            if set_results:
                await self.repository.add_set_results(
                    set_results
                )

            wod_results = [
                WodResult(
                    id=uuid4(),
                    workout_result_id=result.id,
                    wod_id=incoming_wod.wod_id,
                    scaling=incoming_wod.scaling,
                    score=incoming_wod.score_dict(),
                    dnf=incoming_wod.dnf,
                    rpe=(
                        Decimal(str(incoming_wod.rpe))
                        if incoming_wod.rpe is not None
                        else None
                    ),
                    athlete_notes=(
                        incoming_wod.athlete_notes
                    ),
                )
                for incoming_wod in payload.wods
            ]

            if wod_results:
                await self.repository.add_wod_results(
                    wod_results
                )

            await self.repository.mark_workout_completed(
                workout_id
            )

            await self.repository.session.commit()

        except IntegrityError as exc:
            await self.repository.session.rollback()

            raise ApiError(
                409,
                "WORKOUT_ALREADY_COMPLETED",
                "Workout has already been completed.",
            ) from exc

        except Exception:
            await self.repository.session.rollback()
            raise

        return WorkoutResultResponse(
            id=result.id,
            workout_id=result.workout_id,
            status="completed",
            completed_at=result.completed_at,
            completed_sets=sum(
                1
                for item in payload.sets
                if item.completed
            ),
            completed_wods=len(payload.wods),
            notes=result.notes,
        )

    async def get_history(
        self,
        athlete_id: UUID,
        page: int,
        per_page: int,
    ) -> WorkoutHistoryResponse:
        total = await self.repository.history_total(
            athlete_id
        )

        rows = await self.repository.get_history(
            athlete_id,
            page,
            per_page,
        )

        history_set_rows = (
            await self.repository.get_history_sets(
                [row.id for row in rows]
            )
        )

        sets_by_result_id = {
            row.id: []
            for row in rows
        }

        for set_row in history_set_rows:
            sets_by_result_id.setdefault(
                set_row.workout_result_id,
                [],
            ).append(
                WorkoutHistorySet(
                    prescription_id=(
                        set_row.prescription_id
                    ),
                    exercise_id=set_row.exercise_id,
                    set_id=set_row.set_id,
                    set_number=set_row.set_number,
                    actual_reps=set_row.actual_reps,
                    actual_weight=float(
                        set_row.actual_weight
                    ),
                    weight_unit=set_row.weight_unit,
                    rpe=(
                        float(set_row.rpe)
                        if set_row.rpe is not None
                        else None
                    ),
                    completed=set_row.completed,
                    notes=set_row.notes,
                )
            )

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
                    sets=sets_by_result_id.get(
                        row.id,
                        [],
                    ),
                )
                for row in rows
            ],
            meta={
                "page": page,
                "per_page": per_page,
                "total": total,
            },
        )

    def _coach_summary(
        self,
        coach: User | None,
    ) -> CoachSummary | None:
        if not coach:
            return None

        return CoachSummary(
            id=coach.id,
            name=coach.full_name,
        )

    def _to_workout_detail(
        self,
        workout: Workout,
    ) -> WorkoutDetailResponse:
        return WorkoutDetailResponse(
            id=workout.id,
            title=workout.title,
            category=workout.category,
            focus=workout.focus,
            scheduled_for=workout.scheduled_for,
            status=workout.status,
            coach=self._coach_summary(workout.coach),
            session=(
                TrainingSessionResponse(
                    id=workout.training_session.id,
                    blocks=[
                        TrainingBlockResponse(
                            id=block.id,
                            order=block.block_order,
                            type=block.block_type,
                            title=block.title,
                            coach_note=block.coach_note,
                            prescription=(
                                block.prescription or {}
                            ),
                            wod=(
                                WodResponse(
                                    id=block.wod.id,
                                    format=block.wod.format,
                                    score_type=(
                                        block.wod.score_type
                                    ),
                                    duration_seconds=(
                                        block.wod.duration_seconds
                                    ),
                                    time_cap_seconds=(
                                        block.wod.time_cap_seconds
                                    ),
                                    rounds=block.wod.rounds,
                                    scaling_options=list(
                                        block.wod.scaling_options
                                        or []
                                    ),
                                    score_config=(
                                        block.wod.score_config
                                        or {}
                                    ),
                                )
                                if block.wod
                                else None
                            ),
                        )
                        for block in sorted(
                            workout.training_session.blocks,
                            key=lambda item: (
                                item.block_order
                            ),
                        )
                    ],
                )
                if getattr(
                    workout,
                    "training_session",
                    None,
                )
                else None
            ),
            exercises=[
                WorkoutExerciseResponse(
                    prescription_id=(
                        workout_exercise.id
                    ),
                    exercise=(
                        ExerciseSummary.model_validate(
                            workout_exercise.exercise
                        )
                    ),
                    order=(
                        workout_exercise.exercise_order
                    ),
                    coaching_note=(
                        workout_exercise.coaching_note
                    ),
                    sets=[
                        WorkoutSetResponse(
                            id=workout_set.id,
                            set_number=(
                                workout_set.set_number
                            ),
                            target_reps=(
                                workout_set.target_reps
                            ),
                            target_weight=(
                                float(
                                    workout_set.target_weight
                                )
                                if (
                                    workout_set.target_weight
                                    is not None
                                )
                                else None
                            ),
                            weight_unit=(
                                workout_set.weight_unit
                            ),
                        )
                        for workout_set in sorted(
                            workout_exercise.workout_sets,
                            key=lambda item: (
                                item.set_number
                            ),
                        )
                    ],
                )
                for workout_exercise in sorted(
                    workout.workout_exercises,
                    key=lambda item: (
                        item.exercise_order
                    ),
                )
            ],
        )

    async def get_progress_summary(
        self,
        athlete_id: UUID,
    ) -> ProgressSummary:
        workouts, completed, prescribed = (
            await self.repository.progress_totals(
                athlete_id
            )
        )

        recent = await self.repository.get_history(
            athlete_id,
            1,
            10,
        )

        return ProgressSummary(
            total_completed_workouts=workouts,
            total_completed_sets=completed,
            total_prescribed_sets=prescribed,
            recent_activity=[
                WorkoutActivity(
                    workout_id=row.workout_id,
                    workout_title=row.title,
                    completed_at=row.completed_at,
                    completed_sets=row.completed_sets,
                    total_sets=row.total_sets,
                )
                for row in recent
            ],
        )