-- Reddit Signal Scanner - JSON Schema 验证函数
-- 基于 Linus Torvalds 设计原则：简单、可靠、高性能
-- PRD-01-04: 实现PostgreSQL函数验证insights和sources的JSON结构

-- 确保在正确的模式中
SET search_path TO signal_scanner, public;

-- ====================================================================
-- validate_insights_schema: 验证分析结果的JSON结构
-- ====================================================================
-- 验证结构：{
--   "pain_points": [{description, frequency, sentiment_score, example_posts}],
--   "competitors": [{name, mentions, sentiment, strengths, weaknesses}],
--   "opportunities": [{description, relevance_score, potential_users}]
-- }

CREATE OR REPLACE FUNCTION validate_insights_schema(data jsonb)
RETURNS boolean
LANGUAGE plpgsql
IMMUTABLE
PARALLEL SAFE
AS $$
DECLARE
    pain_point jsonb;
    competitor jsonb;
    opportunity jsonb;
BEGIN
    -- 基础结构检查：必须包含三个主要部分
    IF NOT (data ? 'pain_points' AND data ? 'competitors' AND data ? 'opportunities') THEN
        RETURN false;
    END IF;
    
    -- 验证pain_points数组
    IF jsonb_typeof(data->'pain_points') != 'array' THEN
        RETURN false;
    END IF;
    
    -- 验证每个pain_point元素
    FOR pain_point IN SELECT jsonb_array_elements(data->'pain_points')
    LOOP
        -- 检查必需字段存在性和类型
        IF NOT (pain_point ? 'description' AND pain_point ? 'frequency' AND 
                pain_point ? 'sentiment_score' AND pain_point ? 'example_posts') THEN
            RETURN false;
        END IF;
        
        -- 类型检查
        IF jsonb_typeof(pain_point->'description') != 'string' OR
           jsonb_typeof(pain_point->'frequency') != 'number' OR
           jsonb_typeof(pain_point->'sentiment_score') != 'number' OR
           jsonb_typeof(pain_point->'example_posts') != 'array' THEN
            RETURN false;
        END IF;
        
        -- 范围检查
        IF (pain_point->>'frequency')::numeric < 0 OR
           (pain_point->>'sentiment_score')::numeric < -1 OR
           (pain_point->>'sentiment_score')::numeric > 1 THEN
            RETURN false;
        END IF;
    END LOOP;
    
    -- 验证competitors数组
    IF jsonb_typeof(data->'competitors') != 'array' THEN
        RETURN false;
    END IF;
    
    -- 验证每个competitor元素
    FOR competitor IN SELECT jsonb_array_elements(data->'competitors')
    LOOP
        -- 检查必需字段存在性和类型
        IF NOT (competitor ? 'name' AND competitor ? 'mentions' AND 
                competitor ? 'sentiment' AND competitor ? 'strengths' AND 
                competitor ? 'weaknesses') THEN
            RETURN false;
        END IF;
        
        -- 类型检查
        IF jsonb_typeof(competitor->'name') != 'string' OR
           jsonb_typeof(competitor->'mentions') != 'number' OR
           jsonb_typeof(competitor->'sentiment') != 'number' OR
           jsonb_typeof(competitor->'strengths') != 'array' OR
           jsonb_typeof(competitor->'weaknesses') != 'array' THEN
            RETURN false;
        END IF;
        
        -- 范围检查
        IF (competitor->>'mentions')::numeric < 0 OR
           (competitor->>'sentiment')::numeric < -1 OR
           (competitor->>'sentiment')::numeric > 1 THEN
            RETURN false;
        END IF;
    END LOOP;
    
    -- 验证opportunities数组
    IF jsonb_typeof(data->'opportunities') != 'array' THEN
        RETURN false;
    END IF;
    
    -- 验证每个opportunity元素
    FOR opportunity IN SELECT jsonb_array_elements(data->'opportunities')
    LOOP
        -- 检查必需字段存在性和类型
        IF NOT (opportunity ? 'description' AND opportunity ? 'relevance_score' AND 
                opportunity ? 'potential_users') THEN
            RETURN false;
        END IF;
        
        -- 类型检查
        IF jsonb_typeof(opportunity->'description') != 'string' OR
           jsonb_typeof(opportunity->'relevance_score') != 'number' OR
           jsonb_typeof(opportunity->'potential_users') != 'number' THEN
            RETURN false;
        END IF;
        
        -- 范围检查
        IF (opportunity->>'relevance_score')::numeric < 0 OR
           (opportunity->>'relevance_score')::numeric > 1 OR
           (opportunity->>'potential_users')::numeric < 0 THEN
            RETURN false;
        END IF;
    END LOOP;
    
    -- 所有验证通过
    RETURN true;
    
