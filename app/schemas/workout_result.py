from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class SetResultCreate(BaseModel):
    set_id: UUID
    actual_reps: int = Field(ge=0)
    actual_weight: float = Field(ge=0)
    weight_unit: str
    rpe: float | None = Field(default=None, ge=1, le=10)
    completed: bool
    notes: str | None = None

    @field_validator("weight_unit")
    @classmethod
    def validate_weight_unit(cls, value: str) -> str:
        if value not in {"kg", "lb"}:
            raise ValueError("weight_unit must be kg or lb")
        return value


class WorkoutResultCreate(BaseModel):
    completed_at: datetime
    notes: str | None = None
    sets: list[SetResultCreate] = Field(min_length=1)


class WorkoutResultResponse(BaseModel):
    id: UUID
    workout_id: UUID
    completed_at: datetime


class WorkoutResultDataResponse(BaseModel):
    data: WorkoutResultResponse
