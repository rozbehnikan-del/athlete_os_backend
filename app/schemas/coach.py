from datetime import date
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.schemas.workout import WorkoutDetailResponse
from app.schemas.history import WorkoutHistoryItem

class PrescriptionSet(BaseModel):
    model_config = ConfigDict(extra='forbid')
    set_number: int = Field(ge=1, le=2147483647)
    target_reps: int = Field(ge=0, le=2147483647)
    target_weight: float = Field(ge=0, le=999999.99, allow_inf_nan=False)
    weight_unit: Literal['kg', 'lb']

class PrescriptionExercise(BaseModel):
    model_config = ConfigDict(extra='forbid')
    exercise_id: UUID
    order: int = Field(ge=1, le=2147483647)
    coaching_note: str | None = Field(default=None, max_length=4000)
    sets: list[PrescriptionSet] = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def unique_sets(self):
        numbers = [s.set_number for s in self.sets]
        if len(numbers) != len(set(numbers)):
            raise ValueError('Set numbers must be unique within an exercise.')
        return self

class WorkoutCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    focus: str | None = Field(default=None, max_length=200)
    scheduled_for: date
    exercises: list[PrescriptionExercise] = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def unique_order(self):
        orders = [e.order for e in self.exercises]
        if len(orders) != len(set(orders)):
            raise ValueError('Exercise order values must be unique.')
        return self

class AthleteProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    date_of_birth: date | None
    gender: str | None
    height_cm: float | None
    weight_kg: float | None
    experience_level: str | None
    goals: str | None

class CoachAthleteResponse(BaseModel):
    id: UUID
    full_name: str
    email: str | None
    phone: str | None
    is_active: bool
    profile: AthleteProfileResponse | None

class AthleteTraining(BaseModel):
    active_workout: WorkoutDetailResponse | None
    recent_workouts: list[WorkoutHistoryItem]

class CoachAthleteDetail(CoachAthleteResponse):
    training: AthleteTraining

class RosterResponse(BaseModel):
    data: list[CoachAthleteResponse]

class AthleteDetailResponse(BaseModel):
    data: CoachAthleteDetail
