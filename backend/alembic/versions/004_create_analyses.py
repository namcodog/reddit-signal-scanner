"""创建analyses表和JSONB索引优化

Revision ID: 004_create_analyses
Revises: 003_create_schema_validation
Create Date: 2025-08-22 22:15:00.123456

基于 Linus 原则：数据结构决定代码复杂度
- 一对一关系：task_id UNIQUE 确保每个任务只有一个分析结果
- JSONB优化：GIN索引支持高效的包含查询
- Schema验证：数据库层面确保JSONB结构正确
- 性能优化：针对查询模式设计的复合索引
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "004_create_analyses"
down_revision = "003_create_schema_validation"
branch_labels = None
depends_on = None


def upgrade():
    """创建analyses表和相关优化"""

    # ===== 创建analyses表 =====
    op.create_table(
        "analyses",
        # 主键和外键
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        # JSONB存储字段
        sa.Column("insights", postgresql.JSONB, nullable=False),
        sa.Column("sources", postgresql.JSONB, nullable=False),
        # 元数据字段
        sa.Column("confidence_score", sa.Numeric(3, 2), nullable=False),
        sa.Column("analysis_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # 约束定义
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], ondelete="CASCADE", name="fk_analyses_task_id"
        ),
        sa.UniqueConstraint("task_id", name="uq_analyses_task_id"),
        sa.CheckConstraint(
            "confidence_score >= 0.00 AND confidence_score <= 1.00",
            name="ck_analyses_confidence_range",
        ),
        sa.CheckConstraint("analysis_version > 0", name="ck_analyses_version_positive"),
        sa.CheckConstraint(
            "validate_insights_schema(insights)", name="ck_analyses_insights_schema"
        ),
        sa.CheckConstraint(
            "validate_sources_schema(sources)", name="ck_analyses_sources_schema"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # ===== 创建GIN索引（JSONB优化）=====

    # insights字段：使用jsonb_path_ops优化包含查询
    op.create_index(
        "ix_analyses_insights_gin",
        "analyses",
        ["insights"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"insights": "jsonb_path_ops"},
    )

    # sources字段：使用默认GIN操作符，支持多种查询
    op.create_index(
        "ix_analyses_sources_gin",
        "analyses",
        ["sources"],
        unique=False,
        postgresql_using="gin",
    )

    # ===== 创建B-tree索引（排序和范围查询优化）=====

    # 置信度降序索引：支持高质量分析查询
    op.create_index(
        "ix_analyses_confidence_desc",
        "analyses",
        [sa.text("confidence_score DESC")],
        unique=False,
    )

    # 创建时间降序索引：支持最新分析查询
    op.create_index(
        "ix_analyses_created_desc",
        "analyses",
        [sa.text("created_at DESC")],
        unique=False,
    )

    # ===== 创建复合索引（多列查询优化）=====

    # task_id + created_at：关联查询优化
    op.create_index(
        "ix_analyses_task_created",
        "analyses",
        ["task_id", sa.text("created_at DESC")],
        unique=False,
    )

    # confidence_score + created_at：质量和时间组合查询
    op.create_index(
        "ix_analyses_confidence_created",
        "analyses",
        [sa.text("confidence_score DESC"), sa.text("created_at DESC")],
        unique=False,
    )

    # analysis_version + created_at：版本迭代分析
    op.create_index(
        "ix_analyses_version_created",
        "analyses",
        ["analysis_version", sa.text("created_at DESC")],
        unique=False,
    )

    # ===== 创建触发器函数 =====

    # 任务完成状态自动更新函数
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_task_completion_status()
        RETURNS TRIGGER AS $$
        BEGIN
            -- 更新关联任务状态为已完成
            UPDATE tasks 
            SET status = 'completed',
                completed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = NEW.task_id 
              AND status = 'processing';
            
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """
    )

    # 创建触发器
    op.execute(
        """
        CREATE TRIGGER tr_analyses_completion
            AFTER INSERT ON analyses
            FOR EACH ROW
            EXECUTE FUNCTION update_task_completion_status();
    """
    )

    # ===== 启用行级安全策略 =====

    # 启用RLS
    op.execute("ALTER TABLE analyses ENABLE ROW LEVEL SECURITY;")

    # 创建租户隔离策略
    op.execute(
        """
        CREATE POLICY policy_analyses_tenant_isolation ON analyses
            USING (
                task_id IN (
                    SELECT id FROM tasks 
                    WHERE user_id = current_setting('app.current_user_id')::UUID
                )
            );
    """
    )

    # ===== 存储和统计优化 =====

    # JSONB字段压缩存储
    op.execute("ALTER TABLE analyses ALTER COLUMN insights SET STORAGE EXTENDED;")
    op.execute("ALTER TABLE analyses ALTER COLUMN sources SET STORAGE EXTENDED;")

    # 统计信息收集优化
    op.execute("ALTER TABLE analyses ALTER COLUMN insights SET STATISTICS 1000;")
    op.execute("ALTER TABLE analyses ALTER COLUMN sources SET STATISTICS 1000;")

    # ===== 创建性能监控视图 =====

    op.execute(
        """
        CREATE OR REPLACE VIEW v_analyses_stats AS
        SELECT 
            DATE_TRUNC('day', created_at) as analysis_date,
            COUNT(*) as total_analyses,
            AVG(confidence_score) as avg_confidence,
            MIN(confidence_score) as min_confidence,
            MAX(confidence_score) as max_confidence,
            AVG(pg_column_size(insights)) as avg_insights_size,
            AVG(pg_column_size(sources)) as avg_sources_size,
            COUNT(DISTINCT analysis_version) as version_count
        FROM analyses
        GROUP BY DATE_TRUNC('day', created_at)
        ORDER BY analysis_date DESC;
    """
    )

    # ===== 创建维护函数 =====

    # 清理低质量分析函数
    op.execute(
        """
        CREATE OR REPLACE FUNCTION cleanup_low_confidence_analyses(
            confidence_threshold DECIMAL DEFAULT 0.3,
            days_old INTEGER DEFAULT 90
        ) RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            DELETE FROM analyses 
            WHERE confidence_score < confidence_threshold
              AND created_at < CURRENT_TIMESTAMP - (days_old || ' days')::INTERVAL;
            
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """
    )

    # GIN索引重建函数
    op.execute(
        """
        CREATE OR REPLACE FUNCTION rebuild_analyses_gin_indexes() RETURNS VOID AS $$
        BEGIN
            REINDEX INDEX CONCURRENTLY ix_analyses_insights_gin;
            REINDEX INDEX CONCURRENTLY ix_analyses_sources_gin;
        END;
        $$ LANGUAGE plpgsql;
    """
    )

    # ===== 数据验证和测试 =====

    # 验证表创建和约束
    op.execute(
        """
        DO $$
        DECLARE
            table_exists BOOLEAN;
            constraint_count INTEGER;
            index_count INTEGER;
        BEGIN
            -- 检查表是否创建成功
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'analyses' AND table_schema = 'public'
            ) INTO table_exists;
            
            IF NOT table_exists THEN
                RAISE EXCEPTION 'analyses表创建失败';
            END IF;
            
            -- 检查约束数量
            SELECT COUNT(*) INTO constraint_count
            FROM information_schema.table_constraints 
            WHERE table_name = 'analyses' AND table_schema = 'public';
            
            IF constraint_count < 6 THEN
                RAISE WARNING '约束创建不完整，实际: %, 预期: >= 6', constraint_count;
            END IF;
            
            -- 检查GIN索引
            SELECT COUNT(*) INTO index_count
            FROM pg_indexes 
            WHERE tablename = 'analyses' AND indexdef LIKE '%USING gin%';
            
            IF index_count < 2 THEN
                RAISE WARNING 'GIN索引创建不完整，实际: %, 预期: >= 2', index_count;
            END IF;
            
            RAISE NOTICE '✅ analyses表创建完成! 约束: %, GIN索引: %', constraint_count, index_count;
        END $$;
    """
    )