EXCEPTION
    -- 任何异常都视为验证失败
    WHEN OTHERS THEN
        RETURN false;
END;
$$;

-- ====================================================================
-- validate_sources_schema: 验证数据源信息的JSON结构  
-- ====================================================================
-- 验证结构：{
--   "communities": ["r/xxx"],
--   "posts_analyzed": number,
--   "cache_hit_rate": number,
--   "analysis_duration_seconds": number,
--   "reddit_api_calls": number
-- }

CREATE OR REPLACE FUNCTION validate_sources_schema(data jsonb)
RETURNS boolean
LANGUAGE plpgsql
IMMUTABLE  
PARALLEL SAFE
AS $$
DECLARE
    community text;
BEGIN
    -- 基础结构检查：必须包含所有字段
    IF NOT (data ? 'communities' AND data ? 'posts_analyzed' AND 
            data ? 'cache_hit_rate' AND data ? 'analysis_duration_seconds' AND
            data ? 'reddit_api_calls') THEN
        RETURN false;
    END IF;
    
    -- 验证communities数组
    IF jsonb_typeof(data->'communities') != 'array' THEN
        RETURN false;
    END IF;
    
    -- 验证communities数组中的每个元素都是字符串且格式正确
    FOR community IN SELECT jsonb_array_elements_text(data->'communities')
    LOOP
        -- 检查Reddit社区格式 (r/xxx)
        IF community IS NULL OR NOT community ~ '^r/[a-zA-Z0-9_]+$' THEN
            RETURN false;
        END IF;
    END LOOP;
    
    -- 验证数值字段类型
    IF jsonb_typeof(data->'posts_analyzed') != 'number' OR
       jsonb_typeof(data->'cache_hit_rate') != 'number' OR
       jsonb_typeof(data->'analysis_duration_seconds') != 'number' OR
       jsonb_typeof(data->'reddit_api_calls') != 'number' THEN
        RETURN false;
    END IF;
    
    -- 范围检查
    IF (data->>'posts_analyzed')::numeric < 0 OR
       (data->>'cache_hit_rate')::numeric < 0 OR
       (data->>'cache_hit_rate')::numeric > 1 OR
       (data->>'analysis_duration_seconds')::numeric < 0 OR
       (data->>'reddit_api_calls')::numeric < 0 THEN
        RETURN false;
    END IF;
    
    -- 所有验证通过
    RETURN true;
    
EXCEPTION
    -- 任何异常都视为验证失败
    WHEN OTHERS THEN
        RETURN false;
END;
$$;

-- 创建函数的使用示例注释
COMMENT ON FUNCTION validate_insights_schema(jsonb) IS 
'验证分析结果JSON结构，确保包含pain_points, competitors, opportunities三个数组，每个数组元素包含必需字段且类型正确';

COMMENT ON FUNCTION validate_sources_schema(jsonb) IS
'验证数据源信息JSON结构，确保包含communities数组和各种统计数值字段，并进行范围检查';

-- 输出创建完成信息
DO $$
BEGIN
    RAISE NOTICE '✅ JSON Schema 验证函数创建完成';
    RAISE NOTICE '🔍 validate_insights_schema: 验证分析结果结构';
    RAISE NOTICE '📊 validate_sources_schema: 验证数据源信息结构';
    RAISE NOTICE '⚡ 函数设计遵循Linus高性能原则：IMMUTABLE + PARALLEL SAFE';
    RAISE NOTICE '🛡️ 包含完整的类型检查、范围检查和异常处理';
END$$;
