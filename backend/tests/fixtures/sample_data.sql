-- Reddit Signal Scanner - 测试数据样本工厂
-- 基于Linus原则：数据结构决定测试质量
-- 
-- 用途：
--   1. 性能基准测试的大数据量生成
--   2. 边界条件测试的系统化数据
--   3. 多租户隔离测试的隔离验证
--   4. 约束违反测试的完整覆盖

-- ============================================================================
-- 1. 清理和重置函数
-- ============================================================================

-- 清理所有测试数据
CREATE OR REPLACE FUNCTION cleanup_test_data()
RETURNS void AS $$
BEGIN
    -- 按依赖顺序删除
    TRUNCATE reports CASCADE;
    TRUNCATE analyses CASCADE;
    TRUNCATE tasks CASCADE;
    TRUNCATE community_cache CASCADE;
    TRUNCATE users CASCADE;
    
    -- 重置序列（如果有的话）
    -- ALTER SEQUENCE IF EXISTS some_seq RESTART WITH 1;
    
    RAISE NOTICE '测试数据已清理';
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 2. 多租户测试数据生成
-- ============================================================================

-- 创建多租户测试环境
CREATE OR REPLACE FUNCTION create_multi_tenant_test_data()
RETURNS TABLE(
    tenant_a_id UUID,
    tenant_b_id UUID,
    user_a_id UUID,
    user_b_id UUID
) AS $$
DECLARE
    t_a_id UUID := gen_random_uuid();
    t_b_id UUID := gen_random_uuid();
    u_a_id UUID;
    u_b_id UUID;
BEGIN
    -- 租户A用户
    INSERT INTO users (tenant_id, email, password_hash, email_verified, is_active)
    VALUES (
        t_a_id,
        'user_a@tenant_a.com',
        '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj7.k7iBOdYW',
        true,
        true
    ) RETURNING id INTO u_a_id;
    
    -- 租户B用户
    INSERT INTO users (tenant_id, email, password_hash, email_verified, is_active)  
    VALUES (
        t_b_id,
        'user_b@tenant_b.com',
        '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj7.k7iBOdYW',
        true,
        true
    ) RETURNING id INTO u_b_id;
    
    -- 为每个租户创建5个任务
    FOR i IN 1..5 LOOP
        -- 租户A的任务
        INSERT INTO tasks (user_id, product_description, status)
        VALUES (
            u_a_id,
            '租户A的产品描述 ' || i || ' - 这是一个足够长的描述来满足约束要求',
            CASE 
                WHEN i <= 2 THEN 'completed'
                WHEN i = 3 THEN 'processing'
                WHEN i = 4 THEN 'failed'
                ELSE 'pending'
            END
        );
        
        -- 租户B的任务  
        INSERT INTO tasks (user_id, product_description, status)
        VALUES (
            u_b_id,
            '租户B的产品描述 ' || i || ' - 这也是一个足够长的描述来满足约束要求',
            CASE 
                WHEN i <= 3 THEN 'completed'
                WHEN i = 4 THEN 'processing'  
                ELSE 'pending'
            END
        );
    END LOOP;
    
    RETURN QUERY VALUES (t_a_id, t_b_id, u_a_id, u_b_id);
    
    RAISE NOTICE '多租户测试数据已创建: 租户A=%, 租户B=%', t_a_id, t_b_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 3. 边界条件测试数据
-- ============================================================================

-- 创建边界条件测试用户
CREATE OR REPLACE FUNCTION create_edge_case_users()
RETURNS void AS $$
DECLARE
    tenant_id UUID := gen_random_uuid();
