"""
统一任务管理器 - prd04-02核心组件
中央化任务管理，统一任务生命周期控制

基于Linus设计哲学：
1. 统一接口 - 所有任务操作通过一个管理器
2. 简单状态机 - 清晰的任务状态转换
3. 配置驱动 - 所有策略通过配置控制
4. 错误集中处理 - 统一的错误恢复机制
"""

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID

from .types import JsonValue

if TYPE_CHECKING:
    from ..core.user_context import UserContext

from celery.result import AsyncResult
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.celery_app import get_celery_app, get_task_status
from ..core.exceptions import TaskNotFoundError, TaskProducerError
from ..core.sqlalchemy_typing import as_bool_clause
from ..models.task import Task as TaskModel
from ..schemas.task_producer import TaskSubmissionRequest, TaskSubmissionResponse
from ..services.task_producer import TaskProducer, get_task_producer

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """
    任务状态枚举 - 明确的状态定义

    简单的状态机，避免复杂的状态转换逻辑
    """

    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class TaskManager:
    """
    统一任务管理器

    负责任务的完整生命周期管理：
    - 任务创建和提交
    - 状态查询和更新
    - 任务取消和重试
    - 批量操作
    """

    def __init__(self, task_producer: Optional[TaskProducer] = None) -> None:
        """
        初始化任务管理器

        Args:
            task_producer: 任务生产者，用于依赖注入
        """
        self.task_producer = task_producer or get_task_producer()
        self.celery = get_celery_app()

        logger.info("TaskManager初始化完成")

    async def create_task(
        self,
        request: TaskSubmissionRequest,
        db: AsyncSession,
        user_context: Optional["UserContext"] = None,
    ) -> TaskSubmissionResponse:
        """
        创建并提交任务

        这是外部接口的主要入口点，集成了任务生产者的功能

        Args:
            request: 任务创建请求
            db: 数据库会话
            user_context: 用户上下文（修复硬编码用户ID）

        Returns:
            TaskSubmissionResponse: 任务创建响应

        Raises:
            TaskProducerError: 任务创建失败
        """
        logger.info("开始创建任务")

        try:
            response = await self.task_producer.submit_analysis_task(
                request, db, user_context
            )
            logger.info(f"任务创建成功: {response.task_id}")
            return response

        except Exception as e:
            logger.error(f"任务创建失败: {e}", exc_info=True)
            raise TaskProducerError(f"任务创建失败: {e}") from e

    async def get_task(
        self, task_id: str, db: AsyncSession
    ) -> Optional[dict[str, JsonValue]]:
        """
        获取任务详细信息

        结合数据库记录和Celery状态，提供完整的任务信息

        Args:
            task_id: 任务ID
            db: 数据库会话

        Returns:
            Optional[Dict]: 任务信息，如果不存在返回None
        """
        try:
            # 解析为 UUID
            try:
                task_uuid = UUID(task_id)
            except Exception:
                logger.warning(f"无效的任务ID: {task_id}")
                return None

            # 获取数据库记录
            db_task = await db.get(TaskModel, task_uuid)
            if not db_task:
                return None

            # 获取Celery任务状态
            celery_status = self.task_producer.get_task_status(task_id)

            return {
                "task_id": str(db_task.id),
                "user_id": str(db_task.user_id),
                "product_description": db_task.product_description,
                "status": db_task.status,
                "created_at": db_task.created_at.isoformat(),
                "updated_at": db_task.updated_at.isoformat(),
                "celery_status": {
                    "state": celery_status.get("state"),
                    "ready": celery_status.get("ready"),
                    "successful": celery_status.get("successful"),
                    "failed": celery_status.get("failed"),
                },
            }

        except Exception as e:
            logger.error(f"获取任务信息失败 {task_id}: {e}")
            return None

    async def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        db: AsyncSession,
        additional_data: Optional[dict[str, JsonValue]] = None,
    ) -> bool:
        """
        更新任务状态

        Args:
            task_id: 任务ID
            status: 新状态
            db: 数据库会话
            additional_data: 额外数据

        Returns:
            bool: 是否更新成功
        """
        try:
            # 解析为 UUID
            try:
                task_uuid = UUID(task_id)
            except Exception:
                logger.warning(f"无效的任务ID: {task_id}")
                return False

            # 更新数据库记录
            stmt = (
                update(TaskModel)
                .where(as_bool_clause(TaskModel.id == task_uuid))
                .values(status=status.value, updated_at=datetime.now(timezone.utc))
            )

            result = await db.execute(stmt)

            if result.rowcount == 0:
                logger.warning(f"任务不存在，无法更新状态: {task_id}")
                return False

            # 该模型不包含 metadata 字段，additional_data 暂不写库，仅记录日志
            if additional_data:
                logger.debug(
                    "additional_data provided but Task model has no metadata field: %s",
                    list(additional_data.keys()),
                )

            await db.commit()
            logger.debug(f"任务状态已更新: {task_id} -> {status.value}")
            return True

        except Exception as e:
            await db.rollback()
            logger.error(f"更新任务状态失败 {task_id}: {e}")
            return False

    async def cancel_task(self, task_id: str, db: AsyncSession) -> bool:
        """
        取消任务

        Args:
            task_id: 任务ID
            db: 数据库会话

        Returns:
            bool: 是否取消成功
        """
        try:
            # 检查任务是否存在
            task = await db.get(TaskModel, task_id)
            if not task:
                raise TaskNotFoundError(task_id)

            # 检查任务状态是否允许取消
            if task.status in ["completed", "failed", "cancelled"]:
                logger.info(f"任务 {task_id} 状态为 {task.status}，无法取消")
                return False

            # 取消Celery任务
            success = await self.task_producer.cancel_task(task_id, db)

            if success:
                await self.update_task_status(
                    task_id,
                    TaskStatus.CANCELLED,
                    db,
                    {"cancelled_at": datetime.now(timezone.utc).isoformat()},
                )
                logger.info(f"任务已取消: {task_id}")

            return success

        except Exception as e:
            logger.error(f"取消任务失败 {task_id}: {e}")
            return False

    async def list_tasks(
        self,
        db: AsyncSession,
        user_id: Optional[str] = None,
        status: Optional[TaskStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, JsonValue]]:
        """
        列出任务

        Args:
            db: 数据库会话
            user_id: 用户ID过滤
            status: 状态过滤
            limit: 限制数量
            offset: 偏移量

        Returns:
            List[Dict]: 任务列表
        """
        try:
            # 构建查询条件
            conditions = []
            if user_id:
                try:
                    user_uuid = UUID(user_id)
                    conditions.append(as_bool_clause(TaskModel.user_id == user_uuid))
                except Exception:
                    logger.warning(f"无效的用户ID: {user_id}, 忽略该过滤条件")
            if status:
                conditions.append(as_bool_clause(TaskModel.status == status.value))

            # 执行查询
            stmt = (
                select(TaskModel)
                .where(
                    and_(*conditions) if conditions else as_bool_clause(True == True)
                )
                .order_by(TaskModel.created_at.desc())
                .limit(limit)
                .offset(offset)
            )

            result = await db.execute(stmt)
            tasks = result.scalars().all()

            # 转换为字典格式
            task_list: list[dict[str, JsonValue]] = []
            for task in tasks:
                task_list.append(
                    {
                        "task_id": str(task.id),
                        "user_id": str(task.user_id),
                        "product_description": (
                            task.product_description[:100] + "..."
                            if len(task.product_description) > 100
                            else task.product_description
                        ),
                        "status": task.status,
                        "created_at": task.created_at.isoformat(),
                        "updated_at": task.updated_at.isoformat(),
                    }
                )

            logger.debug(f"查询到 {len(task_list)} 个任务")
            return task_list

        except Exception as e:
            logger.error(f"列出任务失败: {e}")
            return []

    async def get_task_statistics(self, db: AsyncSession) -> dict[str, JsonValue]:
        """
        获取任务统计信息

        Args:
            db: 数据库会话

        Returns:
            Dict: 统计信息
        """
        try:
            # 统计各状态的任务数量
            stats = {}
            for status in TaskStatus:
                stmt = select(TaskModel).where(
                    as_bool_clause(TaskModel.status == status.value)
                )
                result = await db.execute(stmt)
                count = len(result.scalars().all())
                stats[status.value] = count

            # 获取队列长度
            from ..core.celery_app import get_active_tasks, get_queue_lengths

            queue_lengths = get_queue_lengths()
            active_tasks = get_active_tasks()

            return {
                "task_counts": stats,
                "queue_lengths": queue_lengths,
                "active_tasks_count": active_tasks.get("total_active", 0),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"获取任务统计失败: {e}")
            return {"error": str(e)}

    async def retry_failed_tasks(
        self, db: AsyncSession, limit: int = 10
    ) -> dict[str, JsonValue]:
        """
        重试失败的任务

        Args:
            db: 数据库会话
            limit: 重试数量限制

        Returns:
            Dict: 重试结果
        """
        try:
            # 查找失败的任务
            stmt = (
                select(TaskModel)
                .where(as_bool_clause(TaskModel.status == TaskStatus.FAILED.value))
                .order_by(TaskModel.updated_at.desc())
                .limit(limit)
            )

            result = await db.execute(stmt)
            failed_tasks = result.scalars().all()

            retry_results = []
            success_count = 0

            for task in failed_tasks:
                try:
                    # 重新提交任务
                    request = TaskSubmissionRequest(
                        product_description=task.product_description, priority=1
                    )

                    response = await self.task_producer.submit_analysis_task(
                        request, db
                    )

                    # 更新原任务状态为已重试
                    await self.update_task_status(
                        str(task.id),
                        TaskStatus.RETRYING,
                        db,
                        {"retry_task_id": response.task_id},
                    )

                    retry_results.append(
                        {
                            "original_task_id": str(task.id),
                            "new_task_id": response.task_id,
                            "status": "retry_submitted",
                        }
                    )

                    success_count += 1

                except Exception as e:
                    logger.error(f"重试任务失败 {task.id}: {e}")
                    retry_results.append(
                        {
                            "original_task_id": str(task.id),
                            "status": "retry_failed",
                            "error": str(e),
                        }
                    )

            return {
                "total_failed_tasks": len(failed_tasks),
                "retry_success_count": success_count,
                "retry_results": retry_results,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"批量重试失败任务异常: {e}")
            return {"error": str(e)}


def get_task_manager() -> TaskManager:
    """
    获取任务管理器实例 - 修复全局单例反模式

    Linus修复：移除全局可变状态，使用依赖注入
    每次调用都创建新实例，避免并发编程噩梦

    Returns:
        TaskManager: 新的任务管理器实例
    """
    # 每次创建新实例，线程安全
    return TaskManager()
