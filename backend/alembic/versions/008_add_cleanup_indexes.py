"""add cleanup performance indexes

Revision ID: 008_cleanup_indexes
Revises: 007_cleanup_procedures
Create Date: 2025-08-23 14:30:00.000000

添加数据清理性能索引 - 优化清理查询性能
基于Quality-Gate检查结果，添加关键复合索引
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "008_cleanup_indexes"
down_revision = "007_cleanup_procedures"
branch_labels = None
depends_on = None


def upgrade():
    """添加清理相关的性能索引"""

    # 1. 为完成任务清理添加复合索引
    # 优化: WHERE status = 'completed' AND completed_at < cutoff_date
    op.execute(
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tasks_completed_cleanup 
        ON tasks(status, completed_at) 
        WHERE status = 'completed' AND completed_at IS NOT NULL
    """
    )

    # 2. 为失败任务清理添加复合索引
    # 优化: WHERE status = 'failed' AND updated_at < cutoff_date
    op.execute(
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tasks_failed_cleanup 
        ON tasks(status, updated_at) 
        WHERE status = 'failed' AND updated_at IS NOT NULL
    """
    )

    # 3. 为孤儿分析查询添加索引
    # 优化: analyses表的task_id和created_at联合查询
    op.execute(
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_analyses_task_created 
        ON analyses(task_id, created_at) 
        WHERE task_id IS NOT NULL
    """
    )

    # 4. 为社区缓存TTL查询添加索引
    # 优化: WHERE last_crawled_at + INTERVAL '1 second' * ttl_seconds < CURRENT_TIMESTAMP
    op.execute(
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_community_cache_ttl 
        ON community_cache(last_crawled_at, ttl_seconds) 
        WHERE last_crawled_at IS NOT NULL AND ttl_seconds IS NOT NULL AND ttl_seconds > 0
    """
    )

    # 5. 为用户活跃度查询添加索引
    # 优化: WHERE is_active = true AND last_login_at < cutoff_date
    op.execute(
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_active_login 
        ON users(is_active, last_login_at, created_at) 
        WHERE is_active = true
    """
    )

    # 6. 为清理日志查询添加额外索引
    # 优化时间范围查询和成功率统计
    op.execute(
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cleanup_logs_time_success 
        ON cleanup_logs(executed_at DESC, success, total_records_cleaned)
    """
    )


def downgrade():
    """删除清理相关的性能索引"""

    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_cleanup_logs_time_success")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_users_active_login")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_community_cache_ttl")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_analyses_task_created")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_tasks_failed_cleanup")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_tasks_completed_cleanup")
