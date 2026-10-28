from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CoachSummary(BaseModel):
    id: UUID
    name: str | None


class ExerciseSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    name: str


class WorkoutSetResponse(BaseModel):
    id: UUID
    set_number: int
    target_reps: int | None
    target_weight: float | None
    weight_unit: str | None


class WorkoutExerciseResponse(BaseModel):
    prescription_id: UUID
    exercise: ExerciseSummary
    order: int
    coaching_note: str | None
    sets: list[WorkoutSetResponse]


class WodResponse(BaseModel):
    id: UUID
    format: str
    score_type: str
    duration_seconds: int | None
    time_cap_seconds: int | None
    rounds: int | None
    scaling_options: list[str]
    score_config: dict


class TrainingBlockResponse(BaseModel):
    id: UUID
    order: int
    type: str
    title: str
    coach_note: str | None
    prescription: dict
    wod: WodResponse | None


class TrainingSessionResponse(BaseModel):
    id: UUID
    blocks: list[TrainingBlockResponse]


class WorkoutDetailResponse(BaseModel):
    id: UUID
    title: str
    category: str | None
    focus: str | None
    scheduled_for: date
    status: str
    coach: CoachSummary | None
    exercises: list[WorkoutExerciseResponse]
    session: TrainingSessionResponse | None = None


class WorkoutDetailDataResponse(BaseModel):
    data: WorkoutDetailResponse | None
