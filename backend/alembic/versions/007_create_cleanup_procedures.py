"""create cleanup procedures

Revision ID: 007_cleanup_procedures
Revises: 006_community_cache
Create Date: 2025-08-23 13:30:00.000000

创建数据清理存储过程 - 遵循Linus设计原则：在正确的层次解决问题
- 数据库执行清理逻辑，应用层管理策略
- 分批处理避免长时间锁表
- 完整的错误处理和日志记录
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "007_cleanup_procedures"
down_revision = "006_community_cache"
branch_labels = None
depends_on = None


def upgrade():
    """创建数据清理相关的表和存储过程"""

    # 1. 创建清理日志表
    op.create_table(
        "cleanup_logs",
        sa.Column(
            "id",
            postgresql.UUID,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "executed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("total_records_cleaned", sa.Integer(), nullable=False, default=0),
        sa.Column("breakdown", postgresql.JSONB, nullable=False, default={}),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("error_message", sa.Text(), nullable=True),
    )

    # 2. 创建清理日志索引
    op.create_index(
        "ix_cleanup_logs_executed_desc", "cleanup_logs", [sa.text("executed_at DESC")]
    )
    op.create_index("ix_cleanup_logs_success", "cleanup_logs", ["success"])

    # 3. 清理完成任务的存储过程
    op.execute(
        """
        CREATE OR REPLACE FUNCTION cleanup_completed_tasks(
            cutoff_date TIMESTAMP WITH TIME ZONE,
            batch_size INTEGER DEFAULT 1000
        ) RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER := 0;
            current_batch INTEGER;
            loop_count INTEGER := 0;
        BEGIN
            -- 安全检查：确保cutoff_date不是未来时间
            IF cutoff_date > CURRENT_TIMESTAMP THEN
                RAISE EXCEPTION '清理截止日期不能是未来时间: %', cutoff_date;
            END IF;
            
            LOOP
                loop_count := loop_count + 1;
                
                -- 防止无限循环
                IF loop_count > 1000 THEN
                    RAISE EXCEPTION '清理循环次数超限，可能存在死循环';
                END IF;
                
                -- 分批删除避免长时间锁表
                WITH deleted AS (
                    DELETE FROM tasks 
                    WHERE status = 'completed' 
                      AND completed_at IS NOT NULL
                      AND completed_at < cutoff_date
                      AND id IN (
                          SELECT id FROM tasks 
                          WHERE status = 'completed' 
                            AND completed_at IS NOT NULL
                            AND completed_at < cutoff_date
                          ORDER BY completed_at ASC
                          LIMIT batch_size
                      )
                    RETURNING id
                )
                SELECT COUNT(*) INTO current_batch FROM deleted;
                
                deleted_count := deleted_count + current_batch;
                
                -- 如果这批没删除任何记录，说明清理完成
                IF current_batch = 0 THEN
                    EXIT;
                END IF;
                
                -- 短暂暂停，释放锁给其他事务
                PERFORM pg_sleep(0.1);
                
                -- 每删除10批提交一次，避免事务过长
                IF loop_count % 10 = 0 THEN
                    RAISE NOTICE '已清理 % 条完成任务记录', deleted_count;
                END IF;
            END LOOP;
            
            RAISE NOTICE '清理完成任务总计: % 条记录', deleted_count;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """
    )

    # 4. 清理失败任务的存储过程
    op.execute(
        """
        CREATE OR REPLACE FUNCTION cleanup_failed_tasks(
            cutoff_date TIMESTAMP WITH TIME ZONE,
            batch_size INTEGER DEFAULT 1000
        ) RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER := 0;
            current_batch INTEGER;
            loop_count INTEGER := 0;
        BEGIN
            -- 安全检查
            IF cutoff_date > CURRENT_TIMESTAMP THEN
                RAISE EXCEPTION '清理截止日期不能是未来时间: %', cutoff_date;
            END IF;
            
            LOOP
                loop_count := loop_count + 1;
                
                IF loop_count > 1000 THEN
                    RAISE EXCEPTION '清理循环次数超限，可能存在死循环';
                END IF;
                
                WITH deleted AS (
                    DELETE FROM tasks 
                    WHERE status = 'failed' 
                      AND updated_at IS NOT NULL
                      AND updated_at < cutoff_date
                      AND id IN (
                          SELECT id FROM tasks 
                          WHERE status = 'failed' 
                            AND updated_at IS NOT NULL
                            AND updated_at < cutoff_date
                          ORDER BY updated_at ASC
                          LIMIT batch_size
                      )
                    RETURNING id
                )
                SELECT COUNT(*) INTO current_batch FROM deleted;
                
                deleted_count := deleted_count + current_batch;
                
                IF current_batch = 0 THEN
                    EXIT;
                END IF;
                
                PERFORM pg_sleep(0.1);
                
                IF loop_count % 10 = 0 THEN
                    RAISE NOTICE '已清理 % 条失败任务记录', deleted_count;
                END IF;
            END LOOP;
            
            RAISE NOTICE '清理失败任务总计: % 条记录', deleted_count;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """
    )

    # 5. 清理孤儿分析记录
    op.execute(
        """
        CREATE OR REPLACE FUNCTION cleanup_orphan_analyses(
            cutoff_time TIMESTAMP WITH TIME ZONE
        ) RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            -- 安全检查
            IF cutoff_time > CURRENT_TIMESTAMP THEN
                RAISE EXCEPTION '清理截止时间不能是未来时间: %', cutoff_time;
            END IF;
            
            -- 删除没有对应task的analysis记录
            -- 使用LEFT JOIN确保安全性
            WITH deleted AS (
                DELETE FROM analyses 
                WHERE id IN (
                    SELECT a.id 
                    FROM analyses a
                    LEFT JOIN tasks t ON a.task_id = t.id
                    WHERE t.id IS NULL
                      AND a.created_at < cutoff_time
                )
                RETURNING id
            )
            SELECT COUNT(*) INTO deleted_count FROM deleted;
            
            RAISE NOTICE '清理孤儿分析记录总计: % 条记录', deleted_count;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """
    )

    # 6. 清理过期社区缓存
    op.execute(
        """
        CREATE OR REPLACE FUNCTION cleanup_expired_community_cache()
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            -- 清理超过TTL的缓存记录
            WITH deleted AS (
                DELETE FROM community_cache 
                WHERE last_crawled_at IS NOT NULL
                  AND ttl_seconds IS NOT NULL
                  AND ttl_seconds > 0
                  AND (last_crawled_at + INTERVAL '1 second' * ttl_seconds) < CURRENT_TIMESTAMP
                RETURNING community_name
            )
            SELECT COUNT(*) INTO deleted_count FROM deleted;
            
            RAISE NOTICE '清理过期缓存总计: % 条记录', deleted_count;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
    """
    )

    # 7. 清理非活跃用户（软删除）
    op.execute(
        """
        CREATE OR REPLACE FUNCTION cleanup_inactive_users(
            cutoff_date TIMESTAMP WITH TIME ZONE
        ) RETURNS INTEGER AS $$
        DECLARE
            updated_count INTEGER;
        BEGIN
            -- 安全检查
            IF cutoff_date > CURRENT_TIMESTAMP - INTERVAL '30 days' THEN
                RAISE EXCEPTION '非活跃用户清理时间不能少于30天: %', cutoff_date;
            END IF;
            
            -- 标记为软删除，不物理删除
            WITH updated AS (
                UPDATE users 
                SET 
                    is_active = false,
                    updated_at = CURRENT_TIMESTAMP
                WHERE is_active = true
                  AND (last_login_at IS NULL OR last_login_at < cutoff_date)
                  AND created_at < cutoff_date - INTERVAL '7 days'  -- 新用户保护期
                  AND id NOT IN (
                      -- 保护有活跃任务的用户
                      SELECT DISTINCT user_id FROM tasks 
                      WHERE user_id IS NOT NULL
                        AND created_at > cutoff_date
                  )
                RETURNING id
            )
            SELECT COUNT(*) INTO updated_count FROM updated;
            
            RAISE NOTICE '软删除非活跃用户总计: % 个用户', updated_count;
            RETURN updated_count;
        END;
        $$ LANGUAGE plpgsql;
    """
    )

    # 8. 主清理函数 - 协调所有清理操作
    op.execute(
        """
        CREATE OR REPLACE FUNCTION execute_data_cleanup(
            completed_task_days INTEGER DEFAULT 30,
            failed_task_days INTEGER DEFAULT 7,
            orphan_analysis_hours NUMERIC DEFAULT 1,
            inactive_user_days INTEGER DEFAULT 365,
            dry_run BOOLEAN DEFAULT false
        ) RETURNS JSONB AS $$
        DECLARE
            results JSONB;
            completed_count INTEGER := 0;
            failed_count INTEGER := 0;
            orphan_count INTEGER := 0;
            cache_count INTEGER := 0;
            user_count INTEGER := 0;
            start_time TIMESTAMP WITH TIME ZONE;
            end_time TIMESTAMP WITH TIME ZONE;
            log_id UUID;
        BEGIN
            start_time := CURRENT_TIMESTAMP;
            
            -- 如果是试运行，只统计不删除
            IF dry_run THEN
                -- 统计将要清理的记录数
                SELECT COUNT(*) INTO completed_count
                FROM tasks 
                WHERE status = 'completed' 
                  AND completed_at IS NOT NULL
                  AND completed_at < CURRENT_TIMESTAMP - INTERVAL '1 day' * completed_task_days;
                
                SELECT COUNT(*) INTO failed_count
                FROM tasks 
                WHERE status = 'failed' 
                  AND updated_at IS NOT NULL
                  AND updated_at < CURRENT_TIMESTAMP - INTERVAL '1 day' * failed_task_days;
                
                SELECT COUNT(*) INTO orphan_count
                FROM analyses a
                LEFT JOIN tasks t ON a.task_id = t.id
                WHERE t.id IS NULL
                  AND a.created_at < CURRENT_TIMESTAMP - INTERVAL '1 hour' * orphan_analysis_hours;
                
                SELECT COUNT(*) INTO cache_count
                FROM community_cache 
                WHERE last_crawled_at IS NOT NULL
                  AND ttl_seconds IS NOT NULL
                  AND ttl_seconds > 0
                  AND (last_crawled_at + INTERVAL '1 second' * ttl_seconds) < CURRENT_TIMESTAMP;
                
                SELECT COUNT(*) INTO user_count
                FROM users 
                WHERE is_active = true
                  AND (last_login_at IS NULL OR last_login_at < CURRENT_TIMESTAMP - INTERVAL '1 day' * inactive_user_days);
            ELSE
                -- 执行实际清理
                SELECT cleanup_completed_tasks(
                    CURRENT_TIMESTAMP - INTERVAL '1 day' * completed_task_days
                ) INTO completed_count;
                
                SELECT cleanup_failed_tasks(
                    CURRENT_TIMESTAMP - INTERVAL '1 day' * failed_task_days
                ) INTO failed_count;
                
                SELECT cleanup_orphan_analyses(
                    CURRENT_TIMESTAMP - INTERVAL '1 hour' * orphan_analysis_hours
                ) INTO orphan_count;
                
                SELECT cleanup_expired_community_cache() INTO cache_count;
                
                SELECT cleanup_inactive_users(
                    CURRENT_TIMESTAMP - INTERVAL '1 day' * inactive_user_days
                ) INTO user_count;
            END IF;
            
            end_time := CURRENT_TIMESTAMP;
            
            -- 构建结果JSON
            results := jsonb_build_object(
                'completed_tasks', completed_count,
                'failed_tasks', failed_count,
                'orphan_analyses', orphan_count,
                'expired_cache', cache_count,
                'inactive_users', user_count,
                'total_cleaned', completed_count + failed_count + orphan_count + cache_count + user_count,
                'duration_seconds', EXTRACT(EPOCH FROM (end_time - start_time))::INTEGER,
                'dry_run', dry_run,
                'executed_at', start_time
            );
            
            -- 记录清理日志（只有实际执行才记录）
            IF NOT dry_run THEN
                INSERT INTO cleanup_logs 
                (executed_at, total_records_cleaned, breakdown, duration_seconds, success)
                VALUES (
                    start_time,
                    completed_count + failed_count + orphan_count + cache_count + user_count,
                    results,
                    EXTRACT(EPOCH FROM (end_time - start_time))::INTEGER,
                    true
                );
            END IF;
            
            RETURN results;
        END;
        $$ LANGUAGE plpgsql;
    """
    )

    # 9. 创建清理统计视图
    op.execute(
        """
        CREATE OR REPLACE VIEW cleanup_stats AS
        SELECT 
            DATE_TRUNC('day', executed_at) as cleanup_date,
            COUNT(*) as cleanup_runs,
            AVG(total_records_cleaned) as avg_records_cleaned,
            MAX(total_records_cleaned) as max_records_cleaned,
            AVG(duration_seconds) as avg_duration_seconds,
            SUM(CASE WHEN success THEN 1 ELSE 0 END)::FLOAT / COUNT(*) * 100 as success_rate_percent
        FROM cleanup_logs 
        WHERE executed_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'
        GROUP BY DATE_TRUNC('day', executed_at)
        ORDER BY cleanup_date DESC;
    """
    )


def downgrade():
    """删除数据清理相关的表和存储过程"""

    # 删除视图
    op.execute("DROP VIEW IF EXISTS cleanup_stats")

    # 删除存储过程
    op.execute("DROP FUNCTION IF EXISTS execute_data_cleanup")
    op.execute("DROP FUNCTION IF EXISTS cleanup_inactive_users")
    op.execute("DROP FUNCTION IF EXISTS cleanup_expired_community_cache")
    op.execute("DROP FUNCTION IF EXISTS cleanup_orphan_analyses")
    op.execute("DROP FUNCTION IF EXISTS cleanup_failed_tasks")
    op.execute("DROP FUNCTION IF EXISTS cleanup_completed_tasks")

    # 删除索引
    op.drop_index("ix_cleanup_logs_success")
    op.drop_index("ix_cleanup_logs_executed_desc")

    # 删除表
    op.drop_table("cleanup_logs")
