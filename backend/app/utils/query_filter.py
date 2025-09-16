"""Reddit Signal Scanner - 查询过滤器工具模块

Linus设计原则："工具函数与数据结构分离"
- 提供纯函数式的查询过滤工具
- 配合Session Events使用，不直接操作数据库
- 高级查询场景的辅助函数
- 简化开发者的租户过滤需求
"""

import logging
from typing import Any, Dict, List, Optional, Type, Union
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from ..core.sqlalchemy_typing import as_bool_clause
from ..core.tenant_isolation import (
    TENANT_AWARE_MODELS,
    TenantContext,
    get_current_tenant_context,
    verify_tenant_access,
)
from ..models.base import Base
from ..models.task import Task

# User 模型在本模块未直接使用，保留按需导入

# 日志记录器
_logger = logging.getLogger(__name__)


def create_tenant_filtered_query(
    model_class: Type[Base],
    tenant_context: Optional[TenantContext] = None,
) -> Select[Any]:
    """
    创建带有租户过滤的查询

    这个函数主要用于高级查询场景，
    在大多数情况下，Session Events会自动处理过滤。

    Args:
        model_class: 模型类
        tenant_context: 租户上下文（可选）

    Returns:
        Select: 带有租户过滤的查询对象
    """
    query: Select[Any] = select(model_class)

    # 获取租户上下文
    if tenant_context is None:
        tenant_context = get_current_tenant_context()

    # 如果没有租户上下文或是系统用户，返回原始查询
    if not tenant_context or not tenant_context.should_filter:
        return query

    # 添加租户过滤条件
    filter_condition = _get_tenant_filter_for_model(
        model_class,
        tenant_context,
    )

    if filter_condition is not None:
        query = query.where(filter_condition)

    return query


def _get_tenant_filter_for_model(
    model_class: Type[Base], tenant_context: TenantContext
) -> Optional[Any]:
    """获取模型的租户过滤条件"""
    if model_class == Task:
        return Task.user_id == tenant_context.user_uuid
    # User模型不需要过滤，因为它本身就是租户表
    return None


def get_user_tasks(
    user_id: Optional[Union[str, UUID]] = None, status: Optional[str] = None
) -> Select[Any]:
    """
    获取用户任务查询 - 示例函数

    这个函数展示了如何与租户过滤系统配合使用。
    在正常情况下，Session Events会自动处理租户过滤。

    Args:
        user_id: 用户ID（可选，由租户上下文提供）
        status: 任务状态过滤

    Returns:
        Select: 任务查询对象
    """
    query: Select[Any] = select(Task)

    # 状态过滤
    if status:
        query = query.where(Task.status == status)

    # 排序：最新的任务在前
    query = query.order_by(Task.created_at.desc())

    # Session Events会自动添加user_id过滤
    return query


def get_user_task_by_id(
    task_id: Union[str, UUID], user_id: Optional[Union[str, UUID]] = None
) -> Select[Any]:
    """
    根据ID获取用户任务

    Args:
        task_id: 任务ID
        user_id: 用户ID（可选）

    Returns:
        Select: 任务查询对象
    """
    query: Select[Any] = select(Task).where(Task.id == task_id)

    # Session Events会自动添加user_id过滤
    return query


def get_tasks_with_pagination(
    offset: int = 0, limit: int = 50, status: Optional[str] = None
) -> Select[Any]:
    """
    分页获取任务

    Args:
        offset: 偏移量
        limit: 数量限制
        status: 状态过滤

    Returns:
        Select: 分页任务查询
    """
    query: Select[Any] = select(Task)

    if status:
        query = query.where(Task.status == status)

    # 排序和分页
    query = query.order_by(Task.created_at.desc()).offset(offset).limit(limit)

    return query


def count_user_tasks(status: Optional[str] = None) -> Select[Any]:
    """
    统计用户任务数量

    Args:
        status: 状态过滤

    Returns:
        Select: 统计查询
    """
    # func 在本函数中未使用，避免无用导入
    query: Select[Any] = select(Task.id)

    if status:
        query = query.where(Task.status == status)

    # Session Events会自动添加user_id过滤
    return query


