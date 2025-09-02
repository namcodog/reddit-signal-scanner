-- Reddit Signal Scanner - 枚举类型定义
-- 基于 Linus 原则：消除特殊情况，只有4个清晰的状态

-- 确保在正确的模式中
SET search_path TO signal_scanner, public;

-- 任务状态枚举（核心状态机）
CREATE TYPE task_status AS ENUM (
    'pending',      -- 已创建，等待处理 
    'processing',   -- 正在分析中
    'completed',    -- 分析完成
    'failed'        -- 分析失败
);

-- 输出枚举创建完成信息
DO $$
BEGIN
    RAISE NOTICE '✅ 枚举类型创建完成：task_status';
    RAISE NOTICE '📋 支持状态：pending → processing → completed/failed';
    RAISE NOTICE '🔄 状态机设计遵循Linus简单性原则';
END$$;