"""create tasks table

Revision ID: 003_create_tasks
Revises: 002_create_users
Create Date: 2025-08-22 17:00:00.000000

Reddit Signal Scanner - Tasks表迁移
基于 Linus 设计哲学：数据结构决定代码复杂度
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "003_create_tasks"
down_revision = "002_create_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建tasks表和相关索引、约束"""

    # 确保在正确的模式中
    op.execute("SET search_path TO signal_scanner, public")

    # 创建tasks表
    op.create_table(
        "tasks",
        # 主键：UUID类型，数据库生成
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
            comment="任务唯一标识",
        ),
        # 多租户隔离：外键到users表
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="任务所属用户，实现多租户隔离",
        ),
        # 产品描述：用户输入的分析目标
        sa.Column(
            "product_description",
            sa.Text(),
            nullable=False,
            comment="用户输入的产品描述，10-2000字符",
        ),
        # 任务状态：使用预定义枚举
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="pending",
            comment="任务状态：pending/processing/completed/failed",
        ),
        # 错误信息：失败时记录具体原因
        sa.Column("error_message", sa.Text(), nullable=True, comment="失败时的错误详情"),
        # 审计字段：自动维护
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="任务创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="最后更新时间",
        ),
        sa.Column(
            "completed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment="任务完成时间，只有completed状态时才设置",
        ),
        # 业务约束：产品描述长度限制
        sa.CheckConstraint(
            "char_length(product_description) BETWEEN 10 AND 2000",
            name="ck_tasks_description_length",
        ),
        # 业务约束：错误信息长度限制（防止恶意填充）
        sa.CheckConstraint(
            "error_message IS NULL OR char_length(error_message) <= 1000",
            name="ck_tasks_error_length",
        ),
        # 业务约束：完成时间必须晚于创建时间
        sa.CheckConstraint(
            "completed_at IS NULL OR completed_at >= created_at",
            name="ck_tasks_completed_after_created",
        ),
        # 业务约束：完成状态的一致性
        sa.CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL) OR "
            "(status != 'completed' AND completed_at IS NULL)",
            name="ck_tasks_completion_consistency",
        ),
        comment="用户分析任务表 - 支持完整生命周期管理和多租户数据隔离",
    )

    # 创建索引（基于实际查询模式设计）

    # 最重要：多租户查询优化
    op.create_index("ix_tasks_user_status", "tasks", ["user_id", "status"])

    # 历史查询：按用户和创建时间排序
    op.create_index(
        "ix_tasks_user_created", "tasks", ["user_id", sa.text("created_at DESC")]
    )

    # 系统监控：按状态查询活跃任务（条件索引）
    op.create_index(
        "ix_tasks_status",
        "tasks",
        ["status"],
        postgresql_where=sa.text("status IN ('pending', 'processing')"),
    )

    # 性能优化：处理中任务按时间排序（条件索引）
    op.create_index(
        "ix_tasks_processing",
        "tasks",
        ["created_at"],
        postgresql_where=sa.text("status = 'processing'"),
    )

    # 创建自动更新updated_at字段的触发器函数
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_tasks_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """
    )

    # 创建触发器
    op.execute(
        """
        CREATE TRIGGER tr_tasks_updated_at
            BEFORE UPDATE ON tasks
            FOR EACH ROW
            EXECUTE FUNCTION update_tasks_updated_at();
    """
    )

    # 添加表和列注释
    op.execute("COMMENT ON TABLE tasks IS '用户分析任务表 - 支持完整生命周期管理和多租户数据隔离'")
    op.execute("COMMENT ON COLUMN tasks.id IS '任务唯一标识'")
    op.execute("COMMENT ON COLUMN tasks.user_id IS '任务所属用户，实现多租户隔离'")
    op.execute("COMMENT ON COLUMN tasks.product_description IS '用户输入的产品描述，10-2000字符'")
    op.execute(
        "COMMENT ON COLUMN tasks.status IS '任务状态：pending/processing/completed/failed'"
    )
    op.execute("COMMENT ON COLUMN tasks.error_message IS '失败时的错误详情'")
    op.execute("COMMENT ON COLUMN tasks.completed_at IS '任务完成时间，只有completed状态时才设置'")


def downgrade() -> None:
    """删除tasks表和相关对象"""

    # 确保在正确的模式中
    op.execute("SET search_path TO signal_scanner, public")

    # 删除触发器和函数
    op.execute("DROP TRIGGER IF EXISTS tr_tasks_updated_at ON tasks")
    op.execute("DROP FUNCTION IF EXISTS update_tasks_updated_at()")

    # 删除索引（表删除时会自动删除，但明确列出更清晰）
    op.drop_index("ix_tasks_processing", "tasks")
    op.drop_index("ix_tasks_status", "tasks")
    op.drop_index("ix_tasks_user_created", "tasks")
    op.drop_index("ix_tasks_user_status", "tasks")

    # 删除表
    op.drop_table("tasks")


# Linus式迁移设计说明:
#
# 1. 幂等性操作
#    - 使用IF EXISTS确保可重复执行
#    - 明确的upgrade/downgrade路径
#
# 2. 原子性保证
#    - 单个事务中创建表、索引、约束
#    - 失败时自动回滚，保持数据库一致性
#
# 3. 索引策略清晰
#    - 基于真实查询模式设计
#    - 条件索引节省存储空间
#
# 4. 约束在正确位置
#    - 数据完整性约束在数据库层
#    - 业务逻辑约束在应用层
#
# 5. 注释完整
#    - 每个字段都有业务含义说明
#    - 便于后续维护和理解
