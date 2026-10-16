from uuid import UUID

from pydantic import BaseModel, field_validator


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized or normalized.count("@") != 1:
            raise ValueError("email must contain one @")
        local_part, domain = normalized.split("@", 1)
        if not local_part or not domain or "." not in domain:
            raise ValueError("email must be email-like")
        return normalized


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenDataResponse(BaseModel):
    data: TokenResponse


class CurrentUserResponse(BaseModel):
    id: UUID
    email: str | None
    phone: str | None
    full_name: str
    role: str
    is_active: bool


class CurrentUserDataResponse(BaseModel):
    data: CurrentUserResponse
