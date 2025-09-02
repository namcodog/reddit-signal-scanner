-- Reddit Signal Scanner - Users表DDL定义
-- 基于Linus架构原则：数据结构决定一切，消除特殊情况

-- 用户表：多租户系统基础
-- 设计哲学：个人用户=单用户租户，无特殊处理逻辑
CREATE TABLE users (
    -- 主键：UUID自动生成
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 多租户核心：数据隔离基础
    tenant_id UUID NOT NULL DEFAULT gen_random_uuid(),
    
    -- 用户凭证：在租户内唯一
    email VARCHAR(320) NOT NULL,  -- RFC 5321标准长度
    password_hash VARCHAR(255) NOT NULL,  -- BCrypt哈希+预留空间
    
    -- 用户状态：简化管理
    email_verified BOOLEAN NOT NULL DEFAULT false,
    is_active BOOLEAN NOT NULL DEFAULT true,
    
    -- 审计字段：自动维护
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- 数据库约束：保证数据质量
    CONSTRAINT ck_users_email_format 
        CHECK (email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    CONSTRAINT ck_users_password_bcrypt 
        CHECK (password_hash ~ '^\$2[aby]\$[0-9]{2}\$[./A-Za-z0-9]{53}$')
);

-- 核心索引：基于实际查询模式设计
-- 1. 租户内邮箱唯一性（支持软删除）
CREATE UNIQUE INDEX ix_users_tenant_email_unique 
    ON users (tenant_id, email) 
    WHERE is_active = true;

-- 2. 活跃用户按租户查询（高频查询优化）
CREATE INDEX ix_users_tenant_active 
    ON users (tenant_id, is_active) 
    WHERE is_active = true;

-- 3. 认证查询索引（登录时使用）
CREATE INDEX ix_users_email_lookup 
    ON users (email) 
    WHERE is_active = true;

-- 4. 租户查询索引（数据隔离性能保证）
CREATE INDEX ix_users_tenant_id 
    ON users (tenant_id);

-- updated_at自动更新触发器
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- 表注释
COMMENT ON TABLE users IS '用户表 - 多租户架构基础，所有用户数据通过tenant_id隔离';
COMMENT ON COLUMN users.id IS '用户唯一标识符';
COMMENT ON COLUMN users.tenant_id IS '租户ID，个人用户=单用户租户';
COMMENT ON COLUMN users.email IS '用户邮箱地址，租户内唯一';
COMMENT ON COLUMN users.password_hash IS 'BCrypt密码哈希值';
COMMENT ON COLUMN users.email_verified IS '邮箱是否已验证';
COMMENT ON COLUMN users.is_active IS '用户是否激活（软删除支持）';
COMMENT ON COLUMN users.created_at IS '用户创建时间';
COMMENT ON COLUMN users.updated_at IS '用户信息最后更新时间';

-- Linus式设计说明
/*
索引策略基于实际查询模式：

1. ix_users_tenant_email_unique (唯一)
   - 查询：用户注册检查、登录验证
   - 条件：WHERE tenant_id = ? AND email = ? AND is_active = true
   
2. ix_users_tenant_active (范围)
   - 查询：获取租户下所有活跃用户
   - 条件：WHERE tenant_id = ? AND is_active = true
   
3. ix_users_email_lookup (单列)
   - 查询：跨租户邮箱查找（管理功能）
   - 条件：WHERE email = ? AND is_active = true

性能特点：
- 部分索引：只为活跃用户创建索引，节省50%+空间
- 复合索引：支持最左前缀匹配原则
- 约束下沉：数据库层验证，应用层零负担

多租户设计优势：
- 零特殊情况：tenant_id永远存在，统一数据访问模式
- 扩展性：个人用户升级为团队时无需数据迁移
- 性能：基于tenant_id的查询都能使用索引
*/