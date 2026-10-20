from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.coach_athlete import CoachAthlete
from app.models.user import User, AthleteProfile
from app.models.exercise import Exercise

class CoachRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def athletes(self, coach_id: UUID, athlete_id: UUID | None = None):
        stmt = (select(User, AthleteProfile)
                .join(CoachAthlete, CoachAthlete.athlete_id == User.id)
                .outerjoin(AthleteProfile, AthleteProfile.user_id == User.id)
                .where(CoachAthlete.coach_id == coach_id,
                       CoachAthlete.status == 'active', CoachAthlete.ended_at.is_(None),
                       User.role == 'athlete')
                .order_by(User.full_name, User.id))
        if athlete_id is not None:
            stmt = stmt.where(User.id == athlete_id).with_for_update(of=CoachAthlete)
        return list((await self.session.execute(stmt)).all())

    async def exercises(self):
        return list((await self.session.scalars(
            select(Exercise).where(Exercise.is_active.is_(True)).order_by(Exercise.name, Exercise.id)
        )).all())

    async def exercise_ids(self, ids: set[UUID]):
        return set((await self.session.scalars(
            select(Exercise.id).where(Exercise.id.in_(ids), Exercise.is_active.is_(True))
        )).all())

    async def add_workout(self, workout):
        self.session.add(workout)
        await self.session.flush()