# 高级查询工具
def build_complex_task_query(
    statuses: Optional[List[str]] = None,
    created_after: Optional[str] = None,
    created_before: Optional[str] = None,
    search_term: Optional[str] = None,
) -> Select[Any]:
    """
    构建复杂的任务查询

    展示如何在复杂查询中使用租户过滤系统。

    Args:
        statuses: 状态列表
        created_after: 创建时间起始
        created_before: 创建时间结束
        search_term: 搜索关键词

    Returns:
        Select: 复杂查询对象
    """
    from datetime import datetime

    # func 在本函数中未使用，避免无用导入
    query: Select[Any] = select(Task)
    conditions: List[Any] = []

    # 状态过滤
    if statuses:
        conditions.append(as_bool_clause(Task.status.in_(statuses)))

    # 时间范围过滤
    if created_after:
        try:
            after_date = datetime.fromisoformat(created_after)
            conditions.append(as_bool_clause(Task.created_at >= after_date))
        except ValueError:
            _logger.warning(f"无效的日期格式: {created_after}")

    if created_before:
        try:
            before_date = datetime.fromisoformat(created_before)
            conditions.append(as_bool_clause(Task.created_at <= before_date))
        except ValueError:
            _logger.warning(f"无效的日期格式: {created_before}")

    # 全文搜索
    if search_term:
        conditions.append(
            as_bool_clause(Task.product_description.ilike(f"%{search_term}%"))
        )

    # 应用所有条件
    if conditions:
        query = query.where(and_(*conditions))

    # 排序
    query = query.order_by(Task.created_at.desc())

    return query


# 租户安全检查工具
async def safe_get_task(
    session: AsyncSession,
    task_id: Union[str, UUID],
    user_id: Optional[Union[str, UUID]] = None,
) -> Optional[Task]:
    """
    安全地获取任务，包含租户检查

    这个函数展示了在Session Events之外的额外安全检查。

    Args:
        session: 数据库会话
        task_id: 任务ID
        user_id: 用户ID（可选）

    Returns:
        Optional[Task]: 任务对象或None
    """
    # 使用正常查询，Session Events会自动应用租户过滤
    result = await session.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if task is None:
        return None

    # 额外的安全检查
    if not verify_tenant_access(task, user_id):
        _logger.warning(
            (
                f"租户访问被拒绝: task_id={task_id}, "
                f"task_user_id={task.user_id}, requested_user_id={user_id}"
            )
        )
        return None

    return task


def get_tenant_aware_models() -> List[Type[Base]]:
    """获取所有租户识别模型列表"""
    return list(TENANT_AWARE_MODELS)


def is_tenant_aware_model(model_class: Type[Base]) -> bool:
    """判断模型是否为租户识别模型"""
    return model_class in TENANT_AWARE_MODELS


# 查询统计工具
def get_tenant_query_stats() -> Dict[str, Any]:
    """
    获取租户查询统计信息

    用于调试和监控租户过滤系统的运行状态。

    Returns:
        dict: 统计信息
    """
    tenant_context = get_current_tenant_context()

    return {
        "tenant_context_active": tenant_context is not None,
        "user_id": tenant_context.user_id if tenant_context else None,
        "tenant_id": tenant_context.tenant_id if tenant_context else None,
        "is_system_user": tenant_context.is_system if tenant_context else False,
        "filtering_enabled": (
            tenant_context.should_filter if tenant_context else False
        ),
        "tenant_aware_models": len(TENANT_AWARE_MODELS),
        "models": [cls.__name__ for cls in TENANT_AWARE_MODELS],
    }


# ====================================================================
# 公开API
# ====================================================================

__all__ = [
    "create_tenant_filtered_query",
    "get_user_tasks",
    "get_user_task_by_id",
    "get_tasks_with_pagination",
    "count_user_tasks",
    "build_complex_task_query",
    "safe_get_task",
    "get_tenant_aware_models",
    "is_tenant_aware_model",
    "get_tenant_query_stats",
]
