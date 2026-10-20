from fastapi import APIRouter

from app.api.v1 import auth, workouts, coaches

router = APIRouter(prefix="/v1")
router.include_router(auth.router)
router.include_router(workouts.router)

router.include_router(coaches.router)
