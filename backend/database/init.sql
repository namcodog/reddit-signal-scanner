-- Reddit Signal Scanner - 数据库初始化脚本
-- 基于 Linus Torvalds 设计原则：简单、可靠、高性能
-- 遵循 PRD-01 多租户架构要求

-- 启用必需的PostgreSQL扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- 设置基本数据库配置（优化JSONB性能）
ALTER SYSTEM SET shared_buffers = '512MB';
ALTER SYSTEM SET effective_cache_size = '2GB';
ALTER SYSTEM SET work_mem = '8MB';
ALTER SYSTEM SET gin_pending_list_limit = '4MB';

-- 设置连接和超时配置
ALTER SYSTEM SET statement_timeout = '30s';
ALTER SYSTEM SET idle_in_transaction_session_timeout = '60s';

-- 重新加载配置
SELECT pg_reload_conf();

-- 创建专用模式用于信号扫描系统
CREATE SCHEMA IF NOT EXISTS signal_scanner;
SET search_path TO signal_scanner, public;

-- 输出初始化完成信息
DO $$
BEGIN
    RAISE NOTICE '✅ Reddit Signal Scanner 数据库初始化完成';
    RAISE NOTICE '📊 已启用扩展: uuid-ossp, btree_gin';
    RAISE NOTICE '⚙️  性能配置已优化（JSONB查询友好）';
    RAISE NOTICE '🔒 连接超时和安全设置已配置';
    RAISE NOTICE '📁 模式 signal_scanner 已创建';
END$$;