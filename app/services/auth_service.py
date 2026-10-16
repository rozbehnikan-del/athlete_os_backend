from uuid import UUID

from app.api.errors import ApiError
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import CurrentUserResponse, TokenResponse


INVALID_CREDENTIALS_MESSAGE = "Invalid email or password."


class AuthService:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    async def login(self, email: str, password: str) -> TokenResponse:
        user = await self.repository.get_by_email(email.strip().lower())
        if not user or not user.password_hash or not verify_password(password, user.password_hash):
            raise ApiError(401, "INVALID_CREDENTIALS", INVALID_CREDENTIALS_MESSAGE)
        if not user.is_active:
            raise ApiError(403, "USER_INACTIVE", "User is inactive.")

        access_token, expires_in = create_access_token(user.id, user.role)
        return TokenResponse(access_token=access_token, expires_in=expires_in)

    async def get_user_for_token_subject(self, subject: str) -> User:
        try:
            user_id = UUID(subject)
        except ValueError as exc:
            raise ApiError(401, "INVALID_TOKEN", "Invalid or expired token.") from exc

        user = await self.repository.get_by_id(user_id)
        if not user:
            raise ApiError(401, "INVALID_TOKEN", "Invalid or expired token.")
        if not user.is_active:
            raise ApiError(403, "USER_INACTIVE", "User is inactive.")
        return user


def to_current_user_response(user: User) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=user.id,
        email=user.email,
        phone=user.phone,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
    )