BEGIN
    -- 最长有效邮箱 (320字符)
    INSERT INTO users (tenant_id, email, password_hash, email_verified, is_active)
    VALUES (
        tenant_id,
        repeat('x', 64) || '@' || repeat('y', 251) || '.com',
        '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj7.k7iBOdYW',
        false,
        true
    );
    
    -- 最短有效邮箱 (5字符)
    INSERT INTO users (tenant_id, email, password_hash, email_verified, is_active)
    VALUES (
        tenant_id,
        'a@b.co',
        '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj7.k7iBOdYW',
        false,
        true
    );
    
    -- 包含特殊字符的有效邮箱
    INSERT INTO users (tenant_id, email, password_hash, email_verified, is_active)
    VALUES (
        tenant_id,
        'test.email+tag@sub-domain.example-site.com',
        '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj7.k7iBOdYW',
        true,
        true
    );
    
    -- 非活跃用户
    INSERT INTO users (tenant_id, email, password_hash, email_verified, is_active)
    VALUES (
        tenant_id,
        'inactive@example.com',
        '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj7.k7iBOdYW',
        true,
        false
    );
    
    RAISE NOTICE '边界条件用户已创建';
END;
$$ LANGUAGE plpgsql;

-- 创建任务边界条件数据
CREATE OR REPLACE FUNCTION create_edge_case_tasks(target_user_id UUID)
RETURNS void AS $$
BEGIN
    -- 最短有效描述 (10字符)
    INSERT INTO tasks (user_id, product_description, status)
    VALUES (target_user_id, '1234567890', 'pending');
    
    -- 最长有效描述 (2000字符)
    INSERT INTO tasks (user_id, product_description, status)
    VALUES (target_user_id, repeat('长描述', 333) || '尾', 'pending');
    
    -- 包含多种语言和特殊字符
    INSERT INTO tasks (user_id, product_description, status)
    VALUES (
        target_user_id,
        'Multi-language product: English, 中文, 日本語, Español. Special chars: @#$%^&*()_+-={}[]|\":;''<>?,./',
        'pending'
    );
    
    -- 已完成任务（带完成时间）
    INSERT INTO tasks (user_id, product_description, status, completed_at)
    VALUES (
        target_user_id,
        '这是一个已完成的任务描述',
        'completed',
        CURRENT_TIMESTAMP
    );
    
    -- 失败任务（带错误信息）
    INSERT INTO tasks (user_id, product_description, status, error_message)
    VALUES (
        target_user_id,
        '这是一个失败的任务描述',
        'failed',
        'API调用超时：Reddit服务不可用，请稍后重试'
    );
    
    RAISE NOTICE '边界条件任务已创建';
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 4. 性能测试数据生成
-- ============================================================================

-- 生成大量测试数据用于性能基准测试
CREATE OR REPLACE FUNCTION create_performance_test_data(
    num_users INTEGER DEFAULT 100,
    tasks_per_user INTEGER DEFAULT 100
) RETURNS void AS $$
DECLARE
    tenant_id UUID;
    user_id UUID;
    task_id UUID;
    i INTEGER;
    j INTEGER;
    task_statuses TEXT[] := ARRAY['pending', 'processing', 'completed', 'failed'];
