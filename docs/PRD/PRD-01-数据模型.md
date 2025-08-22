# PRD-01: 数据模型设计

## 1. 问题陈述

### 1.1 背景
Reddit Signal Scanner需要一个极简而强大的数据基础架构，支撑"30秒输入，5分钟分析"的核心承诺。系统**从第一天就必须支持多租户**，确保用户数据完全隔离，同时支持缓存优先架构下的高性能数据访问。

### 1.2 目标
设计四张核心表的完整数据模型，遵循"数据结构优先"原则：
- **立即支持多租户隔离**（user_id从第一天存在）
- 支持异步任务处理和状态管理
- **完整的JSON Schema验证**（防止数据格式错误）
- 支持缓存优先架构的元数据管理
- 实现30天自动数据清理机制

### 1.3 非目标
- **不支持**复杂的用户权限系统（保持简单的租户隔离）
- **不支持**实时协作和共享功能
- **不支持**复杂的数据关系图（保持极简）
- **不支持**历史版本管理（专注当前需求）

## 2. 解决方案

### 2.1 核心设计：四表架构（支持多租户+缓存）

基于Linus的"好品味"原则和多租户要求，我们设计一个无特殊情况的四表架构：

```sql
-- 核心四表关系
Users (用户账户) 
  ↓ 1:N
Task (用户分析任务) 
  ↓ 1:1
Analysis (分析结果数据)
  ↓ 1:1  
Report (渲染报告内容)

-- 独立缓存管理
CommunityCache (社区缓存状态)
```

**设计哲学**：
- **Users表**：用户账户管理，实现租户隔离
- **Task表**：存储用户输入和任务状态，绑定用户ID
- **Analysis表**：存储结构化分析结果，带Schema验证
- **Report表**：存储最终用户报告，预渲染HTML
- **CommunityCache表**：缓存状态元数据，支持缓存优先架构

### 2.2 数据流

```
用户提交产品描述 
  ↓
创建Task记录(status: pending)
  ↓
分析引擎处理(status: processing)  
  ↓
写入Analysis结果
  ↓
生成Report内容
  ↓
更新Task状态(status: completed)
```

### 2.3 关键决策

#### 决策1: 为什么只有三张表？
**理由**: 遵循Linus的"消除复杂性"原则。社区、用户评论等不应该成为持久化实体，它们只是查询和分析的中间数据。

#### 决策2: 为什么使用UUID？
**理由**: 避免分布式环境下的ID冲突，支持未来的水平扩展。

#### 决策3: 为什么JSON存储分析结果？
**理由**: PostgreSQL的JSON支持足够强大，避免过早的表结构优化。遵循"先让它工作，再让它快"的原则。

## 3. 技术规范

### 3.1 数据表结构

#### Users表 - 用户账户管理（多租户基础）
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    
    -- 约束
    CONSTRAINT valid_email CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

-- 用户会话索引
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_active ON users(is_active) WHERE is_active = true;
```

#### Task表 - 分析任务管理（立即支持多租户）
```sql
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,  -- 从第一天就支持多租户，不是预留字段！
    product_description TEXT NOT NULL CHECK (char_length(product_description) >= 10),
    status task_status NOT NULL DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- 外键约束
    CONSTRAINT fk_task_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    
    -- 业务约束
    CONSTRAINT valid_description_length 
        CHECK (char_length(product_description) BETWEEN 10 AND 2000),
    CONSTRAINT valid_completion_time 
        CHECK (completed_at IS NULL OR completed_at >= created_at)
);

