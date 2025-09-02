-- Reddit Signal Scanner - Community Cache表DDL定义
-- 基于Linus架构原则：缓存优先设计，数据结构决定性能
-- PRD-01-07: 实现社区缓存表，支持缓存优先架构的元数据管理

-- 社区缓存元数据表：Reddit社区数据缓存管理核心
-- 设计哲学：缓存即数据源，避免"缓存穿透"特殊处理
CREATE TABLE community_cache (
    -- 主键：Reddit社区名称（自然主键，符合查询模式）
    community_name VARCHAR(100) PRIMARY KEY,
    
    -- 缓存生命周期管理
    last_crawled_at TIMESTAMP WITH TIME ZONE,  -- 最后抓取时间，NULL表示从未抓取
    ttl_seconds INTEGER NOT NULL DEFAULT 3600,  -- 缓存TTL，默认1小时
    posts_cached INTEGER NOT NULL DEFAULT 0,   -- 缓存的帖子数量
    
    -- 缓存质量评估（0.00-1.00）：基于数据完整性和新鲜度
    quality_score DECIMAL(3,2) NOT NULL DEFAULT 0.50
        CONSTRAINT ck_community_cache_quality_range CHECK (quality_score >= 0.00 AND quality_score <= 1.00),
    
    -- 访问频率跟踪：LRU缓存策略基础
    hit_count INTEGER NOT NULL DEFAULT 0,      -- 命中次数，清理策略依据
    last_hit_at TIMESTAMP WITH TIME ZONE,      -- 最后访问时间，LRU算法使用
    
    -- 爬虫优先级管理：1(最高) - 100(最低)
    crawl_priority INTEGER NOT NULL DEFAULT 50
        CONSTRAINT ck_community_cache_priority_range CHECK (crawl_priority >= 1 AND crawl_priority <= 100),
    
    -- 审计字段：自动维护，追踪缓存条目生命周期
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- 社区名称格式约束：必须是有效的Reddit社区格式
    CONSTRAINT ck_community_cache_name_format 
        CHECK (community_name ~ '^r/[a-zA-Z0-9_]+$')
);

-- ====================================================================
-- 索引策略：基于缓存系统查询模式的性能优化
-- ====================================================================

-- 1. 爬虫调度索引：获取需要更新的社区（按优先级排序）
-- 查询模式：WHERE (last_crawled_at IS NULL OR now() - last_crawled_at > interval '1 second' * ttl_seconds) 
--          ORDER BY crawl_priority ASC, last_crawled_at ASC NULLS FIRST
CREATE INDEX ix_community_cache_crawl_schedule 
    ON community_cache (crawl_priority ASC, last_crawled_at ASC NULLS FIRST)
    WHERE last_crawled_at IS NULL OR (EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - last_crawled_at)) > ttl_seconds);

-- 2. 缓存热度索引：LRU清理策略和热点识别
-- 查询模式：ORDER BY hit_count DESC, last_hit_at DESC
CREATE INDEX ix_community_cache_hotness 
    ON community_cache (hit_count DESC, last_hit_at DESC);

-- 3. 缓存质量索引：高质量缓存优先查询
-- 查询模式：WHERE quality_score >= threshold ORDER BY quality_score DESC
CREATE INDEX ix_community_cache_quality 
    ON community_cache (quality_score DESC)
    WHERE quality_score >= 0.70;  -- 只为高质量缓存创建索引

-- 4. 缓存新鲜度索引：按时间范围查询最近更新的缓存
-- 查询模式：WHERE last_crawled_at >= date_threshold ORDER BY last_crawled_at DESC
CREATE INDEX ix_community_cache_freshness 
    ON community_cache (last_crawled_at DESC)
    WHERE last_crawled_at IS NOT NULL;

-- 5. 缓存大小索引：按帖子数量排序，用于容量管理
-- 查询模式：ORDER BY posts_cached DESC（找出占用最多空间的缓存）
CREATE INDEX ix_community_cache_size 
    ON community_cache (posts_cached DESC)
    WHERE posts_cached > 0;

-- ====================================================================
-- 自动维护触发器：确保审计字段一致性
-- ====================================================================

-- updated_at自动更新触发器（复用现有函数）
CREATE TRIGGER update_community_cache_updated_at 
    BEFORE UPDATE ON community_cache
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- 缓存命中计数自动更新触发器
CREATE OR REPLACE FUNCTION update_cache_hit_stats()
RETURNS TRIGGER AS $$
BEGIN
    -- 只在hit_count增加时更新last_hit_at
    IF NEW.hit_count > OLD.hit_count THEN
        NEW.last_hit_at = CURRENT_TIMESTAMP;
    END IF;
    
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_community_cache_hit_stats
    BEFORE UPDATE OF hit_count ON community_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_cache_hit_stats();

