from datetime import datetime
from decimal import Decimal
from uuid import UUID as PyUUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


BLOCK_TYPES = ("warmup", "strength", "skill", "metcon", "accessory")
WOD_FORMATS = (
    "for_time",
    "amrap",
    "emom",
    "rounds_for_time",
    "chipper",
    "intervals",
    "max_load",
    "max_reps",
    "calories",
    "distance",
    "tabata",
    "custom",
)
SCORE_TYPES = (
    "time",
    "rounds_reps",
    "load",
    "reps",
    "calories",
    "distance",
    "intervals",
    "none",
)
SCALING_LEVELS = ("rx", "scaled", "custom", "none")


class TrainingSession(Base):
    __tablename__ = "training_sessions"

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    workout_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workouts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    workout = relationship("Workout")
    blocks = relationship(
        "TrainingBlock",
        back_populates="session",
        order_by="TrainingBlock.block_order",
        cascade="all, delete-orphan",
    )


class TrainingBlock(Base):
    __tablename__ = "training_blocks"
    __table_args__ = (
        UniqueConstraint(
            "training_session_id",
            "block_order",
            name="uq_training_blocks_session_order",
        ),
        CheckConstraint("block_order >= 1", name="ck_training_blocks_order"),
        CheckConstraint(
            "block_type IN ('warmup','strength','skill','metcon','accessory')",
            name="ck_training_blocks_type",
        ),
    )

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    training_session_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("training_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    block_order: Mapped[int] = mapped_column(Integer, nullable=False)
    block_type: Mapped[str] = mapped_column(String(24), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    coach_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    prescription: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    session = relationship("TrainingSession", back_populates="blocks")
    wod = relationship(
        "Wod",
        back_populates="block",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Wod(Base):
    __tablename__ = "wods"
    __table_args__ = (
        CheckConstraint(
            "format IN ('for_time','amrap','emom','rounds_for_time','chipper','intervals','max_load','max_reps','calories','distance','tabata','custom')",
            name="ck_wods_format",
        ),
        CheckConstraint(
            "score_type IN ('time','rounds_reps','load','reps','calories','distance','intervals','none')",
            name="ck_wods_score_type",
        ),
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds > 0",
            name="ck_wods_duration",
        ),
        CheckConstraint(
            "time_cap_seconds IS NULL OR time_cap_seconds > 0",
            name="ck_wods_time_cap",
        ),
        CheckConstraint("rounds IS NULL OR rounds > 0", name="ck_wods_rounds"),
    )

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    training_block_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("training_blocks.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    format: Mapped[str] = mapped_column(String(32), nullable=False)
    score_type: Mapped[str] = mapped_column(String(32), nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_cap_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rounds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scaling_options: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    score_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    block = relationship("TrainingBlock", back_populates="wod")
    results = relationship("WodResult", back_populates="wod")


class WodResult(Base):
    __tablename__ = "wod_results"
    __table_args__ = (
        UniqueConstraint(
            "workout_result_id",
            "wod_id",
            name="uq_wod_results_workout_result_wod",
        ),
        CheckConstraint(
            "scaling IN ('rx','scaled','custom','none')",
            name="ck_wod_results_scaling",
        ),
        CheckConstraint(
            "rpe IS NULL OR (rpe >= 1 AND rpe <= 10)",
            name="ck_wod_results_rpe",
        ),
    )

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    workout_result_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workout_results.id", ondelete="CASCADE"),
        nullable=False,
    )
    wod_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wods.id", ondelete="RESTRICT"),
        nullable=False,
    )
    scaling: Mapped[str] = mapped_column(String(16), nullable=False)
    score: Mapped[dict] = mapped_column(JSON, nullable=False)
    dnf: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rpe: Mapped[Decimal | None] = mapped_column(Numeric(3, 1), nullable=True)
    athlete_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    workout_result = relationship("WorkoutResult")
    wod = relationship("Wod", back_populates="results")