-- 枚举类型定义
CREATE TYPE task_status AS ENUM (
    'pending',      -- 已创建，等待处理
    'processing',   -- 正在分析
    'completed',    -- 分析完成
    'failed'        -- 分析失败
);
```

-- JSON Schema验证函数（防止数据格式错误）
CREATE OR REPLACE FUNCTION validate_insights_schema(data jsonb)
RETURNS boolean AS $$
BEGIN
    -- 必须是对象类型
    IF jsonb_typeof(data) != 'object' THEN
        RETURN false;
    END IF;
    
    -- 必须包含三个核心字段
    IF NOT (data ? 'pain_points' AND data ? 'competitors' AND data ? 'opportunities') THEN
        RETURN false;
    END IF;
    
    -- 每个字段必须是数组
    IF jsonb_typeof(data->'pain_points') != 'array' OR
       jsonb_typeof(data->'competitors') != 'array' OR 
       jsonb_typeof(data->'opportunities') != 'array' THEN
        RETURN false;
    END IF;
    
    -- 验证pain_points结构
    IF EXISTS (
        SELECT 1 FROM jsonb_array_elements(data->'pain_points') AS item
        WHERE NOT (item ? 'description' AND item ? 'frequency' AND item ? 'sentiment_score')
    ) THEN
        RETURN false;
    END IF;
    
    RETURN true;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION validate_sources_schema(data jsonb)
RETURNS boolean AS $$
BEGIN
    IF jsonb_typeof(data) != 'object' THEN
        RETURN false;
    END IF;
    
    -- 必须包含核心溯源字段
    IF NOT (data ? 'communities' AND data ? 'posts_analyzed' AND data ? 'cache_hit_rate') THEN
        RETURN false;
    END IF;
    
    -- communities必须是数组
    IF jsonb_typeof(data->'communities') != 'array' THEN
        RETURN false;
    END IF;
    
    -- posts_analyzed必须是数字
    IF jsonb_typeof(data->'posts_analyzed') != 'number' THEN
        RETURN false;
    END IF;
    
    RETURN true;
END;
$$ LANGUAGE plpgsql;

#### Analysis表 - 分析结果数据（带Schema验证）
```sql
CREATE TABLE analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    
    -- 核心分析结果 (带Schema验证的JSONB)
    insights JSONB NOT NULL CHECK (validate_insights_schema(insights)),
    -- 标准结构: {
    --   "pain_points": [{
    --     "description": "现有笔记应用间的数据迁移困难",
    --     "frequency": 8,
    --     "sentiment_score": -0.75,
    --     "example_posts": [...]
    --   }],
    --   "competitors": [{
    --     "name": "Notion",
    --     "mentions": 45,
    --     "sentiment": "mixed",
    --     "strengths": [...],
    --     "weaknesses": [...]
    --   }],
    --   "opportunities": [{
    --     "description": "开发更智能的笔记连接算法",
    --     "relevance_score": 0.92,
    --     "potential_users": "研究者和内容创作者"
    --   }]
    -- }
    
    -- 数据溯源信息（带Schema验证）
    sources JSONB NOT NULL CHECK (validate_sources_schema(sources)),
    -- 标准结构: {
    --   "communities": ["r/productivity", "r/PKM"],
    --   "posts_analyzed": 1247,
    --   "cache_hit_rate": 0.87,
    --   "analysis_duration_seconds": 267,
    --   "reddit_api_calls": 28
    -- }
    
    -- 质量指标
    confidence_score DECIMAL(3,2) CHECK (confidence_score BETWEEN 0.00 AND 1.00),
    analysis_version VARCHAR(10) DEFAULT '1.0',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- 索引优化
    UNIQUE(task_id)
);
```

#### Report表 - 用户报告内容
```sql
CREATE TABLE reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    
    -- 预渲染的HTML内容
    html_content TEXT NOT NULL,
    
    -- 报告元数据
    template_version VARCHAR(10) DEFAULT '1.0',
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- 索引优化
    UNIQUE(analysis_id)
);

#### CommunityCache表 - 缓存状态管理（支持缓存优先架构）
```sql
CREATE TABLE community_cache (
    community_name VARCHAR(100) PRIMARY KEY,
    
    -- 缓存状态
    last_crawled_at TIMESTAMP WITH TIME ZONE NOT NULL,
    posts_cached INTEGER NOT NULL DEFAULT 0,
    ttl_seconds INTEGER DEFAULT 3600,
    
    -- 质量评估
    quality_score DECIMAL(3,2) DEFAULT 0.50,
    hit_count INTEGER DEFAULT 0,  -- 被分析任务使用的次数
    
    -- 爬取优先级管理
    crawl_priority INTEGER DEFAULT 50 CHECK (crawl_priority BETWEEN 1 AND 100),
    last_hit_at TIMESTAMP WITH TIME ZONE,  -- 最近一次被使用时间
    
    -- 元数据
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- 约束
    CONSTRAINT valid_cache_data CHECK (posts_cached >= 0),
    CONSTRAINT valid_ttl CHECK (ttl_seconds > 0)
);
```

