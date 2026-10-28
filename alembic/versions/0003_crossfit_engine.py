"""Add additive CrossFit training and scoring domain.

Revision ID: 0003_crossfit_engine
Revises: 0002_training_invariants
Create Date: 2026-10-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_crossfit_engine"
down_revision = "0002_training_invariants"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "training_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workout_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workouts.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_table(
        "training_blocks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "training_session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("training_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("block_order", sa.Integer(), nullable=False),
        sa.Column("block_type", sa.String(length=24), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("coach_note", sa.Text(), nullable=True),
        sa.Column("prescription", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint(
            "training_session_id",
            "block_order",
            name="uq_training_blocks_session_order",
        ),
        sa.CheckConstraint("block_order >= 1", name="ck_training_blocks_order"),
        sa.CheckConstraint(
            "block_type IN ('warmup','strength','skill','metcon','accessory')",
            name="ck_training_blocks_type",
        ),
    )
    op.create_index(
        "idx_training_blocks_session",
        "training_blocks",
        ["training_session_id"],
    )

    op.create_table(
        "wods",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "training_block_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("training_blocks.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("format", sa.String(length=32), nullable=False),
        sa.Column("score_type", sa.String(length=32), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("time_cap_seconds", sa.Integer(), nullable=True),
        sa.Column("rounds", sa.Integer(), nullable=True),
        sa.Column("scaling_options", sa.JSON(), nullable=False),
        sa.Column("score_config", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "format IN ('for_time','amrap','emom','rounds_for_time','chipper','intervals','max_load','max_reps','calories','distance','tabata','custom')",
            name="ck_wods_format",
        ),
        sa.CheckConstraint(
            "score_type IN ('time','rounds_reps','load','reps','calories','distance','intervals','none')",
            name="ck_wods_score_type",
        ),
        sa.CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds > 0",
            name="ck_wods_duration",
        ),
        sa.CheckConstraint(
            "time_cap_seconds IS NULL OR time_cap_seconds > 0",
            name="ck_wods_time_cap",
        ),
        sa.CheckConstraint(
            "rounds IS NULL OR rounds > 0",
            name="ck_wods_rounds",
        ),
    )

    op.create_table(
        "wod_results",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workout_result_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workout_results.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "wod_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("wods.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("scaling", sa.String(length=16), nullable=False),
        sa.Column("score", sa.JSON(), nullable=False),
        sa.Column("dnf", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("rpe", sa.Numeric(3, 1), nullable=True),
        sa.Column("athlete_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint(
            "workout_result_id",
            "wod_id",
            name="uq_wod_results_workout_result_wod",
        ),
        sa.CheckConstraint(
            "scaling IN ('rx','scaled','custom','none')",
            name="ck_wod_results_scaling",
        ),
        sa.CheckConstraint(
            "rpe IS NULL OR (rpe >= 1 AND rpe <= 10)",
            name="ck_wod_results_rpe",
        ),
    )
    op.create_index(
        "idx_wod_results_workout_result",
        "wod_results",
        ["workout_result_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_wod_results_workout_result", table_name="wod_results")
    op.drop_table("wod_results")
    op.drop_table("wods")
    op.drop_index("idx_training_blocks_session", table_name="training_blocks")
    op.drop_table("training_blocks")
    op.drop_table("training_sessions")
