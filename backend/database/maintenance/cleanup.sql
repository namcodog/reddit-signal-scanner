-- 数据清理维护脚本 - Reddit Signal Scanner
-- 提供手动执行数据清理的SQL脚本，用于维护和调试
-- 
-- 使用方法：
--   1. 预览清理效果: \i cleanup.sql 然后执行 SELECT * FROM cleanup_preview();
--   2. 执行实际清理: SELECT * FROM execute_data_cleanup();
--   3. 紧急清理: SELECT * FROM execute_emergency_cleanup();

-- ============================================================================
-- 1. 数据清理预览函数 - 查看将要清理的数据统计
-- ============================================================================

CREATE OR REPLACE FUNCTION cleanup_preview()
RETURNS TABLE(
    category VARCHAR(50),
    current_count INTEGER,
    to_be_cleaned INTEGER,
    retention_policy TEXT,
    estimated_space_saved_mb NUMERIC
) AS $$
BEGIN
    -- 完成的任务 (30天保留)
    RETURN QUERY
    SELECT 
        'completed_tasks'::VARCHAR(50) as category,
        (SELECT COUNT(*)::INTEGER FROM tasks WHERE status = 'completed') as current_count,
        (SELECT COUNT(*)::INTEGER 
         FROM tasks 
         WHERE status = 'completed' 
           AND completed_at IS NOT NULL
           AND completed_at < CURRENT_TIMESTAMP - INTERVAL '30 days') as to_be_cleaned,
        '保留30天，之后删除'::TEXT as retention_policy,
        (SELECT COUNT(*)::INTEGER 
         FROM tasks 
         WHERE status = 'completed' 
           AND completed_at < CURRENT_TIMESTAMP - INTERVAL '30 days') * 0.001 as estimated_space_saved_mb;

    -- 失败的任务 (7天保留)  
    RETURN QUERY
    SELECT 
        'failed_tasks'::VARCHAR(50),
        (SELECT COUNT(*)::INTEGER FROM tasks WHERE status = 'failed') as current_count,
        (SELECT COUNT(*)::INTEGER 
         FROM tasks 
         WHERE status = 'failed' 
           AND updated_at IS NOT NULL
           AND updated_at < CURRENT_TIMESTAMP - INTERVAL '7 days') as to_be_cleaned,
        '保留7天，之后删除'::TEXT as retention_policy,
        (SELECT COUNT(*)::INTEGER 
         FROM tasks 
         WHERE status = 'failed' 
           AND updated_at < CURRENT_TIMESTAMP - INTERVAL '7 days') * 0.001 as estimated_space_saved_mb;

    -- 孤儿分析记录 (1小时保留)
    RETURN QUERY
    SELECT 
        'orphan_analyses'::VARCHAR(50),
        (SELECT COUNT(*)::INTEGER FROM analyses) as current_count,
        (SELECT COUNT(*)::INTEGER 
         FROM analyses a
         LEFT JOIN tasks t ON a.task_id = t.id
         WHERE t.id IS NULL
           AND a.created_at < CURRENT_TIMESTAMP - INTERVAL '1 hour') as to_be_cleaned,
        '孤儿记录保留1小时'::TEXT as retention_policy,
        (SELECT COUNT(*)::INTEGER 
         FROM analyses a
         LEFT JOIN tasks t ON a.task_id = t.id
         WHERE t.id IS NULL
           AND a.created_at < CURRENT_TIMESTAMP - INTERVAL '1 hour') * 0.01 as estimated_space_saved_mb;

    -- 过期社区缓存 (TTL驱动)
    RETURN QUERY
    SELECT 
        'expired_cache'::VARCHAR(50),
        (SELECT COUNT(*)::INTEGER FROM community_cache) as current_count,
        (SELECT COUNT(*)::INTEGER 
         FROM community_cache 
         WHERE last_crawled_at IS NOT NULL
           AND ttl_seconds IS NOT NULL
           AND ttl_seconds > 0
           AND (last_crawled_at + INTERVAL '1 second' * ttl_seconds) < CURRENT_TIMESTAMP) as to_be_cleaned,
        '基于TTL自动过期'::TEXT as retention_policy,
        (SELECT COUNT(*)::INTEGER 
         FROM community_cache 
         WHERE last_crawled_at IS NOT NULL
           AND ttl_seconds IS NOT NULL
           AND (last_crawled_at + INTERVAL '1 second' * ttl_seconds) < CURRENT_TIMESTAMP) * 0.005 as estimated_space_saved_mb;

    -- 非活跃用户 (365天保留，软删除)
    RETURN QUERY
    SELECT 
        'inactive_users'::VARCHAR(50),
        (SELECT COUNT(*)::INTEGER FROM users WHERE is_active = true) as current_count,
        (SELECT COUNT(*)::INTEGER 
         FROM users 
         WHERE is_active = true
           AND (last_login_at IS NULL OR last_login_at < CURRENT_TIMESTAMP - INTERVAL '365 days')
           AND created_at < CURRENT_TIMESTAMP - INTERVAL '372 days') as to_be_cleaned,
        '365天无活动，软删除'::TEXT as retention_policy,
        0::NUMERIC as estimated_space_saved_mb; -- 软删除不节省空间
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 2. 紧急清理函数 - 更激进的清理策略
-- ============================================================================