### 3.2 索引策略（支持多租户查询）

```sql
-- Task表索引：基于真实查询模式，重点支持多租户
CREATE INDEX idx_tasks_user_status ON tasks(user_id, status);  -- 组合索引，最重要
CREATE INDEX idx_tasks_user_created ON tasks(user_id, created_at DESC);  -- 用户任务历史
CREATE INDEX idx_tasks_status ON tasks(status);  -- 系统状态监控

-- Analysis表索引：支持质量查询和业务分析
CREATE INDEX idx_analyses_confidence ON analyses(confidence_score DESC);
CREATE INDEX idx_analyses_version ON analyses(analysis_version);
CREATE INDEX idx_analyses_created ON analyses(created_at DESC);

-- JSONB字段的GIN索引：支持复杂洞察查询
CREATE INDEX idx_analyses_insights_gin ON analyses USING gin(insights);
CREATE INDEX idx_analyses_sources_gin ON analyses USING gin(sources);

-- Report表索引：支持快速报告检索
CREATE INDEX idx_reports_generated ON reports(generated_at DESC);
CREATE INDEX idx_reports_template ON reports(template_version);

-- CommunityCache表索引：支持缓存优先架构
CREATE INDEX idx_cache_priority ON community_cache(crawl_priority DESC);  -- 爬取优先级
CREATE INDEX idx_cache_last_crawled ON community_cache(last_crawled_at);  -- 缓存新鲜度
CREATE INDEX idx_cache_hit_count ON community_cache(hit_count DESC);  -- 使用频率
CREATE INDEX idx_cache_quality ON community_cache(quality_score DESC);  -- 质量排序
```

### 3.3 配置参数（支持多租户和缓存）

```yaml
# database_config.yml
database:
  max_connections: 100
  statement_timeout: "30s"
  idle_in_transaction_session_timeout: "60s"
  
  # 多租户数据保留策略
  data_retention:
    completed_tasks_days: 30
    failed_tasks_days: 7
    orphaned_analysis_hours: 1
    inactive_users_days: 365  # 保留非活跃用户数据1年
    
  # 缓存管理策略
  cache_management:
    community_cache_ttl_hours: 1
    max_cached_communities: 1000
    cache_cleanup_interval_minutes: 30
    priority_recalculation_hours: 6

  # 性能优化（支持JSONB查询）
  performance:
    shared_buffers: "512MB"  # 增加以支持JSONB索引
    effective_cache_size: "2GB"
    work_mem: "8MB"  # 增加以支持复杂查询
    gin_pending_list_limit: "4MB"  # 优化GIN索引性能
```

## 4. 验收标准

### 4.1 功能要求

**基础数据操作**：
- [ ] 能创建Task记录，自动生成UUID
- [ ] 能将Task状态从pending → processing → completed
- [ ] 能存储和检索JSON格式的分析结果
- [ ] 能生成完整的分析报告HTML

**数据完整性**：
- [ ] 外键约束正确工作，级联删除生效
- [ ] 所有CHECK约束能阻止无效数据
- [ ] UNIQUE约束确保一对一关系

**异常处理**：
- [ ] 插入无效数据时报错清晰
- [ ] 删除Task时自动清理Analysis和Report
- [ ] 并发操作不会产生数据不一致

### 4.2 性能指标

| 操作类型 | 性能要求 | 测试数据量 |
|---------|---------|-----------|
| 创建Task | < 50ms | 1万条记录 |
| 查询Task状态 | < 10ms | 1万条记录 |
| 写入Analysis | < 100ms | JSON大小<1MB |
| 获取Report | < 20ms | HTML大小<500KB |
| 数据清理 | < 5分钟 | 处理30天过期数据 |