def downgrade():
    """回滚analyses表创建"""

    # 删除维护函数
    op.execute("DROP FUNCTION IF EXISTS rebuild_analyses_gin_indexes();")
    op.execute(
        "DROP FUNCTION IF EXISTS cleanup_low_confidence_analyses(DECIMAL, INTEGER);"
    )

    # 删除视图
    op.execute("DROP VIEW IF EXISTS v_analyses_stats;")

    # 删除触发器和函数
    op.execute("DROP TRIGGER IF EXISTS tr_analyses_completion ON analyses;")
    op.execute("DROP FUNCTION IF EXISTS update_task_completion_status();")

    # 删除行级安全策略
    op.execute("DROP POLICY IF EXISTS policy_analyses_tenant_isolation ON analyses;")

    # 删除索引（复合索引）
    op.drop_index("ix_analyses_version_created", table_name="analyses")
    op.drop_index("ix_analyses_confidence_created", table_name="analyses")
    op.drop_index("ix_analyses_task_created", table_name="analyses")

    # 删除索引（单列B-tree）
    op.drop_index("ix_analyses_created_desc", table_name="analyses")
    op.drop_index("ix_analyses_confidence_desc", table_name="analyses")

    # 删除索引（GIN）
    op.drop_index("ix_analyses_sources_gin", table_name="analyses")
    op.drop_index("ix_analyses_insights_gin", table_name="analyses")

    # 删除表
    op.drop_table("analyses")

    print("✅ analyses表和相关对象已回滚")
