from collections.abc import AsyncGenerator

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ApiError
from app.core.database import get_db_session
from app.core.security import UserRole, decode_access_token
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService

bearer_scheme = HTTPBearer(auto_error=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session


def get_user_repository(session: AsyncSession = Depends(get_session)) -> UserRepository:
    return UserRepository(session)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    repository: UserRepository = Depends(get_user_repository),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError(401, "NOT_AUTHENTICATED", "Authentication credentials were not provided.")

    payload = decode_access_token(credentials.credentials)
    service = AuthService(repository)
    return await service.get_user_for_token_subject(str(payload["sub"]))


async def get_current_athlete(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ATHLETE:
        raise ApiError(403, "FORBIDDEN", "Athlete role required.")
    return current_user