### 4.3 测试用例

```sql
-- 测试1: 正常流程
INSERT INTO tasks (product_description) 
VALUES ('AI笔记应用，帮助研究者管理知识图谱');

-- 测试2: 边界条件
INSERT INTO tasks (product_description) 
VALUES ('描述太短'); -- 应该失败

-- 测试3: 级联删除
DELETE FROM tasks WHERE id = '...'; -- 应该清理关联记录

-- 测试4: JSON查询
SELECT * FROM analyses 
WHERE insights @> '{"pain_points": [{"frequency": 5}]}';
```

## 5. 风险管理

### 5.1 技术风险

**风险1**: PostgreSQL的JSON查询性能
- **影响**: 复杂洞察查询可能超时
- **缓解**: 使用GIN索引，限制JSON深度
- **监控**: 查询执行时间 < 100ms

**风险2**: 数据增长过快
- **影响**: 存储空间和查询性能下降
- **缓解**: 30天自动清理策略
- **监控**: 表大小和行数增长趋势

### 5.2 依赖项

**PostgreSQL版本**: >= 13.0 （支持gen_random_uuid()）
**扩展要求**: 
- uuid-ossp （UUID生成）
- btree_gin （复合索引优化）

### 5.3 降级方案

**数据库不可用**：
- 返回503错误，提示稍后重试
- 任务队列暂停接收新任务
- 保持现有分析任务在Redis中

**存储空间不足**：
- 立即执行数据清理
- 暂停新任务创建
- 发送运维告警

---

## 附录A: 数据库迁移脚本（支持多租户+缓存）

```sql
-- 001_initial_schema.sql
BEGIN;

-- 启用UUID扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- 创建枚举类型
CREATE TYPE task_status AS ENUM ('pending', 'processing', 'completed', 'failed');

-- JSON Schema验证函数
CREATE OR REPLACE FUNCTION validate_insights_schema(data jsonb)
RETURNS boolean AS $$
BEGIN
    IF jsonb_typeof(data) != 'object' THEN RETURN false; END IF;
    IF NOT (data ? 'pain_points' AND data ? 'competitors' AND data ? 'opportunities') THEN RETURN false; END IF;
    IF jsonb_typeof(data->'pain_points') != 'array' OR jsonb_typeof(data->'competitors') != 'array' OR jsonb_typeof(data->'opportunities') != 'array' THEN RETURN false; END IF;
    IF EXISTS (SELECT 1 FROM jsonb_array_elements(data->'pain_points') AS item WHERE NOT (item ? 'description' AND item ? 'frequency' AND item ? 'sentiment_score')) THEN RETURN false; END IF;
    RETURN true;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION validate_sources_schema(data jsonb)
RETURNS boolean AS $$
BEGIN
    IF jsonb_typeof(data) != 'object' THEN RETURN false; END IF;
    IF NOT (data ? 'communities' AND data ? 'posts_analyzed' AND data ? 'cache_hit_rate') THEN RETURN false; END IF;
    IF jsonb_typeof(data->'communities') != 'array' THEN RETURN false; END IF;
    IF jsonb_typeof(data->'posts_analyzed') != 'number' THEN RETURN false; END IF;
    RETURN true;
END;
$$ LANGUAGE plpgsql;

-- 创建用户表（多租户基础）
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    CONSTRAINT valid_email CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$')
);

-- 创建任务表（立即支持多租户）
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    product_description TEXT NOT NULL,
    status task_status NOT NULL DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    
    CONSTRAINT fk_task_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT valid_description_length CHECK (char_length(product_description) BETWEEN 10 AND 2000),
    CONSTRAINT valid_completion_time CHECK (completed_at IS NULL OR completed_at >= created_at)
);

-- 创建分析表（带Schema验证）
CREATE TABLE analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    insights JSONB NOT NULL CHECK (validate_insights_schema(insights)),
    sources JSONB NOT NULL CHECK (validate_sources_schema(sources)),
    confidence_score DECIMAL(3,2) CHECK (confidence_score BETWEEN 0.00 AND 1.00),
    analysis_version VARCHAR(10) DEFAULT '1.0',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(task_id)
);

-- 创建报告表
CREATE TABLE reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    html_content TEXT NOT NULL,
    template_version VARCHAR(10) DEFAULT '1.0',
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(analysis_id)
);

-- 创建缓存状态表（支持缓存优先架构）
CREATE TABLE community_cache (
    community_name VARCHAR(100) PRIMARY KEY,
    last_crawled_at TIMESTAMP WITH TIME ZONE NOT NULL,
    posts_cached INTEGER NOT NULL DEFAULT 0,
    ttl_seconds INTEGER DEFAULT 3600,
    quality_score DECIMAL(3,2) DEFAULT 0.50,
    hit_count INTEGER DEFAULT 0,
    crawl_priority INTEGER DEFAULT 50 CHECK (crawl_priority BETWEEN 1 AND 100),
    last_hit_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT valid_cache_data CHECK (posts_cached >= 0),
    CONSTRAINT valid_ttl CHECK (ttl_seconds > 0)
);

-- 创建优化索引（支持多租户查询）
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_active ON users(is_active) WHERE is_active = true;
CREATE INDEX idx_tasks_user_status ON tasks(user_id, status);
CREATE INDEX idx_tasks_user_created ON tasks(user_id, created_at DESC);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_analyses_confidence ON analyses(confidence_score DESC);
CREATE INDEX idx_analyses_version ON analyses(analysis_version);
CREATE INDEX idx_analyses_created ON analyses(created_at DESC);
CREATE INDEX idx_analyses_insights_gin ON analyses USING gin(insights);
CREATE INDEX idx_analyses_sources_gin ON analyses USING gin(sources);
CREATE INDEX idx_reports_generated ON reports(generated_at DESC);
CREATE INDEX idx_reports_template ON reports(template_version);
CREATE INDEX idx_cache_priority ON community_cache(crawl_priority DESC);
CREATE INDEX idx_cache_last_crawled ON community_cache(last_crawled_at);
CREATE INDEX idx_cache_hit_count ON community_cache(hit_count DESC);
CREATE INDEX idx_cache_quality ON community_cache(quality_score DESC);

COMMIT;
```

