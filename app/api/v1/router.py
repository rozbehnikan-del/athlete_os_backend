from fastapi import APIRouter

from app.api.v1 import workouts

router = APIRouter(prefix="/v1")
router.include_router(workouts.router)
