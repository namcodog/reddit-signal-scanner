-- reports表：HTML报告存储 - Linus式简单设计
-- 原则：数据库存储数据，应用处理逻辑

-- ===== 依赖检查 =====
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'analyses') THEN
        RAISE EXCEPTION 'analyses表不存在，请先执行004_create_analyses.sql';
    END IF;
END $$;

-- ===== 创建reports表 =====

CREATE TABLE IF NOT EXISTS reports (
    -- 主键：UUID，保持系统一致性
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 外键：一对多关系（移除UNIQUE约束）
    analysis_id UUID NOT NULL,
    
    -- HTML内容：核心存储
    html_content TEXT NOT NULL,
    
    -- 状态：简单状态管理
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    
    -- 创建时间：简单审计
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- ===== 约束定义 =====
    
    -- 外键约束：级联删除
    CONSTRAINT fk_reports_analysis_id 
        FOREIGN KEY (analysis_id) 
        REFERENCES analyses(id) 
        ON DELETE CASCADE,
    
    -- HTML内容大小限制（10MB）
    CONSTRAINT ck_reports_html_size 
        CHECK (length(html_content) <= 10485760),
    
    -- 状态枚举约束
    CONSTRAINT ck_reports_status 
        CHECK (status IN ('active', 'deprecated', 'draft'))
);

-- ===== 索引优化 =====

-- 核心查询：活跃报告查找
CREATE INDEX IF NOT EXISTS ix_reports_analysis_active 
    ON reports (analysis_id) WHERE status = 'active';

-- 时间排序：最新报告优先
CREATE INDEX IF NOT EXISTS ix_reports_created_desc 
    ON reports (created_at DESC);

-- ===== 权限设置 =====

GRANT SELECT, INSERT, UPDATE, DELETE ON reports TO app_role;
GRANT USAGE ON SEQUENCE reports_id_seq TO app_role;
GRANT SELECT ON reports TO readonly_role;

-- ===== 初始化检查 =====

DO $$
DECLARE
    table_count INTEGER;
    index_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count 
    FROM information_schema.tables 
    WHERE table_name = 'reports';
    
    IF table_count = 0 THEN
        RAISE EXCEPTION 'reports表创建失败';
    END IF;
    
    SELECT COUNT(*) INTO index_count
    FROM pg_indexes 
    WHERE tablename = 'reports';
    
    IF index_count < 2 THEN
        RAISE WARNING '索引创建不完整，实际: %, 预期: 2', index_count;
    END IF;
    
    RAISE NOTICE '✅ reports表创建成功！';
    RAISE NOTICE '📊 表: %, 索引: %', table_count, index_count;
END $$;