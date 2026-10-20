from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_athlete, get_session
from app.models.user import User
from app.repositories.workout_repository import WorkoutRepository
from app.schemas.history import WorkoutHistoryResponse
from app.schemas.workout import WorkoutDetailDataResponse
from app.schemas.workout_result import WorkoutResultCreate, WorkoutResultDataResponse
from app.services.workout_service import WorkoutService

router = APIRouter(tags=["training"])


def get_workout_service(session: AsyncSession = Depends(get_session)) -> WorkoutService:
    return WorkoutService(WorkoutRepository(session))


@router.get("/athletes/me/workouts/today", response_model=WorkoutDetailDataResponse)
async def get_today_workout(
    current_athlete: User = Depends(get_current_athlete),
    service: WorkoutService = Depends(get_workout_service),
) -> WorkoutDetailDataResponse:
    return WorkoutDetailDataResponse(data=await service.get_today_workout(current_athlete.id))


@router.get("/workouts/{workout_id}", response_model=WorkoutDetailDataResponse)
async def get_workout(
    workout_id: UUID,
    current_athlete: User = Depends(get_current_athlete),
    service: WorkoutService = Depends(get_workout_service),
) -> WorkoutDetailDataResponse:
    return WorkoutDetailDataResponse(data=await service.get_workout_for_athlete(workout_id, current_athlete.id))


@router.post(
    "/workouts/{workout_id}/results",
    response_model=WorkoutResultDataResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_workout_result(
    workout_id: UUID,
    payload: WorkoutResultCreate,
    current_athlete: User = Depends(get_current_athlete),
    service: WorkoutService = Depends(get_workout_service),
) -> WorkoutResultDataResponse:
    result = await service.submit_result(workout_id, current_athlete.id, payload)
    return WorkoutResultDataResponse(data=result)


@router.get("/athletes/me/workout-history", response_model=WorkoutHistoryResponse)
async def get_workout_history(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_athlete: User = Depends(get_current_athlete),
    service: WorkoutService = Depends(get_workout_service),
) -> WorkoutHistoryResponse:
    return await service.get_history(current_athlete.id, page, per_page)


from app.schemas.progress import ProgressSummaryResponse

@router.get('/athletes/me/progress-summary', response_model=ProgressSummaryResponse)
async def get_progress_summary(
    current_athlete: User = Depends(get_current_athlete),
    service: WorkoutService = Depends(get_workout_service),
) -> ProgressSummaryResponse:
    return ProgressSummaryResponse(data=await service.get_progress_summary(current_athlete.id))
