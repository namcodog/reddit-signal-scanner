"""创建users表实现多租户基础

迁移ID: 002_create_users
基于版本: 001_init_database
创建时间: 2025-08-22

Linus架构原则应用：
- 数据结构决定一切：tenant_id从第一天存在
- 消除特殊情况：个人用户=单用户租户
- 索引基于查询模式：支持高频查询优化
- 约束在数据库层：邮箱格式、密码哈希验证
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "002_create_users"
down_revision = "001_init_database"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建users表 - 多租户架构基础"""

    # 创建用户表
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            comment="用户唯一标识符",
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            comment="租户ID，个人用户=单用户租户",
        ),
        sa.Column("email", sa.String(320), nullable=False, comment="用户邮箱地址，租户内唯一"),
        sa.Column(
            "password_hash", sa.String(255), nullable=False, comment="BCrypt密码哈希值"
        ),
        sa.Column(
            "email_verified",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="邮箱是否已验证",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            comment="用户是否激活（软删除支持）",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="用户创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="用户信息最后更新时间",
        ),
        # 数据库约束：保证数据质量
        sa.CheckConstraint(
            "email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'",
            name="ck_users_email_format",
        ),
        sa.CheckConstraint(
            "password_hash ~ '^\\$2[aby]\\$[0-9]{2}\\$[./A-Za-z0-9]{53}$'",
            name="ck_users_password_bcrypt",
        ),
        comment="用户表 - 多租户架构基础，所有用户数据通过tenant_id隔离",
    )

    # 核心索引：基于实际查询模式

    # 1. 租户内邮箱唯一性（支持软删除）
    op.create_index(
        "ix_users_tenant_email_unique",
        "users",
        ["tenant_id", "email"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )

    # 2. 活跃用户按租户查询（高频查询优化）
    op.create_index(
        "ix_users_tenant_active",
        "users",
        ["tenant_id", "is_active"],
        postgresql_where=sa.text("is_active = true"),
    )

    # 3. 认证查询索引（登录时使用）
    op.create_index(
        "ix_users_email_lookup",
        "users",
        ["email"],
        postgresql_where=sa.text("is_active = true"),
    )

    # 4. 租户查询索引（数据隔离性能保证）
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    # 创建updated_at自动更新触发器
    op.execute(
        """
    CREATE OR REPLACE FUNCTION update_updated_at_column()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = CURRENT_TIMESTAMP;
        RETURN NEW;
    END;
    $$ language 'plpgsql';
    """
    )

    op.execute(
        """
    CREATE TRIGGER update_users_updated_at 
        BEFORE UPDATE ON users 
        FOR EACH ROW 
        EXECUTE FUNCTION update_updated_at_column();
    """
    )


def downgrade() -> None:
    """回滚users表创建"""

    # 删除触发器和函数
    op.execute("DROP TRIGGER IF EXISTS update_users_updated_at ON users;")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")

    # 删除索引（表删除时会自动删除，但明确列出用于文档）
    op.drop_index("ix_users_tenant_id", table_name="users")
    op.drop_index("ix_users_email_lookup", table_name="users")
    op.drop_index("ix_users_tenant_active", table_name="users")
    op.drop_index("ix_users_tenant_email_unique", table_name="users")

    # 删除用户表
    op.drop_table("users")
