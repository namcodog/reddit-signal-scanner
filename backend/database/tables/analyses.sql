-- analyses表：存储Reddit分析结果
-- 基于 Linus 原则：数据结构决定代码复杂度
-- 一对一关系设计，JSONB + GIN索引优化，Schema验证确保数据质量

-- ===== 依赖检查 =====
-- 确保依赖的Schema验证函数已存在
DO $$
BEGIN
    -- 检查validate_insights_schema函数
    IF NOT EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'validate_insights_schema') THEN
        RAISE EXCEPTION 'validate_insights_schema函数不存在，请先执行003_schema_validation.sql';
    END IF;
    
    -- 检查validate_sources_schema函数  
    IF NOT EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'validate_sources_schema') THEN
        RAISE EXCEPTION 'validate_sources_schema函数不存在，请先执行003_schema_validation.sql';
    END IF;
    
    -- 检查tasks表是否存在
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'tasks') THEN
        RAISE EXCEPTION 'tasks表不存在，请先执行002_create_tasks.sql';
    END IF;
END $$;

-- ===== 创建analyses表 =====

CREATE TABLE IF NOT EXISTS analyses (
    -- 主键：UUID，保持系统一致性
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 外键：一对一关系，每个任务只有一个分析结果
    task_id UUID NOT NULL UNIQUE,
    
    -- 分析洞察：JSONB存储，支持复杂查询
    -- 结构：{"pain_points": [...], "competitors": [...], "opportunities": [...]}
    insights JSONB NOT NULL,
    
    -- 数据溯源：分析元数据和缓存信息
    -- 结构：{"communities": [...], "posts_analyzed": N, "cache_hit_rate": 0.x}
    sources JSONB NOT NULL,
    
    -- 置信度：量化分析质量 (0.00-1.00)
    confidence_score DECIMAL(3,2) NOT NULL,
    
    -- 分析版本：支持算法迭代，实现向前兼容
    analysis_version INTEGER NOT NULL DEFAULT 1,
    
    -- 审计字段：记录创建时间（不可变）
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- ===== 约束定义 =====
    
    -- 外键约束：级联删除确保数据完整性
    CONSTRAINT fk_analyses_task_id 
        FOREIGN KEY (task_id) 
        REFERENCES tasks(id) 
        ON DELETE CASCADE,
    
    -- 置信度范围约束
    CONSTRAINT ck_analyses_confidence_range 
        CHECK (confidence_score BETWEEN 0.00 AND 1.00),
    
    -- 分析版本约束
    CONSTRAINT ck_analyses_version_positive 
        CHECK (analysis_version > 0),
    
    -- Schema验证约束：确保insights结构正确
    CONSTRAINT ck_analyses_insights_schema 
        CHECK (validate_insights_schema(insights)),
    
    -- Schema验证约束：确保sources结构正确  
    CONSTRAINT ck_analyses_sources_schema 
        CHECK (validate_sources_schema(sources))
);

-- ===== 索引优化 =====

-- GIN索引：insights字段的包含查询优化
-- 使用jsonb_path_ops操作符类，索引更小，查询更快
CREATE INDEX IF NOT EXISTS ix_analyses_insights_gin 
    ON analyses USING GIN(insights jsonb_path_ops);

-- GIN索引：sources字段的复杂查询支持  
-- 使用默认操作符类，支持多种查询模式
CREATE INDEX IF NOT EXISTS ix_analyses_sources_gin 
    ON analyses USING GIN(sources);

-- B-tree索引：置信度降序查询优化
CREATE INDEX IF NOT EXISTS ix_analyses_confidence_desc 
    ON analyses (confidence_score DESC);

-- B-tree索引：创建时间降序查询优化
CREATE INDEX IF NOT EXISTS ix_analyses_created_desc 
    ON analyses (created_at DESC);

-- 复合索引：关联查询优化（task_id + created_at）
CREATE INDEX IF NOT EXISTS ix_analyses_task_created 
    ON analyses (task_id, created_at DESC);

-- 复合索引：置信度和时间组合查询
CREATE INDEX IF NOT EXISTS ix_analyses_confidence_created 
    ON analyses (confidence_score DESC, created_at DESC);

-- 复合索引：版本和时间查询（支持算法迭代分析）
CREATE INDEX IF NOT EXISTS ix_analyses_version_created 
    ON analyses (analysis_version, created_at DESC);

-- ===== 触发器：自动状态同步 =====

-- 函数：插入分析结果时自动更新任务状态
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
    
    -- 记录日志：分析完成事件
    INSERT INTO audit_logs (table_name, operation, record_id, details)
    VALUES (
        'analyses', 
        'task_completed',
        NEW.id,
        jsonb_build_object(
            'task_id', NEW.task_id,
            'confidence_score', NEW.confidence_score,
            'analysis_version', NEW.analysis_version
        )
    );
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 创建触发器
CREATE TRIGGER tr_analyses_completion
    AFTER INSERT ON analyses
    FOR EACH ROW
    EXECUTE FUNCTION update_task_completion_status();

-- ===== 行级安全策略 (RLS) =====

-- 启用行级安全
ALTER TABLE analyses ENABLE ROW LEVEL SECURITY;

