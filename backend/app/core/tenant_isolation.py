"""Reddit Signal Scanner - 多租户数据隔离核心模块

Linus设计原则："数据结构决定一切 + 消除特殊情况"
- 使用SQLAlchemy Session Events实现自动过滤
- 基于context7最佳实践：do_orm_execute + with_loader_criteria
- 租户上下文统一管理，零特殊情况
- 只在有租户上下文时激活过滤，系统用户不受限制
"""

import logging
from contextvars import ContextVar
from types import TracebackType
from typing import Any, ContextManager, Optional, Set, Type, Union, cast
from uuid import UUID

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, with_loader_criteria
from sqlalchemy.sql.elements import ColumnElement

from ..models.base import Base
from ..models.task import Task
from .user_context import UserContext, get_current_user_context

# 日志记录器
_logger = logging.getLogger(__name__)

# 租户上下文存储（请求级别）
_tenant_context: ContextVar[Optional["TenantContext"]] = ContextVar(
    "tenant_context", default=None
)

# 需要进行租户隔离的模型类列表
TENANT_AWARE_MODELS: Set[Type[Base]] = {
    Task,  # 任务通过user_id实现租户隔离
    # User, # User模型不需要隔离，因为它本身就是租户表
}


class TenantContext:
    """
    租户上下文管理器

    基于Linus原则：数据结构决定一切
    - tenant_id始终存在，消除NULL判断特殊情况
    - user_id用于实际的数据过滤（多租户通过用户实现）
    - is_system标识系统用户，系统用户不受租户限制
    """

    def __init__(
        self,
        user_id: Union[str, UUID],
        tenant_id: Union[str, UUID],
        is_system: bool = False,
    ):
        self.user_id = str(user_id) if user_id else None
        self.tenant_id = str(tenant_id) if tenant_id else None
        self.is_system = is_system

    def __str__(self) -> str:
        return (
            f"TenantContext(user={self.user_id}, "
            f"tenant={self.tenant_id}, system={self.is_system})"
        )

    @property
    def user_uuid(self) -> Optional[UUID]:
        """UUID格式的用户ID"""
        return UUID(self.user_id) if self.user_id else None

    @property
    def tenant_uuid(self) -> Optional[UUID]:
        """UUID格式的租户ID"""
        return UUID(self.tenant_id) if self.tenant_id else None

    @property
    def should_filter(self) -> bool:
        """是否应该进行租户过滤"""
        # 系统用户不受租户限制
        if self.is_system:
            return False
        # 必须有user_id才进行过滤
        return bool(self.user_id)


def get_current_tenant_context() -> Optional[TenantContext]:
    """获取当前租户上下文"""
    return _tenant_context.get()


def set_tenant_context(tenant_context: Optional[TenantContext]) -> None:
    """设置租户上下文"""
    _tenant_context.set(tenant_context)


def create_tenant_context_from_user(
    user_context: UserContext,
) -> TenantContext:
    """
    从用户上下文创建租户上下文

    在多租户架构中，每个用户属于一个租户，
    通过user_id实现数据隔离。
    """
    # 在当前实现中，user_id 即 tenant_id
    return TenantContext(
        user_id=user_context.user_id,
        tenant_id=user_context.user_id,
        is_system=user_context.is_system_user,
    )


def should_apply_tenant_filter(entity: Any) -> bool:
    """
    判断实体是否需要应用租户过滤

    Args:
        entity: SQLAlchemy实体类或实例

    Returns:
        bool: 是否需要过滤
    """
    if entity is None:
        return False

    # 获取实体类
    entity_class = entity if isinstance(entity, type) else type(entity)

    # 检查是否在租户识别模型列表中
    return entity_class in TENANT_AWARE_MODELS


def get_tenant_filter_criterion(
    entity_class: Type[Base],
) -> Optional[ColumnElement[bool]]:
    """
    获取租户过滤条件

    Args:
        entity_class: 实体类

    Returns:
        SQLAlchemy过滤条件
    """
    tenant_context = get_current_tenant_context()

    if not tenant_context or not tenant_context.should_filter:
        return None

    # 不同模型的过滤策略
    if entity_class == Task:
        # Task模型通过user_id进行租户隔离
        return Task.user_id == tenant_context.user_uuid

    # 默认情况：无过滤
    return None


