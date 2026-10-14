from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import PaginationMeta


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


class WorkoutHistoryResponse(BaseModel):
    data: list[WorkoutHistoryItem]
    meta: PaginationMeta
