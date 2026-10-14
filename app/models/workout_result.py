from datetime import datetime
from decimal import Decimal
from uuid import UUID as PyUUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class WorkoutResult(Base):
    __tablename__ = "workout_results"

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    workout_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workouts.id"), nullable=False)
    athlete_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column("athlete_notes", Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    workout = relationship("Workout")
    set_results = relationship("SetResult", back_populates="workout_result")


class SetResult(Base):
    __tablename__ = "set_results"

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    workout_result_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workout_results.id"),
        nullable=False,
    )
    workout_exercise_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workout_exercises.id"),
        nullable=False,
    )
    workout_set_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workout_sets.id"), nullable=False)
    actual_reps: Mapped[int] = mapped_column(nullable=False)
    actual_weight: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    weight_unit: Mapped[str] = mapped_column(String, nullable=False)
    rpe: Mapped[Decimal | None] = mapped_column(Numeric(3, 1), nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    athlete_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    workout_result = relationship("WorkoutResult", back_populates="set_results")
