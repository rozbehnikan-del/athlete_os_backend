from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db_session
from app.core.security import CurrentAthlete, CurrentUser


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session


async def get_current_user() -> CurrentUser:
    settings = get_settings()
    return CurrentUser(id=settings.demo_athlete_id)


async def get_current_athlete() -> CurrentAthlete:
    settings = get_settings()
    return CurrentAthlete(id=settings.demo_athlete_id)
