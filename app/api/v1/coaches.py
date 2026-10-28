from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_coach, get_current_user, get_session
from app.models.user import User
from app.repositories.coach_repository import CoachRepository
from app.services.coach_service import CoachService
from app.schemas.coach import TrainingSessionCreate, WorkoutCreate, RosterResponse, AthleteDetailResponse
from app.schemas.workout import WorkoutDetailDataResponse, ExerciseSummary
from pydantic import BaseModel

router = APIRouter(tags=['coach'])

def get_coach_service(session: AsyncSession = Depends(get_session)):
    return CoachService(CoachRepository(session))

@router.get('/coaches/me/athletes', response_model=RosterResponse)
async def roster(user: User = Depends(get_current_coach), service=Depends(get_coach_service)):
    return RosterResponse(data=await service.roster(user.id))

@router.get('/coaches/me/athletes/{athlete_id}', response_model=AthleteDetailResponse)
async def detail(athlete_id: UUID, user: User = Depends(get_current_coach), service=Depends(get_coach_service)):
    return AthleteDetailResponse(data=await service.detail(user.id, athlete_id))

@router.post('/coaches/me/athletes/{athlete_id}/sessions', response_model=WorkoutDetailDataResponse, status_code=201)
async def create_training_session(
    athlete_id: UUID,
    payload: TrainingSessionCreate,
    user: User = Depends(get_current_coach),
    service=Depends(get_coach_service),
):
    return WorkoutDetailDataResponse(
        data=await service.create_session(user.id, athlete_id, payload)
    )

@router.post('/coaches/me/athletes/{athlete_id}/workouts', response_model=WorkoutDetailDataResponse, status_code=201)
async def create_workout(athlete_id: UUID, payload: WorkoutCreate,
                         user: User = Depends(get_current_coach), service=Depends(get_coach_service)):
    return WorkoutDetailDataResponse(data=await service.create(user.id, athlete_id, payload))

class ExerciseLibraryResponse(BaseModel):
    data: list[ExerciseSummary]

@router.get('/exercises', response_model=ExerciseLibraryResponse)
async def exercises(user: User = Depends(get_current_user), service=Depends(get_coach_service)):
    return ExerciseLibraryResponse(data=await service.exercises())
