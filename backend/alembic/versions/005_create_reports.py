"""create reports table - Linus简化版

Revision ID: 005_create_reports
Revises: 004_create_analyses
Create Date: 2025-08-22 22:30:00.000000

原则：数据库存储数据，应用处理逻辑
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "005_create_reports"
down_revision = "004_create_analyses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建reports表 - 简化版本"""

    # 创建reports表
    op.create_table(
        "reports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "analysis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("html_content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # 基本约束
        sa.CheckConstraint(
            "length(html_content) <= 10485760", name="ck_reports_html_size"
        ),
        sa.CheckConstraint(
            "status IN ('active', 'deprecated', 'draft')", name="ck_reports_status"
        ),
    )

    # 核心索引
    op.create_index(
        "ix_reports_analysis_active",
        "reports",
        ["analysis_id"],
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index("ix_reports_created_desc", "reports", [sa.text("created_at DESC")])


def downgrade() -> None:
    """删除reports表"""
    op.drop_index("ix_reports_created_desc", "reports")
    op.drop_index("ix_reports_analysis_active", "reports")
    op.drop_table("reports")