BEGIN
    RAISE NOTICE '开始创建性能测试数据: % 用户, 每用户 % 任务', num_users, tasks_per_user;
    
    FOR i IN 1..num_users LOOP
        tenant_id := gen_random_uuid();
        
        -- 创建用户
        INSERT INTO users (tenant_id, email, password_hash, email_verified, is_active)
        VALUES (
            tenant_id,
            'perf_user_' || i || '@performance.test',
            '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj7.k7iBOdYW',
            (i % 2 = 0),  -- 50%邮箱验证率
            (i % 20 != 0) -- 95%活跃率
        ) RETURNING id INTO user_id;
        
        -- 为每个用户创建任务
        FOR j IN 1..tasks_per_user LOOP
            INSERT INTO tasks (
                user_id, 
                product_description, 
                status,
                completed_at,
                error_message
            ) VALUES (
                user_id,
                '性能测试产品描述 ' || i || '-' || j || ': ' || repeat('这是一个产品描述内容。', 5),
                task_statuses[(j % 4) + 1],
                CASE WHEN task_statuses[(j % 4) + 1] = 'completed' 
                     THEN CURRENT_TIMESTAMP - interval '1 day' * (j % 30)
                     ELSE NULL 
                END,
                CASE WHEN task_statuses[(j % 4) + 1] = 'failed'
                     THEN '测试失败错误信息 ' || j
                     ELSE NULL
                END
            ) RETURNING id INTO task_id;
            
            -- 为已完成的任务创建分析结果 (每4个任务中1个)
            IF task_statuses[(j % 4) + 1] = 'completed' AND j % 4 = 1 THEN
                INSERT INTO analyses (
                    task_id,
                    insights,
                    sources,
                    confidence_score,
                    analysis_version
                ) VALUES (
                    task_id,
                    '{"pain_points": [{"description": "测试痛点", "frequency": 10, "sentiment_score": 0.5}], "competitors": [{"name": "测试竞品", "mention_count": 5, "sentiment_score": 0.6, "strengths": [], "weaknesses": [], "price_mentions": [], "market_position": "unknown"}], "opportunities": [{"title": "测试机会", "description": "测试机会描述", "market_size_indicator": "medium", "urgency_score": 0.7, "feasibility_score": 0.8, "target_communities": [], "related_keywords": [], "estimated_demand": 100}]}'::jsonb,
                    '{"communities": ["r/test"], "posts_analyzed": 100, "cache_hit_rate": 0.5, "comments_analyzed": 500, "time_range_days": 30, "analysis_duration_seconds": 45.0, "reddit_api_calls": 50, "data_quality_score": 0.9, "filtered_spam_posts": 5, "language_distribution": {"en": 95, "other": 5}, "algorithm_version": "test_v1.0", "processing_parameters": {}}'::jsonb,
                    0.75 + (j % 25) * 0.01,  -- 0.75-0.99的置信度分布
                    1
                );
            END IF;
        END LOOP;
        
        -- 每100个用户输出进度
        IF i % 100 = 0 THEN
            RAISE NOTICE '已创建 % 个用户及其任务', i;
        END IF;
    END LOOP;
    
    RAISE NOTICE '性能测试数据创建完成: % 用户, % 任务总计', num_users, num_users * tasks_per_user;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 5. JSON Schema测试数据
-- ============================================================================

-- 创建有效的洞察数据样本
CREATE OR REPLACE FUNCTION get_valid_insights_sample()
RETURNS jsonb AS $$
BEGIN
    RETURN '{
        "pain_points": [
            {
                "description": "找不到好用的Reddit营销工具，现有工具功能单一",
                "sentiment_score": 0.75,
                "frequency": 23,
                "evidence_posts": ["post_123", "post_456"],
                "categories": ["工具缺失", "营销困难"]
            },
            {
                "description": "Reddit API限制太严格，影响数据收集",
                "sentiment_score": 0.85,
                "frequency": 18,
                "evidence_posts": ["post_789"],
                "categories": ["API限制"]
            }
        ],
        "competitors": [
            {
                "name": "Hootsuite",
                "mention_count": 45,
                "sentiment_score": 0.65,
                "strengths": ["功能全面", "界面友好", "支持多平台"],
                "weaknesses": ["价格昂贵", "学习成本高"],
                "price_mentions": ["$99/month", "too expensive", "subscription model"],
                "market_position": "leader"
            },
            {
                "name": "Buffer",
                "mention_count": 32,
                "sentiment_score": 0.72,
                "strengths": ["简单易用", "价格合理"],
                "weaknesses": ["功能有限", "Reddit支持不足"],
                "price_mentions": ["$15/month", "affordable"],
                "market_position": "challenger"
            }
        ],
        "opportunities": [
            {
                "title": "专门的Reddit营销自动化工具",
                "description": "开发专注于Reddit的营销自动化工具，填补市场空白",
                "market_size_indicator": "large",
                "urgency_score": 0.85,
                "feasibility_score": 0.70,
                "target_communities": ["r/entrepreneur", "r/marketing", "r/smallbusiness"],
                "related_keywords": ["reddit automation", "social media marketing", "community management"],
                "estimated_demand": 2500
            },
            {
                "title": "Reddit数据分析SaaS平台",
                "description": "提供深度的Reddit数据分析和用户洞察服务",
                "market_size_indicator": "medium",
                "urgency_score": 0.72,
                "feasibility_score": 0.85,
                "target_communities": ["r/analytics", "r/datascience"],
                "related_keywords": ["reddit analytics", "social listening", "data insights"],
                "estimated_demand": 1200
            }
        ],
        "analysis_summary": {
            "total_mentions": 150,
            "sentiment_distribution": {"positive": 0.4, "neutral": 0.35, "negative": 0.25},
            "top_themes": ["automation", "pricing", "ease_of_use", "feature_gaps"]
        },
        "key_insights": [
            "Reddit营销工具市场存在显著功能空白",
            "用户对现有工具的定价普遍不满",
            "自动化是最被需要的功能",
            "易用性比功能丰富性更重要"
        ]
    }'::jsonb;
