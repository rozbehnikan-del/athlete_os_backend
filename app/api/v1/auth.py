from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_user_repository
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import CurrentUserDataResponse, LoginRequest, TokenDataResponse
from app.services.auth_service import AuthService, to_current_user_response

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(repository: UserRepository = Depends(get_user_repository)) -> AuthService:
    return AuthService(repository)


@router.post("/login", response_model=TokenDataResponse)
async def login(payload: LoginRequest, service: AuthService = Depends(get_auth_service)) -> TokenDataResponse:
    token = await service.login(payload.email, payload.password)
    return TokenDataResponse(data=token)


@router.get("/me", response_model=CurrentUserDataResponse)
async def me(current_user: User = Depends(get_current_user)) -> CurrentUserDataResponse:
    return CurrentUserDataResponse(data=to_current_user_response(current_user))
