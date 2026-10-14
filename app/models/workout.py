from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Workout(Base):
    __tablename__ = "workouts"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    athlete_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("athlete_profiles.id"), nullable=False)
    coach_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("coach_profiles.id"), nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    focus: Mapped[str | None] = mapped_column(String, nullable=True)
    scheduled_for: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    coach = relationship("CoachProfile")
    workout_exercises = relationship(
        "WorkoutExercise",
        back_populates="workout",
        order_by="WorkoutExercise.exercise_order",
    )


class WorkoutExercise(Base):
    __tablename__ = "workout_exercises"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    workout_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("workouts.id"), nullable=False)
    exercise_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("exercises.id"), nullable=False)
    exercise_order: Mapped[int] = mapped_column(Integer, nullable=False)
    coaching_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    workout = relationship("Workout", back_populates="workout_exercises")
    exercise = relationship("Exercise")
    workout_sets = relationship(
        "WorkoutSet",
        back_populates="workout_exercise",
        order_by="WorkoutSet.set_number",
    )


class WorkoutSet(Base):
    __tablename__ = "workout_sets"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    workout_exercise_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workout_exercises.id"),
        nullable=False,
    )
    set_number: Mapped[int] = mapped_column(Integer, nullable=False)
    target_reps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_weight: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    weight_unit: Mapped[str | None] = mapped_column(String, nullable=True)

    workout_exercise = relationship("WorkoutExercise", back_populates="workout_sets")