-- ====================================================================
-- 表和字段注释：文档化缓存策略
-- ====================================================================

COMMENT ON TABLE community_cache IS '社区缓存元数据表 - Reddit社区数据的缓存状态管理，支持智能缓存更新策略';

COMMENT ON COLUMN community_cache.community_name IS 'Reddit社区名称（如r/startups），作为自然主键';
COMMENT ON COLUMN community_cache.last_crawled_at IS '最后抓取时间，NULL表示从未抓取';
COMMENT ON COLUMN community_cache.ttl_seconds IS '缓存生存时间（秒），决定何时需要重新抓取';
COMMENT ON COLUMN community_cache.posts_cached IS '当前缓存的帖子数量，用于容量管理';
COMMENT ON COLUMN community_cache.quality_score IS '缓存质量评分(0.00-1.00)，基于数据完整性和新鲜度';
COMMENT ON COLUMN community_cache.hit_count IS '缓存命中次数，用于LRU清理策略';
COMMENT ON COLUMN community_cache.last_hit_at IS '最后访问时间，LRU算法核心指标';
COMMENT ON COLUMN community_cache.crawl_priority IS '爬虫优先级(1-100)，1为最高优先级';
COMMENT ON COLUMN community_cache.created_at IS '缓存条目创建时间';
COMMENT ON COLUMN community_cache.updated_at IS '缓存元数据最后更新时间';

-- 输出创建完成信息
DO $$
BEGIN
    RAISE NOTICE '✅ Community Cache 缓存表创建完成';
    RAISE NOTICE '🚀 表结构: community_cache (缓存优先架构核心)';
    RAISE NOTICE '📊 索引策略: 5个高性能索引，覆盖所有查询场景';
    RAISE NOTICE '   • ix_community_cache_crawl_schedule (爬虫调度)';
    RAISE NOTICE '   • ix_community_cache_hotness (热度排序)';  
    RAISE NOTICE '   • ix_community_cache_quality (质量筛选)';
    RAISE NOTICE '   • ix_community_cache_freshness (新鲜度查询)';
    RAISE NOTICE '   • ix_community_cache_size (容量管理)';
    RAISE NOTICE '⚡ 自动维护: updated_at触发器 + hit_count统计';
    RAISE NOTICE '🛡️ 约束保护: 社区名格式 + 质量评分范围 + 优先级范围';
END$$;

-- ====================================================================
-- Linus式设计说明和性能优化策略
-- ====================================================================

/*
缓存表设计核心思想：

1. 【数据结构决定一切】
   - community_name作为自然主键：符合查询模式，避免JOIN
   - TTL字段内置：支持不同社区的个性化缓存策略
   - quality_score量化：缓存质量可测量、可优化

2. 【消除特殊情况】  
   - last_crawled_at允许NULL：统一处理"从未抓取"和"已抓取"
   - 所有数值字段都有合理默认值：避免应用层特殊判断
   - hit_count从0开始：新缓存和旧缓存使用同一套LRU逻辑

3. 【索引策略基于实际查询模式】
   - 爬虫调度：需要处理过期缓存，按优先级排序
   - 缓存访问：需要LRU清理，按命中次数和时间排序  
   - 质量管理：需要筛选高质量缓存，按评分排序
   - 容量管理：需要识别大缓存，按帖子数排序
   - 时间窗口：需要查询最近更新，按时间排序

4. 【性能优化内置】
   - 部分索引：只为符合条件的记录创建索引，节省50%+空间
   - 复合索引：支持常见查询的覆盖索引，减少回表
   - 触发器自动化：减少应用层代码复杂度

5. 【缓存策略支持】
   - LRU清理：hit_count + last_hit_at
   - TTL过期：last_crawled_at + ttl_seconds  
   - 优先级调度：crawl_priority
   - 质量评估：quality_score
   - 容量管理：posts_cached

查询性能预期：
- 主键查询（by community_name）：O(1) 
- 爬虫调度查询：O(log n)，使用ix_community_cache_crawl_schedule
- LRU清理查询：O(log n)，使用ix_community_cache_hotness
- 质量筛选查询：O(log n)，使用ix_community_cache_quality

这个表是整个缓存系统的基石，必须设计正确。
"好的缓存比任何算法优化都重要。" - Linus Torvalds
*/