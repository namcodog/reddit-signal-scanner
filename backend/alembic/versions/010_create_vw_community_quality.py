"""create view vw_community_quality

Revision ID: 010_create_vw_community_quality
Revises: 009_create_feedback_events
Create Date: 2025-09-18
"""

from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "010_create_vw_community_quality"
down_revision = "009_create_feedback_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建占位只读视图，后续由数据管道填充真实来源
    op.execute(
        """
        CREATE OR REPLACE VIEW vw_community_quality AS
        SELECT NULL::text AS community,
               0.0::double precision AS dup_ratio,
               0.0::double precision AS spam_ratio,
               NOW()::timestamptz      AS updated_at
        WHERE FALSE;
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS vw_community_quality")

