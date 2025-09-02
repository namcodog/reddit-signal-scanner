"""
Reddit Signal Scanner - 用户模型

Linus设计原则: "好品味数据结构 + 消除特殊情况"
- 多租户从第一天就设计正确，避免后续重构地狱
- 索引策略基于实际查询模式，不是理论完美
- 每个字段都有存在的理由，拒绝"可能需要"的字段
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, Column, String, TIMESTAMP, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgreSQL_UUID
from sqlalchemy.sql import func
from .base import Base

from sqlalchemy.orm import relationship


class User(Base):
    """用户模型 - 多租户系统基础

    Linus原则应用:
    1. 数据结构决定一切 - tenant_id始终存在，消除特殊情况
    2. 好品味索引 - 基于实际查询模式设计复合索引
    3. 约束在数据库层 - 不依赖应用层验证
    """

    __tablename__ = "users"

    # 主键：UUID类型，数据库生成
    id: UUID = Column(
        PostgreSQL_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        comment="用户唯一标识",
    )

    # 多租户隔离：永远不为NULL，个人用户使用个人tenant_id
    tenant_id: UUID = Column(
        PostgreSQL_UUID(as_uuid=True),
        nullable=False,
        server_default=func.gen_random_uuid(),  # 个人用户默认生成个人tenant
        comment="租户标识，实现数据隔离",
    )

    # 用户凭证：在tenant内唯一
    email: str = Column(
        String(320),  # RFC 5321标准：64@255+1 = 320
        nullable=False,
        comment="用户邮箱地址",
    )

    password_hash: str = Column(
        String(255),  # BCrypt哈希固定长度60，预留空间
        nullable=False,
        comment="BCrypt密码哈希值",
    )

    # 邮箱验证：简化状态管理
    email_verified: bool = Column(
        Boolean, nullable=False, server_default="false", comment="邮箱是否已验证"
    )

    # 用户状态：活跃用户优先查询
    is_active: bool = Column(
        Boolean, nullable=False, server_default="true", comment="用户是否激活"
    )

    # 审计字段：自动维护，不允许应用修改
    created_at: datetime = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        comment="创建时间",
    )

    updated_at: datetime = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        comment="最后更新时间",
    )

    # 数据库约束：在数据层保证数据完整性
    __table_args__ = (
        # 核心唯一约束：同一租户内邮箱唯一
        Index(
            "ix_users_tenant_email_unique",
            "tenant_id",
            "email",
            unique=True,
            postgresql_where=(Column("is_active") is True),  # 只对活跃用户生效
        ),
        # 高频查询索引：活跃用户按租户查询
        Index(
            "ix_users_tenant_active",
            "tenant_id",
            "is_active",
            postgresql_where=(Column("is_active") is True),
        ),
        # 认证查询索引：登录时使用
        Index(
            "ix_users_email_lookup",
            "email",
            postgresql_where=(Column("is_active") is True),
        ),
        # 邮箱格式约束：数据库层验证
        CheckConstraint(
            "email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'",
            name="ck_users_email_format",
        ),
        # 密码哈希约束：确保BCrypt格式
        CheckConstraint(
            "password_hash ~ '^\\$2[aby]\\$[0-9]{2}\\$[./A-Za-z0-9]{53}$'",
            name="ck_users_password_bcrypt",
        ),
        # 表注释
        {"comment": "用户表 - 多租户架构基础，所有用户数据通过tenant_id隔离"},
    )

    # 关系映射：用户的任务列表
    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        """调试友好的字符串表示"""
        return (
            f"<User(id={self.id}, email={self.email[:20]}..., "
            f"tenant={self.tenant_id}, active={self.is_active})>"
        )

    def __str__(self) -> str:
        """用户友好的字符串表示"""
        return f"{self.email} ({'已激活' if self.is_active else '已停用'})"


# Linus式设计说明:
#
# 1. 数据结构决定一切
#    - tenant_id永远存在，消除了"单租户vs多租户"的特殊情况
#    - 个人用户就是single-user tenant，没有特殊处理逻辑
#
# 2. 索引基于实际查询模式
#    - ix_users_tenant_email_unique: 用户注册/登录
#    - ix_users_tenant_active: 租户用户列表
#    - ix_users_email_lookup: 跨租户邮箱查找（管理功能）
#
# 3. 约束在数据库层
#    - 邮箱格式、密码哈希格式都在数据库层验证
#    - 应用层只需要处理业务逻辑，不需要验证数据格式
#
# 4. 性能优化内置
#    - 部分索引：只为活跃用户创建索引，节省空间
#    - 复合索引：支持最常见的查询模式
#
# 5. 审计自动化
#    - created_at/updated_at由数据库自动维护
#    - 应用层无法篡改审计信息
