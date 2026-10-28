from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.crossfit import WodResultCreate


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


class WodResultEntryCreate(WodResultCreate):
    wod_id: UUID


class WorkoutResultCreate(BaseModel):
    completed_at: datetime
    notes: str | None = None
    sets: list[SetResultCreate] = Field(default_factory=list, max_length=1000)
    wods: list[WodResultEntryCreate] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def require_result_data(self):
        if not self.sets and not self.wods:
            raise ValueError("At least one set or WOD result is required.")
        wod_ids = [entry.wod_id for entry in self.wods]
        if len(wod_ids) != len(set(wod_ids)):
            raise ValueError("Each wod_id may only be submitted once.")
        return self


class WorkoutResultResponse(BaseModel):
    id: UUID
    workout_id: UUID
    status: str
    completed_at: datetime
    completed_sets: int
    completed_wods: int = 0
    notes: str | None


class WorkoutResultDataResponse(BaseModel):
    data: WorkoutResultResponse