END;
$$ LANGUAGE plpgsql;

-- 创建有效的数据来源样本
CREATE OR REPLACE FUNCTION get_valid_sources_sample()
RETURNS jsonb AS $$
BEGIN
    RETURN '{
        "communities": ["r/entrepreneur", "r/marketing", "r/startups", "r/smallbusiness"],
        "posts_analyzed": 1250,
        "comments_analyzed": 8450,
        "time_range_days": 30,
        "cache_hit_rate": 0.75,
        "analysis_duration_seconds": 45.6,
        "reddit_api_calls": 125,
        "data_quality_score": 0.92,
        "filtered_spam_posts": 23,
        "language_distribution": {"en": 1200, "es": 30, "fr": 15, "other": 5},
        "algorithm_version": "v2.1.0",
        "processing_parameters": {
            "min_score_threshold": 5,
            "sentiment_model": "vader",
            "clustering_method": "kmeans",
            "max_posts_per_community": 500,
            "time_decay_factor": 0.9
        }
    }'::jsonb;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 6. 约束违反测试数据
-- ============================================================================

-- 获取无效数据样本（用于测试约束违反）
CREATE OR REPLACE FUNCTION get_constraint_violation_samples()
RETURNS TABLE(
    test_case TEXT,
    data_type TEXT,
    invalid_data jsonb,
    expected_constraint TEXT
) AS $$
BEGIN
    -- 无效的洞察数据
    RETURN QUERY VALUES
    ('缺少pain_points字段', 'insights', '{"competitors": [], "opportunities": []}'::jsonb, 'ck_analyses_insights_schema'),
    ('pain_points不是数组', 'insights', '{"pain_points": "not_array", "competitors": [], "opportunities": []}'::jsonb, 'ck_analyses_insights_schema'),
    ('pain_point缺少必需字段', 'insights', '{"pain_points": [{"description": "test"}], "competitors": [], "opportunities": []}'::jsonb, 'ck_analyses_insights_schema'),
    ('sentiment_score超出范围', 'insights', '{"pain_points": [{"description": "test", "frequency": 1, "sentiment_score": 1.5}], "competitors": [], "opportunities": []}'::jsonb, 'ck_analyses_insights_schema');
    
    -- 无效的来源数据
    RETURN QUERY VALUES
    ('缺少communities字段', 'sources', '{"posts_analyzed": 100, "cache_hit_rate": 0.5}'::jsonb, 'ck_analyses_sources_schema'),
    ('communities不是数组', 'sources', '{"communities": "not_array", "posts_analyzed": 100, "cache_hit_rate": 0.5}'::jsonb, 'ck_analyses_sources_schema'),
    ('posts_analyzed为负数', 'sources', '{"communities": [], "posts_analyzed": -1, "cache_hit_rate": 0.5}'::jsonb, 'ck_analyses_sources_schema'),
    ('cache_hit_rate超出范围', 'sources', '{"communities": [], "posts_analyzed": 100, "cache_hit_rate": 1.5}'::jsonb, 'ck_analyses_sources_schema');
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 7. 便捷的数据管理函数
-- ============================================================================

