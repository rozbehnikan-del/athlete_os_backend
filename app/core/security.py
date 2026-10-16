from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from app.api.errors import ApiError
from app.core.config import get_settings

password_hash = PasswordHash.recommended()


class UserRole(StrEnum):
    ATHLETE = "athlete"
    COACH = "coach"
    DOCTOR = "doctor"
    NUTRITIONIST = "nutritionist"
    ADMIN = "admin"


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    return password_hash.verify(plain, hashed)


def create_access_token(user_id: UUID, role: str) -> tuple[str, int]:
    settings = get_settings()
    expires_in = settings.jwt_access_token_expire_minutes * 60
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expires_in


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise ApiError(401, "INVALID_TOKEN", "Invalid or expired token.") from exc

    if payload.get("type") != "access":
        raise ApiError(401, "INVALID_TOKEN", "Invalid or expired token.")
    if not payload.get("sub"):
        raise ApiError(401, "INVALID_TOKEN", "Invalid or expired token.")
    if payload.get("role") not in {role.value for role in UserRole}:
        raise ApiError(401, "INVALID_TOKEN", "Invalid or expired token.")
    return payload
