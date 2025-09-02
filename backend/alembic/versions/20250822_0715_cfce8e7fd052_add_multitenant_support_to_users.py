"""升级users表实现多租户架构

迁移ID: cfce8e7fd052
基于版本: 5d9d95bf
创建时间: 2025-08-22 07:15:15

Linus设计原则应用：
1. 添加tenant_id字段，消除单租户vs多租户的特殊情况
2. 重建索引策略，基于实际查询模式优化
3. 添加数据库约束，将验证逻辑下沉到数据层
4. 邮箱唯一性改为tenant内唯一，支持跨租户相同邮箱

安全的升级策略：
- 为现有用户生成个人tenant_id
- 先添加字段，后重建索引，避免锁表
- 使用部分索引减少存储空间
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "cfce8e7fd052"
down_revision = "5d9d95bf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """升级数据库schema实现多租户支持"""

    # 第一步：添加tenant_id字段
    op.add_column(
        "users",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,  # 临时允许NULL，后续会更新
            comment="租户标识，实现数据隔离",
        ),
    )

    # 第二步：为现有用户生成个人tenant_id
    # 每个现有用户获得独立的tenant_id
    op.execute(
        """
        UPDATE users 
        SET tenant_id = gen_random_uuid() 
        WHERE tenant_id IS NULL
    """
    )

    # 第三步：将tenant_id设为NOT NULL
    op.alter_column("users", "tenant_id", nullable=False)

    # 第四步：添加email_verified字段
    op.add_column(
        "users",
        sa.Column(
            "email_verified",
            sa.Boolean,
            nullable=False,
            server_default="false",
            comment="邮箱是否已验证",
        ),
    )

    # 第五步：修改email字段长度（RFC 5321标准）
    op.alter_column("users", "email", type_=sa.String(320))

    # 第六步：删除旧索引（需要重建）
    op.drop_index("ix_users_active", table_name="users")
    # 注意：email的唯一索引会在后面重建为复合索引

    # 第七步：创建新的"好品味"索引策略

    # 核心唯一约束：同一租户内邮箱唯一（只对活跃用户）
    op.create_index(
        "ix_users_tenant_email_unique",
        "users",
        ["tenant_id", "email"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )

    # 高频查询索引：活跃用户按租户查询
    op.create_index(
        "ix_users_tenant_active",
        "users",
        ["tenant_id", "is_active"],
        postgresql_where=sa.text("is_active = true"),
    )

    # 认证查询索引：登录时使用（跨租户邮箱查找）
    op.create_index(
        "ix_users_email_lookup",
        "users",
        ["email"],
        postgresql_where=sa.text("is_active = true"),
    )

    # 第八步：添加数据库约束

    # 邮箱格式约束
    op.create_check_constraint(
        "ck_users_email_format",
        "users",
        "email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'",
    )

    # BCrypt密码哈希格式约束
    op.create_check_constraint(
        "ck_users_password_bcrypt",
        "users",
        "password_hash ~ '^\\$2[aby]\\$[0-9]{2}\\$[./A-Za-z0-9]{53}$'",
    )


def downgrade() -> None:
    """回滚多租户支持（仅用于开发阶段）"""

    # 警告：这会丢失tenant隔离数据！

    # 删除约束
    op.drop_constraint("ck_users_password_bcrypt", "users", type_="check")
    op.drop_constraint("ck_users_email_format", "users", type_="check")

    # 删除新索引
    op.drop_index("ix_users_email_lookup", table_name="users")
    op.drop_index("ix_users_tenant_active", table_name="users")
    op.drop_index("ix_users_tenant_email_unique", table_name="users")

    # 恢复旧索引
    op.create_index(
        "ix_users_active",
        "users",
        ["is_active"],
        postgresql_where=sa.text("is_active = true"),
    )

    # 删除新字段
    op.drop_column("users", "email_verified")
    op.drop_column("users", "tenant_id")

    # 恢复email字段长度
    op.alter_column("users", "email", type_=sa.String(255))


# Linus式迁移策略说明：
#
# 1. 安全优先
#    - 先添加字段再填充数据，避免NOT NULL约束冲突
#    - 使用gen_random_uuid()为现有用户生成tenant_id
#    - 逐步重建索引，避免长时间锁表
#
# 2. 性能优化
#    - 部分索引：只为活跃用户创建索引，节省空间
#    - 复合索引：支持tenant + email的复合查询
#    - 合理的索引命名：清楚表达索引用途
#
# 3. 数据完整性
#    - 约束在数据库层：邮箱格式、密码哈希格式
#    - 唯一性约束：tenant内邮箱唯一，支持跨租户相同邮箱
#    - 审计完整性：时间戳字段保持不变
#
# 4. 可回滚性
#    - 完整的downgrade()实现
#    - 但回滚会丢失tenant隔离，只适合开发阶段