## 附录B: 数据清理存储过程

```sql
-- 清理过期数据的存储过程
CREATE OR REPLACE FUNCTION cleanup_expired_data()
RETURNS TABLE(deleted_tasks INTEGER, deleted_orphaned INTEGER) AS $$
DECLARE
    completed_count INTEGER;
    failed_count INTEGER;
    orphaned_count INTEGER;
BEGIN
    -- 清理30天前的已完成任务
    DELETE FROM tasks 
    WHERE status = 'completed' 
      AND completed_at < CURRENT_TIMESTAMP - INTERVAL '30 days';
    GET DIAGNOSTICS completed_count = ROW_COUNT;
    
    -- 清理7天前的失败任务
    DELETE FROM tasks 
    WHERE status = 'failed' 
      AND updated_at < CURRENT_TIMESTAMP - INTERVAL '7 days';
    GET DIAGNOSTICS failed_count = ROW_COUNT;
    
    -- 清理1小时前的孤儿分析记录
    DELETE FROM analyses 
    WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '1 hour'
      AND task_id NOT IN (SELECT id FROM tasks);
    GET DIAGNOSTICS orphaned_count = ROW_COUNT;
    
    RETURN QUERY SELECT 
        completed_count + failed_count,
        orphaned_count;
END;
$$ LANGUAGE plpgsql;
```

---

**文档版本**: 2.0（修复Linus致命问题）  
**最后更新**: 2025-01-21  
**关键修复**:  
- ✅ 立即支持多租户（user_id从第一天存在）
- ✅ 完整JSON Schema验证（防止数据格式错误）
- ✅ 缓存状态管理表（支持缓存优先架构）
- ✅ 优化多租户索引策略

**审核状态**: 等待Linus re-review  
**实施优先级**: P0 - 核心基础设施（已修复致命缺陷）