CREATE OR REPLACE FUNCTION execute_emergency_cleanup()
RETURNS JSONB AS $$
DECLARE
    result JSONB;
BEGIN
    -- 使用更激进的清理策略
    SELECT execute_data_cleanup(
        15,    -- 完成任务保留15天
        3,     -- 失败任务保留3天  
        0.5,   -- 孤儿分析保留30分钟
        180,   -- 非活跃用户保留180天
        false  -- 不是试运行
    ) INTO result;
    
    -- 添加紧急清理标记
    result := result || jsonb_build_object('cleanup_type', 'emergency');
    
    RAISE WARNING '已执行紧急数据清理: %', result;
    
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 3. 数据库维护相关函数
-- ============================================================================

-- 获取数据库大小信息
CREATE OR REPLACE FUNCTION get_database_size_info()
RETURNS TABLE(
    table_name TEXT,
    size_mb NUMERIC,
    row_count BIGINT,
    avg_row_size_bytes NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        schemaname||'.'||tablename as table_name,
        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))::NUMERIC as size_mb,
        n_tup_ins - n_tup_del as row_count,
        CASE 
            WHEN n_tup_ins - n_tup_del > 0 
            THEN pg_total_relation_size(schemaname||'.'||tablename)::NUMERIC / (n_tup_ins - n_tup_del)
            ELSE 0 
        END as avg_row_size_bytes
    FROM pg_stat_user_tables 
    WHERE schemaname = 'public'
    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
END;
$$ LANGUAGE plpgsql;

-- 获取数据库清理建议
CREATE OR REPLACE FUNCTION get_cleanup_recommendations()
RETURNS TABLE(
    recommendation_type TEXT,
    priority INTEGER,
    description TEXT,
    estimated_impact TEXT,
    sql_command TEXT
) AS $$
BEGIN
    -- 基于当前数据库状态提供清理建议
    
    -- 检查是否有大量完成的任务
    IF (SELECT COUNT(*) FROM tasks WHERE status = 'completed' 
        AND completed_at < CURRENT_TIMESTAMP - INTERVAL '30 days') > 1000 THEN
        RETURN QUERY VALUES (
            '清理完成任务'::TEXT,
            1::INTEGER,
            '发现大量超过30天的已完成任务'::TEXT,
            '可节省空间，提升查询性能'::TEXT,
            'SELECT cleanup_completed_tasks(CURRENT_TIMESTAMP - INTERVAL ''30 days'');'::TEXT
        );
    END IF;

    -- 检查是否有大量失败的任务
    IF (SELECT COUNT(*) FROM tasks WHERE status = 'failed' 
        AND updated_at < CURRENT_TIMESTAMP - INTERVAL '7 days') > 500 THEN
        RETURN QUERY VALUES (
            '清理失败任务'::TEXT,
            2::INTEGER,
            '发现大量超过7天的失败任务'::TEXT,
            '可节省空间'::TEXT,
            'SELECT cleanup_failed_tasks(CURRENT_TIMESTAMP - INTERVAL ''7 days'');'::TEXT
        );
    END IF;

    -- 检查孤儿分析记录
    IF (SELECT COUNT(*) FROM analyses a LEFT JOIN tasks t ON a.task_id = t.id WHERE t.id IS NULL) > 100 THEN
        RETURN QUERY VALUES (
            '清理孤儿分析'::TEXT,
            3::INTEGER,
            '发现大量没有对应任务的分析记录'::TEXT,
            '清理数据不一致问题'::TEXT,
            'SELECT cleanup_orphan_analyses(CURRENT_TIMESTAMP - INTERVAL ''1 hour'');'::TEXT
        );
    END IF;

    -- 检查过期缓存
    IF (SELECT COUNT(*) FROM community_cache 
        WHERE last_crawled_at + INTERVAL '1 second' * ttl_seconds < CURRENT_TIMESTAMP) > 50 THEN
        RETURN QUERY VALUES (
            '清理过期缓存'::TEXT,
            4::INTEGER,
            '发现大量过期的社区缓存'::TEXT,
            '节省缓存空间'::TEXT,
            'SELECT cleanup_expired_community_cache();'::TEXT
        );
    END IF;

    -- 如果没有发现需要清理的数据
    IF NOT FOUND THEN
        RETURN QUERY VALUES (
            '无需清理'::TEXT,
            0::INTEGER,
            '数据库状态良好，暂无需要清理的数据'::TEXT,
            '继续监控'::TEXT,
            '-- 无需执行'::TEXT
        );
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 4. 清理历史和统计查询
-- ============================================================================

