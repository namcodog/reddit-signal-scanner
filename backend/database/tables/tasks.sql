-- Reddit Signal Scanner - Tasks表定义
-- 基于 Linus 设计哲学：数据结构决定代码复杂度
-- 任务：prd01-03 创建tasks表和状态管理

-- 确保在正确的模式中
SET search_path TO signal_scanner, public;

-- 创建tasks表
CREATE TABLE tasks (
    -- 主键：UUID类型，数据库生成
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 多租户隔离：外键到users表
    user_id UUID NOT NULL,
    
    -- 产品描述：用户输入的分析目标
    product_description TEXT NOT NULL,
    
    -- 任务状态：使用预定义枚举
    status task_status NOT NULL DEFAULT 'pending',
    
    -- 错误信息：失败时记录具体原因
    error_message TEXT,
    
    -- 审计字段：自动维护
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- 外键约束：级联删除确保数据一致性
    CONSTRAINT fk_tasks_user_id 
        FOREIGN KEY (user_id) 
        REFERENCES users(id) 
        ON DELETE CASCADE,
    
    -- 业务约束：产品描述长度限制
    CONSTRAINT ck_tasks_description_length 
        CHECK (char_length(product_description) BETWEEN 10 AND 2000),
    
    -- 业务约束：错误信息长度限制（防止恶意填充）
    CONSTRAINT ck_tasks_error_length
        CHECK (error_message IS NULL OR char_length(error_message) <= 1000),
    
    -- 业务约束：完成时间必须晚于创建时间
    CONSTRAINT ck_tasks_completed_after_created 
        CHECK (completed_at IS NULL OR completed_at >= created_at),
    
    -- 业务约束：完成状态的一致性
    CONSTRAINT ck_tasks_completion_consistency 
        CHECK (
            (status = 'completed' AND completed_at IS NOT NULL) OR
            (status != 'completed' AND completed_at IS NULL)
        )
);

-- 索引策略（基于实际查询模式设计）

-- 最重要：多租户查询优化
CREATE INDEX ix_tasks_user_status ON tasks (user_id, status);

-- 历史查询：按用户和创建时间排序
CREATE INDEX ix_tasks_user_created ON tasks (user_id, created_at DESC);

-- 系统监控：按状态查询所有任务
CREATE INDEX ix_tasks_status ON tasks (status) 
WHERE status IN ('pending', 'processing');

-- 性能优化：只为活跃状态创建条件索引
CREATE INDEX ix_tasks_processing ON tasks (created_at) 
WHERE status = 'processing';

-- 自动更新updated_at字段的触发器
CREATE OR REPLACE FUNCTION update_tasks_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_tasks_updated_at
    BEFORE UPDATE ON tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_tasks_updated_at();

-- 表注释
COMMENT ON TABLE tasks IS '用户分析任务表 - 支持完整生命周期管理和多租户数据隔离';
COMMENT ON COLUMN tasks.id IS '任务唯一标识';
COMMENT ON COLUMN tasks.user_id IS '任务所属用户，实现多租户隔离';
COMMENT ON COLUMN tasks.product_description IS '用户输入的产品描述，10-2000字符';
COMMENT ON COLUMN tasks.status IS '任务状态：pending/processing/completed/failed';
COMMENT ON COLUMN tasks.error_message IS '失败时的错误详情';
COMMENT ON COLUMN tasks.completed_at IS '任务完成时间，只有completed状态时才设置';

-- 输出创建完成信息
DO $$
BEGIN
    RAISE NOTICE '✅ Tasks表创建完成';
    RAISE NOTICE '📋 支持多租户数据隔离和完整生命周期管理';
    RAISE NOTICE '🔍 索引策略基于实际查询模式优化';
    RAISE NOTICE '🛡️  包含完整的业务约束和数据完整性检查';
END$$;