"""
用户上下文管理 - 安全的用户身份管理
修复signal-validator发现的硬编码用户ID问题

基于Linus设计哲学：
1. 简单胜过聪明 - 统一的用户上下文接口
2. 安全第一 - 严格的用户身份验证和隔离
3. 配置驱动 - 通过配置控制默认行为
4. 向前兼容 - 平滑的迁移路径
"""

import logging
import uuid
from typing import Any, Callable, Dict, Optional, TypeVar
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from .types import JsonValue

logger = logging.getLogger(__name__)


class UserContext:
    """
    用户上下文管理器

    提供统一的用户身份管理，替代硬编码的默认用户ID
    """

    # 系统预定义用户（用于向后兼容）
    SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"
    ANONYMOUS_USER_ID = "00000000-0000-0000-0000-000000000002"

    def __init__(
        self,
        user_id: Optional[str] = None,
        is_anonymous: bool = True,
        user_data: Optional[dict[str, JsonValue]] = None,
    ):
        """
        初始化用户上下文

        Args:
            user_id: 用户ID，None时使用匿名用户
            is_anonymous: 是否为匿名用户
            user_data: 额外的用户数据
        """
        self._user_id = user_id
        self._is_anonymous = is_anonymous
        self._user_data = user_data or {}

        # 如果没有提供user_id，使用系统默认
        if not self._user_id:
            self._user_id = (
                self.ANONYMOUS_USER_ID if is_anonymous else self.SYSTEM_USER_ID
            )

    @property
    def user_id(self) -> str:
        """获取用户ID"""
        # 确保返回值不为None，如果是None则使用默认值
        if self._user_id is None:
            return self.ANONYMOUS_USER_ID
        return self._user_id

    @property
    def user_uuid(self) -> UUID:
        """获取用户UUID对象"""
        return UUID(self._user_id)

    @property
    def is_anonymous(self) -> bool:
        """是否为匿名用户"""
        return self._is_anonymous

    @property
    def is_system_user(self) -> bool:
        """是否为系统用户"""
        return self._user_id == self.SYSTEM_USER_ID

    @property
    def user_data(self) -> dict[str, JsonValue]:
        """获取用户数据"""
        return self._user_data.copy()

    def has_permission(self, resource: str, action: str) -> bool:
        """
        检查用户权限（简化版本）

        Args:
            resource: 资源名称
            action: 操作类型

        Returns:
            bool: 是否有权限
        """
        # 系统用户拥有所有权限
        if self.is_system_user:
            return True

        # 匿名用户只能创建和查看自己的任务
        if self.is_anonymous:
            return resource == "task" and action in ["create", "read"]

        # 其他情况需要实现具体的权限系统
        return True

    def can_access_task(self, task_user_id: str) -> bool:
        """
        检查是否可以访问指定用户的任务

        Args:
            task_user_id: 任务所属用户ID

        Returns:
            bool: 是否可以访问
        """
        # 系统用户可以访问所有任务
        if self.is_system_user:
            return True

        # 用户只能访问自己的任务
        return str(self._user_id) == str(task_user_id)

    def to_dict(self) -> dict[str, JsonValue]:
        """转换为字典格式"""
        return {
            "user_id": self._user_id,
            "is_anonymous": self._is_anonymous,
            "is_system_user": self.is_system_user,
            "user_data": self._user_data,
        }

    def __str__(self) -> str:
        """字符串表示"""
        user_type = (
            "system"
            if self.is_system_user
            else "anonymous"
            if self.is_anonymous
            else "user"
        )
        return f"UserContext({self._user_id}, {user_type})"