-- 策略：用户只能访问自己的分析结果
CREATE POLICY policy_analyses_tenant_isolation ON analyses
    USING (
        task_id IN (
            SELECT id FROM tasks WHERE user_id = current_setting('app.current_user_id')::UUID
        )
    );

-- ===== 存储优化配置 =====

-- JSONB字段使用EXTENDED存储策略，启用压缩
ALTER TABLE analyses ALTER COLUMN insights SET STORAGE EXTENDED;
ALTER TABLE analyses ALTER COLUMN sources SET STORAGE EXTENDED;

-- ===== 统计信息配置 =====

-- 为JSONB字段配置统计信息收集
ALTER TABLE analyses ALTER COLUMN insights SET STATISTICS 1000;
ALTER TABLE analyses ALTER COLUMN sources SET STATISTICS 1000;

-- ===== 分区策略（未来扩展）=====

-- 注释：为大数据量准备的分区策略
-- 按月分区可以提高查询性能和维护效率
/*
-- 示例：按月分区（当数据量 > 1000万时启用）
CREATE TABLE analyses_y2025m01 PARTITION OF analyses
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
    
CREATE TABLE analyses_y2025m02 PARTITION OF analyses  
    FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');
*/

-- ===== 性能监控视图 =====

-- 视图：分析结果性能统计
CREATE OR REPLACE VIEW v_analyses_stats AS
SELECT 
    DATE_TRUNC('day', created_at) as analysis_date,
    COUNT(*) as total_analyses,
    AVG(confidence_score) as avg_confidence,
    MIN(confidence_score) as min_confidence,
    MAX(confidence_score) as max_confidence,
    -- JSONB字段大小统计
    AVG(pg_column_size(insights)) as avg_insights_size,
    AVG(pg_column_size(sources)) as avg_sources_size,
    -- 分析版本分布
    jsonb_object_agg(analysis_version, version_count) as version_distribution
FROM analyses
CROSS JOIN LATERAL (
    SELECT analysis_version, COUNT(*) as version_count
    FROM analyses a2 
    WHERE DATE_TRUNC('day', a2.created_at) = DATE_TRUNC('day', analyses.created_at)
    GROUP BY analysis_version
) version_stats
GROUP BY DATE_TRUNC('day', created_at)
ORDER BY analysis_date DESC;

-- ===== 维护函数 =====

-- 函数：清理过期的低置信度分析结果
CREATE OR REPLACE FUNCTION cleanup_low_confidence_analyses(
    confidence_threshold DECIMAL DEFAULT 0.3,
    days_old INTEGER DEFAULT 90
) RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- 删除指定天数前且置信度低于阈值的分析结果
    DELETE FROM analyses 
    WHERE confidence_score < confidence_threshold
      AND created_at < CURRENT_TIMESTAMP - INTERVAL '%s days' % days_old;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    -- 记录清理操作
    INSERT INTO audit_logs (table_name, operation, details)
    VALUES (
        'analyses',
        'cleanup_low_confidence', 
        jsonb_build_object(
            'deleted_count', deleted_count,
            'confidence_threshold', confidence_threshold,
            'days_old', days_old
        )
    );
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- 函数：重建GIN索引（维护工具）
CREATE OR REPLACE FUNCTION rebuild_analyses_gin_indexes() RETURNS VOID AS $$
BEGIN
    -- 并发重建索引，避免阻塞业务
    REINDEX INDEX CONCURRENTLY ix_analyses_insights_gin;
    REINDEX INDEX CONCURRENTLY ix_analyses_sources_gin;
    
    -- 记录维护操作
    INSERT INTO audit_logs (table_name, operation, details)
    VALUES (
        'analyses',
        'indexes_rebuilt',
        jsonb_build_object('indexes', ['ix_analyses_insights_gin', 'ix_analyses_sources_gin'])
    );
END;
$$ LANGUAGE plpgsql;

-- ===== 权限设置 =====

-- 应用角色权限
GRANT SELECT, INSERT, UPDATE, DELETE ON analyses TO app_role;
GRANT USAGE ON SEQUENCE analyses_id_seq TO app_role;

-- 只读角色权限（分析师、报告）
GRANT SELECT ON analyses TO readonly_role;
GRANT SELECT ON v_analyses_stats TO readonly_role;

-- ===== 初始化检查 =====

-- 验证表创建成功和索引状态
DO $$
DECLARE
    table_count INTEGER;
    index_count INTEGER;
BEGIN
    -- 检查表是否创建成功
    SELECT COUNT(*) INTO table_count 
    FROM information_schema.tables 
    WHERE table_name = 'analyses';
    
    IF table_count = 0 THEN
        RAISE EXCEPTION 'analyses表创建失败';
    END IF;
    
    -- 检查GIN索引是否创建成功
    SELECT COUNT(*) INTO index_count
    FROM pg_indexes 
    WHERE tablename = 'analyses' 
      AND indexdef LIKE '%USING gin%';
    
    IF index_count < 2 THEN
        RAISE WARNING 'GIN索引创建不完整，实际: %, 预期: 2', index_count;
    END IF;
    
    RAISE NOTICE '✅ analyses表和索引创建成功！';
    RAISE NOTICE '📊 表: %, GIN索引: %', table_count, index_count;
END $$;