-- 查看最近的清理历史
CREATE OR REPLACE VIEW recent_cleanup_history AS
SELECT 
    executed_at,
    total_records_cleaned,
    breakdown->>'completed_tasks' as completed_tasks_cleaned,
    breakdown->>'failed_tasks' as failed_tasks_cleaned,
    breakdown->>'orphan_analyses' as orphan_analyses_cleaned,
    breakdown->>'expired_cache' as expired_cache_cleaned,
    breakdown->>'inactive_users' as inactive_users_cleaned,
    duration_seconds,
    success,
    CASE 
        WHEN success THEN '✅ 成功'
        ELSE '❌ 失败: ' || COALESCE(error_message, '未知错误')
    END as status
FROM cleanup_logs 
ORDER BY executed_at DESC 
LIMIT 20;

-- 清理效果趋势分析
CREATE OR REPLACE VIEW cleanup_trends AS
SELECT 
    DATE_TRUNC('week', executed_at) as week,
    COUNT(*) as cleanup_runs,
    AVG(total_records_cleaned) as avg_records_per_run,
    SUM(total_records_cleaned) as total_records_cleaned,
    AVG(duration_seconds) as avg_duration_seconds,
    COUNT(CASE WHEN success THEN 1 END)::FLOAT / COUNT(*) * 100 as success_rate_percent
FROM cleanup_logs 
WHERE executed_at >= CURRENT_TIMESTAMP - INTERVAL '12 weeks'
GROUP BY DATE_TRUNC('week', executed_at)
ORDER BY week DESC;

-- ============================================================================
-- 5. 便捷的维护命令
-- ============================================================================

-- 查看数据库当前状态
\echo '=== 数据库清理状态检查 ==='
SELECT 'Database Size Information' as info_type;
SELECT * FROM get_database_size_info();

\echo ''
SELECT 'Cleanup Preview' as info_type;  
SELECT * FROM cleanup_preview();

\echo ''
SELECT 'Cleanup Recommendations' as info_type;
SELECT * FROM get_cleanup_recommendations();

\echo ''
SELECT 'Recent Cleanup History' as info_type;
SELECT * FROM recent_cleanup_history;

\echo ''
\echo '=== 可用的清理命令 ==='
\echo '1. 预览清理效果: SELECT * FROM cleanup_preview();'
\echo '2. 执行标准清理: SELECT * FROM execute_data_cleanup();'
\echo '3. 执行紧急清理: SELECT * FROM execute_emergency_cleanup();'
\echo '4. 获取清理建议: SELECT * FROM get_cleanup_recommendations();'
\echo '5. 查看清理历史: SELECT * FROM recent_cleanup_history;'
\echo '6. 查看清理趋势: SELECT * FROM cleanup_trends;'
\echo ''
\echo '=== 手动清理命令 ==='
\echo '清理完成任务(30天): SELECT cleanup_completed_tasks(CURRENT_TIMESTAMP - INTERVAL ''30 days'');'
\echo '清理失败任务(7天):  SELECT cleanup_failed_tasks(CURRENT_TIMESTAMP - INTERVAL ''7 days'');'
\echo '清理孤儿分析(1小时): SELECT cleanup_orphan_analyses(CURRENT_TIMESTAMP - INTERVAL ''1 hour'');'
\echo '清理过期缓存:        SELECT cleanup_expired_community_cache();'
\echo '软删除非活跃用户:    SELECT cleanup_inactive_users(CURRENT_TIMESTAMP - INTERVAL ''365 days'');'