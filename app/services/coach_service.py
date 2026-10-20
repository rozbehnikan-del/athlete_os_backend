from app.core.scheduling import scheduling_date
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4
from sqlalchemy.exc import IntegrityError
from app.api.errors import ApiError
from app.models.workout import Workout, WorkoutExercise, WorkoutSet
from app.repositories.workout_repository import WorkoutRepository
from app.schemas.coach import CoachAthleteResponse, CoachAthleteDetail, AthleteTraining, AthleteProfileResponse
from app.services.workout_service import WorkoutService

class CoachService:
    def __init__(self, repository, workouts=None):
        self.repository = repository
        self.workouts = workouts or WorkoutRepository(repository.session)

    @staticmethod
    def athlete(row):
        user, profile = row
        return CoachAthleteResponse(
            id=user.id, full_name=user.full_name, email=user.email, phone=user.phone,
            is_active=user.is_active,
            profile=AthleteProfileResponse.model_validate(profile) if profile else None)

    async def exercises(self):
        from app.schemas.workout import ExerciseSummary
        return [ExerciseSummary.model_validate(e) for e in await self.repository.exercises()]

    async def roster(self, coach_id):
        return [self.athlete(row) for row in await self.repository.athletes(coach_id)]

    async def assigned(self, coach_id, athlete_id, *, for_update=False):
        rows = await self.repository.athletes(coach_id, athlete_id, for_update=True) if for_update else await self.repository.athletes(coach_id, athlete_id)
        if not rows:
            raise ApiError(404, 'ATHLETE_NOT_FOUND', 'Assigned athlete not found.')
        return self.athlete(rows[0])

    async def detail(self, coach_id, athlete_id):
        athlete = await self.assigned(coach_id, athlete_id)
        service = WorkoutService(self.workouts)
        active = await service.get_today_workout(athlete_id)
        history = await service.get_history(athlete_id, 1, 5)
        return CoachAthleteDetail(**athlete.model_dump(), training=AthleteTraining(
            active_workout=active, recent_workouts=history.data))

    async def create(self, coach_id, athlete_id, payload):
        try:
            await self.assigned(coach_id, athlete_id, for_update=True)
            ids = {e.exercise_id for e in payload.exercises}
            if await self.repository.exercise_ids(ids) != ids:
                raise ApiError(422, 'INVALID_EXERCISE', 'One or more exercises are unavailable.')
            now = datetime.now(UTC)
            workout = Workout(id=uuid4(), athlete_id=athlete_id, coach_id=coach_id,
                title=payload.title, category=payload.category, focus=payload.focus,
                scheduled_for=payload.scheduled_for,
                status='active' if payload.scheduled_for == scheduling_date() else 'planned',
                created_at=now, updated_at=now)
            workout.workout_exercises = [WorkoutExercise(
                id=uuid4(), exercise_id=e.exercise_id, exercise_order=e.order,
                coaching_note=e.coaching_note, created_at=now,
                workout_sets=[WorkoutSet(id=uuid4(), set_number=s.set_number,
                    target_reps=s.target_reps, target_weight=Decimal(str(s.target_weight)),
                    weight_unit=s.weight_unit, created_at=now) for s in e.sets])
                for e in payload.exercises]
            await self.repository.add_workout(workout)
            # Resolve the response before committing, so serialization failures also roll back.
            detail = await self.workouts.get_workout_detail(workout.id)
            response = WorkoutService(self.workouts)._to_workout_detail(detail)
            await self.repository.session.commit()
            return response
        except IntegrityError as exc:
            await self.repository.session.rollback()
            constraint = getattr(getattr(exc.orig, 'diag', None), 'constraint_name', None)
            if constraint == 'uq_workouts_athlete_scheduled_open':
                raise ApiError(409, 'WORKOUT_SCHEDULE_CONFLICT', 'An active or planned workout already exists for this athlete and date.') from exc
            raise ApiError(409, 'WORKOUT_CONFLICT', 'Workout could not be assigned. Refresh and retry.') from exc
        except Exception:
            await self.repository.session.rollback()
            raise
