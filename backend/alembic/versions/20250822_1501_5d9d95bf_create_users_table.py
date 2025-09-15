"""创建users表实现多租户基础架构

Revision ID: 5d9d95bf
Revises: 001_init_database
Create Date: 2025-08-22 15:01:32.649336

基于PRD-01要求和Linus设计原则：
- UUID主键，自动生成
- 邮箱唯一性和索引
- 密码哈希存储
- 时间戳字段自动管理
- 软删除支持（is_active）
- 多租户架构基础
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "5d9d95bf"
down_revision = "001_init_database"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建users表"""

    # 创建users表
    op.create_table(
        "users",
        # 主键：UUID类型，自动生成
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            comment="用户唯一标识",
        ),
        # 用户凭证
        sa.Column(
            "email", sa.String(255), unique=True, nullable=False, comment="用户邮箱地址"
        ),
        sa.Column("password_hash", sa.String(255), nullable=False, comment="密码哈希值"),
        # 状态管理
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
            comment="用户是否激活",
        ),
        # 时间戳
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
            onupdate=sa.func.current_timestamp(),
            comment="更新时间",
        ),
        # 表注释
        comment="用户表 - 多租户架构基础",
    )

    # 创建索引

    # 邮箱唯一索引（已通过unique=True创建）

    # 活跃用户索引 - 条件索引，只索引激活用户
    op.create_index(
        "ix_users_active",
        "users",
        ["is_active"],
        postgresql_where=sa.text("is_active = true"),
    )

    # 创建时间索引 - 支持按时间查询
    op.create_index("ix_users_created_at", "users", ["created_at"])


def downgrade() -> None:
    """删除users表"""

    # 删除索引
    op.drop_index("ix_users_created_at", table_name="users")
    op.drop_index("ix_users_active", table_name="users")

    # 删除表
    op.drop_table("users")