class UserContextManager:
    """
    用户上下文管理器

    提供用户上下文的创建、验证和管理功能
    """

    @staticmethod
    def create_anonymous_user() -> UserContext:
        """
        创建匿名用户上下文

        用于无需认证的场景，如公开API

        Returns:
            UserContext: 匿名用户上下文
        """
        return UserContext(
            user_id=UserContext.ANONYMOUS_USER_ID,
            is_anonymous=True,
            user_data={
                "type": "anonymous",
                "permissions": ["task:create", "task:read"],
            },
        )

    @staticmethod
    def create_system_user() -> UserContext:
        """
        创建系统用户上下文

        用于系统内部操作，如定时任务、维护任务等

        Returns:
            UserContext: 系统用户上下文
        """
        return UserContext(
            user_id=UserContext.SYSTEM_USER_ID,
            is_anonymous=False,
            user_data={"type": "system", "permissions": ["*"]},
        )

    @staticmethod
    def create_authenticated_user(
        user_id: str, user_data: Optional[dict[str, JsonValue]] = None
    ) -> UserContext:
        """
        创建认证用户上下文

        用于已认证的真实用户

        Args:
            user_id: 用户ID
            user_data: 用户数据

        Returns:
            UserContext: 认证用户上下文
        """
        if not user_id or user_id.strip() == "":
            raise ValueError("user_id不能为空")

        # 验证UUID格式
        try:
            UUID(user_id)
        except ValueError:
            raise ValueError(f"无效的用户ID格式: {user_id}")

        return UserContext(
            user_id=user_id,
            is_anonymous=False,
            user_data=user_data or {"type": "authenticated"},
        )

    @staticmethod
    async def verify_user_exists(user_id: str, db: AsyncSession) -> bool:
        """
        验证用户是否存在（占位符实现）

        Args:
            user_id: 用户ID
            db: 数据库会话

        Returns:
            bool: 用户是否存在
        """
        # TODO: 实现真实的用户验证逻辑
        # 当前版本返回True以保持向后兼容

        # 系统预定义用户总是存在
        if user_id in [UserContext.SYSTEM_USER_ID, UserContext.ANONYMOUS_USER_ID]:
            return True

        # 其他用户ID的验证逻辑
        try:
            UUID(user_id)
            return True  # 暂时认为所有有效UUID格式的用户都存在
        except ValueError:
            return False


# 全局用户上下文（线程安全的上下文变量）
from contextvars import ContextVar

current_user_context: ContextVar[Optional[UserContext]] = ContextVar(
    "current_user_context", default=None
)


def get_current_user_context() -> UserContext:
    """
    获取当前用户上下文

    Returns:
        UserContext: 当前用户上下文

    Raises:
        HTTPException: 如果没有设置用户上下文
    """
    context = current_user_context.get()
    if context is None:
        # 默认使用匿名用户上下文
        logger.warning("没有设置用户上下文，使用匿名用户")
        return UserContextManager.create_anonymous_user()

    return context


def set_current_user_context(context: UserContext) -> None:
    """
    设置当前用户上下文

    Args:
        context: 用户上下文
    """
    current_user_context.set(context)


# FastAPI依赖函数
async def get_user_context() -> UserContext:
    """
    FastAPI依赖函数：获取用户上下文

    用于依赖注入，确保每个请求都有用户上下文

    Returns:
        UserContext: 当前请求的用户上下文
    """
    return get_current_user_context()


async def get_anonymous_user_context() -> UserContext:
    """
    FastAPI依赖函数：获取匿名用户上下文

    用于不需要认证的公开端点

    Returns:
        UserContext: 匿名用户上下文
    """
    return UserContextManager.create_anonymous_user()


async def get_system_user_context() -> UserContext:
    """
    FastAPI依赖函数：获取系统用户上下文

    用于系统内部操作

    Returns:
        UserContext: 系统用户上下文
    """
    return UserContextManager.create_system_user()


T = TypeVar("T")


# 装饰器：设置用户上下文
def with_user_context(
    user_context: UserContext,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    装饰器：为函数设置用户上下文

    Args:
        user_context: 要设置的用户上下文
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args: Any, **kwargs: Any) -> T:
            # 保存原有上下文
            old_context = current_user_context.get()

            try:
                # 设置新上下文
                set_current_user_context(user_context)
                return func(*args, **kwargs)
            finally:
                # 恢复原有上下文
                if old_context is not None:
                    current_user_context.set(old_context)
                else:
                    # 清除上下文
                    current_user_context.set(None)

        return wrapper

    return decorator
