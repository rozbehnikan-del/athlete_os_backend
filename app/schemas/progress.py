from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, computed_field
from app.core.completion_grade import completion_grade

class WorkoutActivity(BaseModel):
    workout_id: UUID
    workout_title: str
    completed_at: datetime
    completed_sets: int
    total_sets: int

class ProgressSummary(BaseModel):
    total_completed_workouts: int
    total_completed_sets: int
    total_prescribed_sets: int
    recent_activity: list[WorkoutActivity]

    @computed_field
    @property
    def completion_percentage(self) -> float | None:
        return completion_grade(self.total_completed_sets, self.total_prescribed_sets)[0]

    @computed_field
    @property
    def completion_grade(self) -> str | None:
        return completion_grade(self.total_completed_sets, self.total_prescribed_sets)[1]

class ProgressSummaryResponse(BaseModel):
    data: ProgressSummary
