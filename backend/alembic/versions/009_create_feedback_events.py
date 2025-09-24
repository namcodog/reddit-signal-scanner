"""create feedback_events table

Revision ID: 009_create_feedback_events
Revises: 008_add_cleanup_indexes
Create Date: 2025-09-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "009_create_feedback_events"
down_revision = "008_add_cleanup_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ensure pgcrypto for gen_random_uuid
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "feedback_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=True),
        sa.Column("task_id", sa.Text(), nullable=True),
        sa.Column("analysis_id", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("source IN ('user','admin','system')", name="ck_feedback_source"),
        sa.CheckConstraint(
            "event_type IN ('community_decision','analysis_rating','insight_flag','metric')",
            name="ck_feedback_event_type",
        ),
    )

    # helpful indexes
    op.create_index(
        "ix_feedback_events_type_time",
        "feedback_events",
        ["event_type", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_feedback_events_task",
        "feedback_events",
        ["task_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_feedback_events_task", table_name="feedback_events")
    op.drop_index("ix_feedback_events_type_time", table_name="feedback_events")
    op.drop_table("feedback_events")
