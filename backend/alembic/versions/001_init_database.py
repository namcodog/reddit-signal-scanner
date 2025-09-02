"""创建Reddit Signal Scanner基础数据表结构

迁移ID: 001_init_database
基于版本: None
创建时间: 2025-08-22

基于 Linus Torvalds 设计哲学和 PRD-01 要求：
- 5张核心表：users, tasks, analyses, reports, community_cache
- 立即支持多租户（user_id从第一天存在）
- JSON Schema验证函数防止数据格式错误
- 完整的索引策略支持高性能查询
- 缓存优先架构支持
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "001_init_database"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """执行数据库升级操作 - 创建完整的表结构"""

    # 1. 启用必要的PostgreSQL扩展
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "btree_gin"')

    # 2. 创建枚举类型
    task_status_enum = postgresql.ENUM(
        "pending",
        "processing",
        "completed",
        "failed",
        name="task_status",
        create_type=True,
    )
    task_status_enum.create(op.get_bind())

    # 3. 创建JSON Schema验证函数

    # insights JSON schema验证函数
    op.execute(
        """
    CREATE OR REPLACE FUNCTION validate_insights_schema(data jsonb)
    RETURNS boolean AS $$
    BEGIN
        -- 必须是对象类型
        IF jsonb_typeof(data) != 'object' THEN
            RETURN false;
        END IF;
        
        -- 必须包含三个核心字段
        IF NOT (data ? 'pain_points' AND data ? 'competitors' AND data ? 'opportunities') THEN
            RETURN false;
        END IF;
        
        -- 每个字段必须是数组
        IF jsonb_typeof(data->'pain_points') != 'array' OR
           jsonb_typeof(data->'competitors') != 'array' OR 
           jsonb_typeof(data->'opportunities') != 'array' THEN
            RETURN false;
        END IF;
        
        -- 验证pain_points结构
        IF EXISTS (
            SELECT 1 FROM jsonb_array_elements(data->'pain_points') AS item
            WHERE NOT (item ? 'description' AND item ? 'frequency' AND item ? 'sentiment_score')
        ) THEN
            RETURN false;
        END IF;
        
        RETURN true;
    END;
    $$ LANGUAGE plpgsql;
    """
    )

    # sources JSON schema验证函数
    op.execute(
        """
    CREATE OR REPLACE FUNCTION validate_sources_schema(data jsonb)
    RETURNS boolean AS $$
    BEGIN
        IF jsonb_typeof(data) != 'object' THEN
            RETURN false;
        END IF;
        
        -- 必须包含核心溯源字段
        IF NOT (data ? 'communities' AND data ? 'posts_analyzed' AND data ? 'cache_hit_rate') THEN
            RETURN false;
        END IF;
        
        -- communities必须是数组
        IF jsonb_typeof(data->'communities') != 'array' THEN
            RETURN false;
        END IF;
        
        -- posts_analyzed必须是数字
        IF jsonb_typeof(data->'posts_analyzed') != 'number' THEN
            RETURN false;
        END IF;
        
        RETURN true;
    END;
    $$ LANGUAGE plpgsql;
    """
    )

    # 4. 创建用户表（多租户基础）
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.CheckConstraint(
            "email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'",
            name="valid_email",
        ),
    )

    # 5. 创建任务表（立即支持多租户）
    op.create_table(
        "tasks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_description", sa.Text(), nullable=False),
        sa.Column("status", task_status_enum, nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "char_length(product_description) BETWEEN 10 AND 2000",
            name="valid_description_length",
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR completed_at >= created_at",
            name="valid_completion_time",
        ),
    )

    # 6. 创建分析表（带Schema验证）
    op.create_table(
        "analyses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("insights", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sources", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence_score", sa.DECIMAL(precision=3, scale=2), nullable=True),
        sa.Column(
            "analysis_version", sa.String(10), nullable=False, server_default="1.0"
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("task_id"),
        sa.CheckConstraint(
            "confidence_score IS NULL OR (confidence_score BETWEEN 0.00 AND 1.00)",
            name="valid_confidence_score",
        ),
        sa.CheckConstraint(
            "validate_insights_schema(insights)", name="valid_insights_schema"
        ),
        sa.CheckConstraint(
            "validate_sources_schema(sources)", name="valid_sources_schema"
        ),
    )

    # 7. 创建报告表
    op.create_table(
        "reports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("html_content", sa.Text(), nullable=False),
        sa.Column(
            "template_version", sa.String(10), nullable=False, server_default="1.0"
        ),
        sa.Column(
            "generated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["analysis_id"], ["analyses.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("analysis_id"),
    )

    # 8. 创建缓存状态表（支持缓存优先架构）
    op.create_table(
        "community_cache",
        sa.Column("community_name", sa.String(100), nullable=False),
        sa.Column("last_crawled_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("posts_cached", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ttl_seconds", sa.Integer(), nullable=True, server_default="3600"),
        sa.Column(
            "quality_score",
            sa.DECIMAL(precision=3, scale=2),
            nullable=True,
            server_default="0.50",
        ),
        sa.Column("hit_count", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("crawl_priority", sa.Integer(), nullable=True, server_default="50"),
        sa.Column("last_hit_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("community_name"),
        sa.CheckConstraint("posts_cached >= 0", name="valid_cache_data"),
        sa.CheckConstraint("ttl_seconds IS NULL OR ttl_seconds > 0", name="valid_ttl"),
        sa.CheckConstraint(
            "crawl_priority IS NULL OR (crawl_priority BETWEEN 1 AND 100)",
            name="valid_crawl_priority",
        ),
    )

    # 9. 创建优化索引（支持多租户查询）

    # Users表索引
    op.create_index("idx_users_email", "users", ["email"])
    op.create_index(
        "idx_users_active",
        "users",
        ["is_active"],
        postgresql_where=sa.text("is_active = true"),
    )

    # Tasks表索引（基于真实查询模式，重点支持多租户）
    op.create_index("idx_tasks_user_status", "tasks", ["user_id", "status"])
    op.create_index(
        "idx_tasks_user_created",
        "tasks",
        ["user_id", "created_at"],
        postgresql_using="btree",
        postgresql_ops={"created_at": "DESC"},
    )
    op.create_index("idx_tasks_status", "tasks", ["status"])

    # Analyses表索引
    op.create_index(
        "idx_analyses_confidence",
        "analyses",
        ["confidence_score"],
        postgresql_using="btree",
        postgresql_ops={"confidence_score": "DESC"},
    )
    op.create_index("idx_analyses_version", "analyses", ["analysis_version"])
    op.create_index(
        "idx_analyses_created",
        "analyses",
        ["created_at"],
        postgresql_using="btree",
        postgresql_ops={"created_at": "DESC"},
    )

    # JSONB字段的GIN索引（支持复杂洞察查询）
    op.create_index(
        "idx_analyses_insights_gin", "analyses", ["insights"], postgresql_using="gin"
    )
    op.create_index(
        "idx_analyses_sources_gin", "analyses", ["sources"], postgresql_using="gin"
    )

    # Reports表索引
    op.create_index(
        "idx_reports_generated",
        "reports",
        ["generated_at"],
        postgresql_using="btree",
        postgresql_ops={"generated_at": "DESC"},
    )
    op.create_index("idx_reports_template", "reports", ["template_version"])

    # CommunityCache表索引（支持缓存优先架构）
    op.create_index(
        "idx_cache_priority",
        "community_cache",
        ["crawl_priority"],
        postgresql_using="btree",
        postgresql_ops={"crawl_priority": "DESC"},
    )
    op.create_index("idx_cache_last_crawled", "community_cache", ["last_crawled_at"])
    op.create_index(
        "idx_cache_hit_count",
        "community_cache",
        ["hit_count"],
        postgresql_using="btree",
        postgresql_ops={"hit_count": "DESC"},
    )
    op.create_index(
        "idx_cache_quality",
        "community_cache",
        ["quality_score"],
        postgresql_using="btree",
        postgresql_ops={"quality_score": "DESC"},
    )


def downgrade() -> None:
    """执行数据库降级操作 - 删除所有表和对象"""

    # 删除索引（PostgreSQL会自动删除，但明确列出用于文档）
    op.drop_index("idx_cache_quality", table_name="community_cache")
    op.drop_index("idx_cache_hit_count", table_name="community_cache")
    op.drop_index("idx_cache_last_crawled", table_name="community_cache")
    op.drop_index("idx_cache_priority", table_name="community_cache")
    op.drop_index("idx_reports_template", table_name="reports")
    op.drop_index("idx_reports_generated", table_name="reports")
    op.drop_index("idx_analyses_sources_gin", table_name="analyses")
    op.drop_index("idx_analyses_insights_gin", table_name="analyses")
    op.drop_index("idx_analyses_created", table_name="analyses")
    op.drop_index("idx_analyses_version", table_name="analyses")
    op.drop_index("idx_analyses_confidence", table_name="analyses")
    op.drop_index("idx_tasks_status", table_name="tasks")
    op.drop_index("idx_tasks_user_created", table_name="tasks")
    op.drop_index("idx_tasks_user_status", table_name="tasks")
    op.drop_index("idx_users_active", table_name="users")
    op.drop_index("idx_users_email", table_name="users")

    # 删除表（按依赖关系逆序）
    op.drop_table("community_cache")
    op.drop_table("reports")
    op.drop_table("analyses")
    op.drop_table("tasks")
    op.drop_table("users")

    # 删除JSON验证函数
    op.execute("DROP FUNCTION IF EXISTS validate_sources_schema(jsonb)")
    op.execute("DROP FUNCTION IF EXISTS validate_insights_schema(jsonb)")

    # 删除枚举类型
    op.execute("DROP TYPE IF EXISTS task_status")

    # 删除扩展（谨慎操作，可能被其他对象使用）
    # op.execute('DROP EXTENSION IF EXISTS "btree_gin"')
    # op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
