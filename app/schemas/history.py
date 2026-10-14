from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import PaginationMeta


class WorkoutHistorySet(BaseModel):
    prescription_id: UUID
    exercise_id: UUID
    set_id: UUID
    set_number: int
    actual_reps: int
    actual_weight: float
    weight_unit: str
    rpe: float | None
    completed: bool
    notes: str | None


class WorkoutHistoryItem(BaseModel):
    id: UUID
    workout_id: UUID
    workout_title: str
    category: str | None
    focus: str | None
    completed_at: datetime
    completed_sets: int
    total_sets: int
    notes: str | None
    sets: list[WorkoutHistorySet]


class WorkoutHistoryResponse(BaseModel):
    data: list[WorkoutHistoryItem]
    meta: PaginationMeta
