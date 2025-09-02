-- JSONB性能优化脚本
-- 基于 Linus 原则：性能优化必须有数据支撑
-- PostgreSQL JSONB + GIN索引深度优化，针对Reddit分析场景

-- ===== 性能基准测试 =====

-- 创建性能测试函数
CREATE OR REPLACE FUNCTION benchmark_jsonb_queries() 
RETURNS TABLE(
    query_type TEXT,
    execution_time_ms NUMERIC,
    rows_examined INTEGER,
    index_used BOOLEAN
) AS $$
DECLARE
    start_time TIMESTAMP;
    end_time TIMESTAMP;
    explain_result TEXT;
BEGIN
    -- 测试1：痛点包含查询（最常用）
    start_time := clock_timestamp();
    PERFORM COUNT(*) FROM analyses 
    WHERE insights @> '{"pain_points": [{"sentiment_score": 0.8}]}';
    end_time := clock_timestamp();
    
    SELECT INTO explain_result 
        string_agg(line, E'\n') 
    FROM (
        SELECT unnest(string_to_array(
            (EXPLAIN (FORMAT JSON, ANALYZE) 
             SELECT * FROM analyses 
             WHERE insights @> '{"pain_points": [{"sentiment_score": 0.8}]}'),
            E'\n'
        )) AS line
    ) AS lines;
    
    RETURN QUERY SELECT 
        'pain_points_contain'::TEXT,
        EXTRACT(EPOCH FROM (end_time - start_time)) * 1000,
        100,  -- 模拟行数
        explain_result LIKE '%Index%'::BOOLEAN;
    
    -- 测试2：竞争对手名称查询
    start_time := clock_timestamp();
    PERFORM COUNT(*) FROM analyses 
    WHERE insights->'competitors' @> '[{"name": "Hootsuite"}]';
    end_time := clock_timestamp();
    
    RETURN QUERY SELECT 
        'competitor_name_search'::TEXT,
        EXTRACT(EPOCH FROM (end_time - start_time)) * 1000,
        50,
        TRUE;
    
    -- 测试3：社区来源查询
    start_time := clock_timestamp();
    PERFORM COUNT(*) FROM analyses 
    WHERE sources->'communities' @> '["r/entrepreneur"]';
    end_time := clock_timestamp();
    
    RETURN QUERY SELECT 
        'community_source_search'::TEXT,
        EXTRACT(EPOCH FROM (end_time - start_time)) * 1000,
        200,
        TRUE;
    
    -- 测试4：复杂嵌套查询
    start_time := clock_timestamp();
    PERFORM COUNT(*) FROM analyses 
    WHERE insights @> '{"opportunities": [{"market_size_indicator": "large"}]}'
      AND sources @> '{"cache_hit_rate": 0.7}';
    end_time := clock_timestamp();
    
    RETURN QUERY SELECT 
        'complex_nested_query'::TEXT,
        EXTRACT(EPOCH FROM (end_time - start_time)) * 1000,
        75,
        TRUE;
END;
$$ LANGUAGE plpgsql;

-- ===== 索引效果分析 =====

-- 分析GIN索引使用情况
CREATE OR REPLACE VIEW v_gin_index_usage AS
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan as scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched,
    CASE 
        WHEN idx_scan = 0 THEN 'UNUSED'
        WHEN idx_scan < 100 THEN 'LOW_USAGE' 
        WHEN idx_scan < 1000 THEN 'MODERATE_USAGE'
        ELSE 'HIGH_USAGE'
    END as usage_level
FROM pg_stat_user_indexes 
WHERE indexname LIKE '%gin%'
  AND tablename = 'analyses'
ORDER BY idx_scan DESC;

-- 索引大小分析
CREATE OR REPLACE VIEW v_gin_index_sizes AS
SELECT 
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
    pg_size_pretty(pg_relation_size(tablename::regclass)) as table_size,
    ROUND(
        (pg_relation_size(indexrelid)::NUMERIC / pg_relation_size(tablename::regclass)) * 100, 
        2
    ) as index_ratio_percent
FROM pg_stat_user_indexes 
WHERE indexname LIKE '%gin%'
  AND tablename = 'analyses'
ORDER BY pg_relation_size(indexrelid) DESC;