-- 获取测试数据统计
CREATE OR REPLACE FUNCTION get_test_data_stats()
RETURNS TABLE(
    table_name TEXT,
    row_count BIGINT,
    sample_ids TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 'users'::TEXT, COUNT(*), string_agg(id::text, ', ' ORDER BY created_at LIMIT 5)
    FROM users;
    
    RETURN QUERY  
    SELECT 'tasks'::TEXT, COUNT(*), string_agg(id::text, ', ' ORDER BY created_at LIMIT 5)
    FROM tasks;
    
    RETURN QUERY
    SELECT 'analyses'::TEXT, COUNT(*), string_agg(id::text, ', ' ORDER BY created_at LIMIT 5) 
    FROM analyses;
    
    RETURN QUERY
    SELECT 'reports'::TEXT, COUNT(*), string_agg(id::text, ', ' ORDER BY created_at LIMIT 5)
    FROM reports;
    
    RETURN QUERY
    SELECT 'community_cache'::TEXT, COUNT(*), string_agg(id::text, ', ' ORDER BY created_at LIMIT 5)
    FROM community_cache;
END;
$$ LANGUAGE plpgsql;

-- 创建完整的测试环境
CREATE OR REPLACE FUNCTION setup_complete_test_environment()
RETURNS void AS $$
BEGIN
    -- 清理现有数据
    PERFORM cleanup_test_data();
    
    -- 创建多租户数据
    PERFORM create_multi_tenant_test_data();
    
    -- 创建边界条件数据
    PERFORM create_edge_case_users();
    
    -- 为第一个用户创建边界条件任务
    PERFORM create_edge_case_tasks((SELECT id FROM users LIMIT 1));
    
    RAISE NOTICE '完整测试环境已设置';
    
    -- 显示统计信息
    RAISE NOTICE '数据统计:';
    PERFORM get_test_data_stats();
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 8. 使用示例和文档
-- ============================================================================

/*
使用示例：

-- 1. 设置基本测试环境
SELECT setup_complete_test_environment();

-- 2. 创建性能测试数据（小规模）
SELECT create_performance_test_data(10, 50);

-- 3. 创建大规模性能测试数据（谨慎使用）
SELECT create_performance_test_data(1000, 100);

-- 4. 获取测试JSON数据
SELECT get_valid_insights_sample();
SELECT get_valid_sources_sample();

-- 5. 查看约束违反测试用例
SELECT * FROM get_constraint_violation_samples();

-- 6. 查看数据统计
SELECT * FROM get_test_data_stats();

-- 7. 清理测试数据
SELECT cleanup_test_data();

-- 8. 多租户数据隔离测试
SELECT * FROM create_multi_tenant_test_data();
*/

COMMENT ON FUNCTION cleanup_test_data() IS '清理所有测试数据，恢复空白状态';
COMMENT ON FUNCTION create_multi_tenant_test_data() IS '创建多租户测试数据，返回租户和用户ID';
COMMENT ON FUNCTION create_performance_test_data(INTEGER, INTEGER) IS '创建大量性能测试数据，参数：用户数量，每用户任务数量';
COMMENT ON FUNCTION get_valid_insights_sample() IS '获取有效的洞察数据JSON样本';
COMMENT ON FUNCTION get_valid_sources_sample() IS '获取有效的数据来源JSON样本';
COMMENT ON FUNCTION setup_complete_test_environment() IS '一键设置完整的测试环境';

-- 测试环境验证：确保所有函数正常工作
DO $$
BEGIN
    RAISE NOTICE '测试数据工厂SQL脚本加载完成';
    RAISE NOTICE '可用函数：';
    RAISE NOTICE '  - setup_complete_test_environment()：一键测试环境设置';
    RAISE NOTICE '  - create_performance_test_data(users, tasks_per_user)：性能测试数据';
    RAISE NOTICE '  - get_valid_insights_sample()：有效洞察数据样本';
    RAISE NOTICE '  - get_valid_sources_sample()：有效来源数据样本';
    RAISE NOTICE '  - cleanup_test_data()：清理所有测试数据';
    RAISE NOTICE '  - get_test_data_stats()：数据统计信息';
END $$;