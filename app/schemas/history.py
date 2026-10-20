from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, computed_field

from app.core.completion_grade import completion_grade
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

    @computed_field
    @property
    def completion_percentage(self) -> float | None:
        return completion_grade(self.completed_sets, self.total_sets)[0]

    @computed_field
    @property
    def completion_grade(self) -> str | None:
        return completion_grade(self.completed_sets, self.total_sets)[1]


class WorkoutHistoryResponse(BaseModel):
    data: list[WorkoutHistoryItem]
    meta: PaginationMeta