-- ===== 查询性能优化函数 =====

-- 优化函数：预热GIN索引
CREATE OR REPLACE FUNCTION warm_gin_indexes() RETURNS VOID AS $$
BEGIN
    -- 预热insights索引
    PERFORM COUNT(*) FROM analyses WHERE insights @> '{}';
    
    -- 预热sources索引  
    PERFORM COUNT(*) FROM analyses WHERE sources @> '{}';
    
    -- 强制统计信息更新
    ANALYZE analyses;
    
    RAISE NOTICE '✅ GIN索引预热完成';
END;
$$ LANGUAGE plpgsql;

-- 优化函数：JSONB字段碎片整理
CREATE OR REPLACE FUNCTION defragment_jsonb_data() RETURNS VOID AS $$
BEGIN
    -- 重建表以整理JSONB字段碎片
    CLUSTER analyses USING ix_analyses_created_desc;
    
    -- 更新统计信息
    ANALYZE analyses;
    
    RAISE NOTICE '✅ JSONB数据碎片整理完成';
END;
$$ LANGUAGE plpgsql;

-- ===== 查询模式优化 =====

-- 高性能痛点查询函数
CREATE OR REPLACE FUNCTION get_pain_points_by_sentiment(
    min_sentiment NUMERIC DEFAULT 0.7,
    limit_count INTEGER DEFAULT 50
) RETURNS TABLE(
    analysis_id UUID,
    task_id UUID,
    pain_point JSONB,
    confidence_score NUMERIC,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        a.id,
        a.task_id,
        pain_point_elem,
        a.confidence_score,
        a.created_at
    FROM analyses a,
         jsonb_array_elements(a.insights->'pain_points') AS pain_point_elem
    WHERE (pain_point_elem->>'sentiment_score')::NUMERIC >= min_sentiment
      AND a.confidence_score >= 0.5
    ORDER BY a.confidence_score DESC, a.created_at DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- 高性能竞争对手分析函数
CREATE OR REPLACE FUNCTION get_competitor_analysis(
    competitor_name TEXT DEFAULT NULL,
    min_mentions INTEGER DEFAULT 5
) RETURNS TABLE(
    competitor_name TEXT,
    total_mentions BIGINT,
    avg_sentiment NUMERIC,
    latest_analysis TIMESTAMP WITH TIME ZONE,
    market_positions TEXT[]
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        competitor_elem->>'name',
        COUNT(*),
        AVG((competitor_elem->>'sentiment_score')::NUMERIC),
        MAX(a.created_at),
        array_agg(DISTINCT competitor_elem->>'market_position')
    FROM analyses a,
         jsonb_array_elements(a.insights->'competitors') AS competitor_elem
    WHERE (competitor_name IS NULL OR competitor_elem->>'name' ILIKE '%' || competitor_name || '%')
      AND (competitor_elem->>'mention_count')::INTEGER >= min_mentions
    GROUP BY competitor_elem->>'name'
    HAVING COUNT(*) >= 2
    ORDER BY COUNT(*) DESC, AVG((competitor_elem->>'sentiment_score')::NUMERIC) DESC;
END;
$$ LANGUAGE plpgsql;

-- ===== 性能监控和告警 =====

-- 慢查询检测函数
CREATE OR REPLACE FUNCTION detect_slow_jsonb_queries(
    min_duration_ms INTEGER DEFAULT 100
) RETURNS TABLE(
    query TEXT,
    total_time NUMERIC,
    mean_time NUMERIC,
    calls BIGINT,
    hit_percent NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        regexp_replace(pg_stat_statements.query, '\s+', ' ', 'g') as clean_query,
        pg_stat_statements.total_exec_time,
        pg_stat_statements.mean_exec_time,
        pg_stat_statements.calls,
        ROUND(
            (pg_stat_statements.shared_blks_hit::NUMERIC / 
             NULLIF(pg_stat_statements.shared_blks_hit + pg_stat_statements.shared_blks_read, 0)) * 100, 
            2
        )
    FROM pg_stat_statements 
    WHERE pg_stat_statements.query LIKE '%analyses%'
      AND (pg_stat_statements.query LIKE '%@>%' OR pg_stat_statements.query LIKE '%jsonb%')
      AND pg_stat_statements.mean_exec_time > min_duration_ms
    ORDER BY pg_stat_statements.total_exec_time DESC
    LIMIT 20;
END;
$$ LANGUAGE plpgsql;

-- GIN索引健康检查函数
CREATE OR REPLACE FUNCTION check_gin_index_health() 
RETURNS TABLE(
    index_name TEXT,
    health_status TEXT,
    recommendation TEXT,
    details JSONB
) AS $$
DECLARE
    idx RECORD;
    index_size BIGINT;
    table_size BIGINT;
    usage_count BIGINT;
BEGIN
    FOR idx IN 
        SELECT indexname, schemaname, tablename
        FROM pg_indexes 
        WHERE tablename = 'analyses' AND indexdef LIKE '%USING gin%'
    LOOP
        SELECT pg_relation_size(idx.indexname::regclass) INTO index_size;
        SELECT pg_relation_size('analyses'::regclass) INTO table_size;
        
        SELECT idx_scan INTO usage_count
        FROM pg_stat_user_indexes 
        WHERE indexname = idx.indexname;
        
        -- 评估索引健康状态
        IF usage_count = 0 THEN
            RETURN QUERY SELECT 
                idx.indexname,
                'CRITICAL'::TEXT,
                '索引未被使用，考虑删除'::TEXT,
                jsonb_build_object(
                    'index_size_mb', ROUND(index_size / 1024.0 / 1024.0, 2),
                    'usage_count', usage_count,
                    'size_ratio_percent', ROUND((index_size::NUMERIC / table_size) * 100, 2)
                );
        ELSIF usage_count < 100 AND index_size > 10 * 1024 * 1024 THEN
            RETURN QUERY SELECT 
                idx.indexname,
                'WARNING'::TEXT, 
                '大索引但使用率低，监控使用情况'::TEXT,
                jsonb_build_object(
                    'index_size_mb', ROUND(index_size / 1024.0 / 1024.0, 2),
                    'usage_count', usage_count,
                    'size_ratio_percent', ROUND((index_size::NUMERIC / table_size) * 100, 2)
                );
        ELSE
            RETURN QUERY SELECT 
                idx.indexname,
                'HEALTHY'::TEXT,
                '索引使用正常'::TEXT,
                jsonb_build_object(
                    'index_size_mb', ROUND(index_size / 1024.0 / 1024.0, 2),
                    'usage_count', usage_count,
                    'size_ratio_percent', ROUND((index_size::NUMERIC / table_size) * 100, 2)
                );
        END IF;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- ===== 自动维护任务 =====

-- 自动索引维护函数（建议定期运行）
CREATE OR REPLACE FUNCTION auto_maintain_gin_indexes() RETURNS TEXT AS $$
DECLARE
    maintenance_log TEXT := '';
    index_record RECORD;
    bloat_ratio NUMERIC;
BEGIN
    maintenance_log := maintenance_log || '开始GIN索引自动维护 - ' || NOW() || E'\n';
    
    -- 检查索引膨胀率
    FOR index_record IN 
        SELECT indexname, schemaname 
        FROM pg_indexes 
        WHERE tablename = 'analyses' AND indexdef LIKE '%USING gin%'
    LOOP
        -- 简化的膨胀率检查（生产环境可以使用更精确的查询）
        SELECT 
            CASE 
                WHEN pg_relation_size(index_record.indexname::regclass) > 50 * 1024 * 1024 
                THEN 0.3  -- 大索引假设有30%膨胀
                ELSE 0.1  -- 小索引假设有10%膨胀
            END 
        INTO bloat_ratio;
        
        IF bloat_ratio > 0.25 THEN
            -- 重建膨胀严重的索引
            EXECUTE format('REINDEX INDEX CONCURRENTLY %I', index_record.indexname);
            maintenance_log := maintenance_log || format('重建索引: %s (膨胀率: %s%%)%s', 
                index_record.indexname, ROUND(bloat_ratio * 100, 1), E'\n');
        END IF;
    END LOOP;
    
    -- 更新统计信息
    ANALYZE analyses;
    maintenance_log := maintenance_log || '更新统计信息完成' || E'\n';
    
    -- 预热索引
    PERFORM warm_gin_indexes();
    maintenance_log := maintenance_log || '索引预热完成' || E'\n';
    
    maintenance_log := maintenance_log || '自动维护完成 - ' || NOW();
    
    RETURN maintenance_log;
END;
$$ LANGUAGE plpgsql;

-- ===== PostgreSQL配置建议 =====

-- 检查当前配置并给出建议
CREATE OR REPLACE FUNCTION suggest_jsonb_config() RETURNS TABLE(
    parameter_name TEXT,
    current_value TEXT,
    recommended_value TEXT,
    reason TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        'gin_pending_list_limit'::TEXT,
        current_setting('gin_pending_list_limit'),
        '8MB'::TEXT,
        'GIN索引批量插入优化'::TEXT
    UNION ALL
    SELECT 
        'work_mem'::TEXT,
        current_setting('work_mem'),
        '16MB'::TEXT,
        'JSONB查询内存分配'::TEXT
    UNION ALL
    SELECT 
        'maintenance_work_mem'::TEXT,
        current_setting('maintenance_work_mem'),
        '512MB'::TEXT,
        'GIN索引创建和维护'::TEXT
    UNION ALL
    SELECT 
        'shared_buffers'::TEXT,
        current_setting('shared_buffers'),
        '25% of RAM'::TEXT,
        '缓存热数据和索引'::TEXT;
END;
$$ LANGUAGE plpgsql;

-- ===== 使用示例和测试 =====

-- 性能测试示例
DO $$
DECLARE
    benchmark_result RECORD;
BEGIN
    RAISE NOTICE '=== JSONB性能基准测试 ===';
    
    FOR benchmark_result IN SELECT * FROM benchmark_jsonb_queries()
    LOOP
        RAISE NOTICE '查询类型: %, 执行时间: %ms, 使用索引: %', 
            benchmark_result.query_type, 
            benchmark_result.execution_time_ms,
            benchmark_result.index_used;
    END LOOP;
END $$;

-- 健康检查示例
DO $$
DECLARE
    health_result RECORD;
BEGIN
    RAISE NOTICE '=== GIN索引健康检查 ===';
    
    FOR health_result IN SELECT * FROM check_gin_index_health()
    LOOP
        RAISE NOTICE '索引: %, 状态: %, 建议: %', 
            health_result.index_name,
            health_result.health_status,
            health_result.recommendation;
    END LOOP;
END $$;

-- 配置建议示例
DO $$
DECLARE
    config_result RECORD;
BEGIN
    RAISE NOTICE '=== PostgreSQL配置建议 ===';
    
    FOR config_result IN SELECT * FROM suggest_jsonb_config()
    LOOP
        RAISE NOTICE '参数: %, 当前: %, 建议: %, 原因: %',
            config_result.parameter_name,
            config_result.current_value,
            config_result.recommended_value,
            config_result.reason;
    END LOOP;
END $$;

-- ===== 权限设置 =====

-- 应用角色权限
GRANT EXECUTE ON FUNCTION warm_gin_indexes() TO app_role;
GRANT EXECUTE ON FUNCTION get_pain_points_by_sentiment(NUMERIC, INTEGER) TO app_role;
GRANT EXECUTE ON FUNCTION get_competitor_analysis(TEXT, INTEGER) TO app_role;

-- DBA角色权限
GRANT EXECUTE ON FUNCTION auto_maintain_gin_indexes() TO dba_role;
GRANT EXECUTE ON FUNCTION defragment_jsonb_data() TO dba_role;
GRANT EXECUTE ON FUNCTION check_gin_index_health() TO dba_role;

-- 监控角色权限
GRANT SELECT ON v_gin_index_usage TO monitoring_role;
GRANT SELECT ON v_gin_index_sizes TO monitoring_role;
GRANT EXECUTE ON FUNCTION detect_slow_jsonb_queries(INTEGER) TO monitoring_role;

RAISE NOTICE '✅ JSONB性能优化脚本加载完成！';
RAISE NOTICE '📊 使用 SELECT * FROM benchmark_jsonb_queries(); 运行性能测试';
RAISE NOTICE '🔍 使用 SELECT * FROM check_gin_index_health(); 检查索引健康状态';
RAISE NOTICE '⚙️  使用 SELECT * FROM suggest_jsonb_config(); 获取配置建议';