def setup_tenant_isolation(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    为会话工厂设置租户隔离

    使用SQLAlchemy Session Events的现代方法：
    - 监听do_orm_execute事件
    - 使用with_loader_criteria自动添加过滤条件

    基于Context7 SQLAlchemy最佳实践。
    """

    # 兼容SQLAlchemy版本：优先在 Session 类上注册 do_orm_execute，以避免 async_sessionmaker 没有该事件的问题
    target = Session

    @event.listens_for(target, "do_orm_execute")
    def _apply_tenant_filter(orm_execute_state: Any) -> None:
        """
        为所有ORM查询自动应用租户过滤

        基于Context7的SQLAlchemy最佳实践：
        - 只在SELECT语句时应用过滤
        - 不影响列加载和关系加载
        - 使用with_loader_criteria添加全局WHERE条件
        """
        # 只处理SELECT查询，不处理列加载和关系加载
        if (
            not orm_execute_state.is_select
            or orm_execute_state.is_column_load
            or orm_execute_state.is_relationship_load
        ):
            return

        # 获取当前租户上下文
        tenant_context = get_current_tenant_context()
        if not tenant_context or not tenant_context.should_filter:
            return

        # 为所有租户识别模型添加过滤条件
        for entity_class in TENANT_AWARE_MODELS:
            filter_criterion = get_tenant_filter_criterion(entity_class)
            if filter_criterion is not None:
                stmt = orm_execute_state.statement
                orm_execute_state.statement = stmt.options(
                    with_loader_criteria(entity_class, filter_criterion)
                )

        _logger.debug(
            "租户过滤已应用: user_id=%s",
            tenant_context.user_id,
        )

    _logger.info("✅ 租户隔离事件监听器已注册（SQLAlchemy Session.do_orm_execute）")


def with_tenant_context(
    user_context: UserContext,
) -> ContextManager[TenantContext]:
    """
    上下文管理器：设置租户上下文

    Usage:
        async with with_tenant_context(user_context) as tenant_ctx:
            # 在此块内，所有数据库查询都会自动应用租户过滤
            tasks = await session.execute(select(Task))
    """
    tenant_context = create_tenant_context_from_user(user_context)

    class TenantContextManager:
        def __enter__(self) -> TenantContext:
            set_tenant_context(tenant_context)
            return tenant_context

        def __exit__(
            self,
            exc_type: Optional[Type[BaseException]],
            exc_val: Optional[BaseException],
            exc_tb: Optional[TracebackType],
        ) -> None:
            set_tenant_context(None)

    return TenantContextManager()


def ensure_tenant_context() -> TenantContext:
    """
    确保租户上下文存在，如果不存在则从用户上下文创建

    Returns:
        TenantContext: 租户上下文

    Raises:
        ValueError: 如果无法获取或创建租户上下文
    """
    tenant_context = get_current_tenant_context()

    if tenant_context is None:
        # 尝试从用户上下文创建
        user_context = get_current_user_context()
        if user_context is None:
            raise ValueError("无法获取用户或租户上下文")

        tenant_context = create_tenant_context_from_user(user_context)
        set_tenant_context(tenant_context)

    return tenant_context


# 安全检查函数
def verify_tenant_access(
    entity: Any, required_user_id: Optional[Union[str, UUID]] = None
) -> bool:
    """
    验证当前用户是否可以访问指定实体

    Args:
        entity: 要验证的实体
        required_user_id: 需要的用户ID（可选）

    Returns:
        bool: 是否可以访问
    """
    tenant_context = get_current_tenant_context()

    # 系统用户可以访问所有数据
    if tenant_context and tenant_context.is_system:
        return True

    # 无租户上下文，禁止访问
    if not tenant_context or not tenant_context.user_id:
        return False

    # 检查实体所有权
    if hasattr(entity, "user_id"):
        entity_user_id = str(entity.user_id) if entity.user_id else None
        return entity_user_id == tenant_context.user_id

    # 检查指定的用户ID
    if required_user_id:
        return str(required_user_id) == tenant_context.user_id

    # 默认允许访问
    return True


def log_potential_tenant_violation(
    action: str,
    entity: Any,
    current_user_id: Optional[str] = None,
    target_user_id: Optional[str] = None,
) -> None:
    """
    记录潜在的租户违规访问

    Args:
        action: 操作类型
        entity: 相关实体
        current_user_id: 当前用户ID
        target_user_id: 目标用户ID
    """
    tenant_context = get_current_tenant_context()

    current = current_user_id or (tenant_context.user_id if tenant_context else "None")
    entity_name = type(entity).__name__ if entity else "None"

    _logger.warning(
        "⚠️  潜在租户违规: 操作=%s, 当前用户=%s, 目标用户=%s, 实体=%s",
        action,
        current,
        target_user_id,
        entity_name,
    )


# ====================================================================
# 公开API - 供其他模块使用
# ====================================================================

__all__ = [
    "TenantContext",
    "get_current_tenant_context",
    "set_tenant_context",
    "create_tenant_context_from_user",
    "setup_tenant_isolation",
    "with_tenant_context",
    "ensure_tenant_context",
    "verify_tenant_access",
    "log_potential_tenant_violation",
    "TENANT_AWARE_MODELS",
]
