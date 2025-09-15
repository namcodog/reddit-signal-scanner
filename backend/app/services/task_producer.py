"""
任务生产者服务 - prd04-02核心实现
将HTTP请求转化为异步Celery任务的桥梁

基于Linus设计哲学：
1. 极简TaskProducer - 无特殊情况分支
2. 统一数据抽象 - TaskData消除类型差异
3. 配置驱动 - 队列选择和参数配置
4. 统一错误处理 - 消除散乱的异常处理
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, Mapping, Optional

if TYPE_CHECKING:
    from ..core.user_context import UserContext

from celery import Celery
from celery.exceptions import Retry, CeleryError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.celery_app import get_celery_app
from ..core.exceptions import DatabaseError, TaskProducerError
from ..models.task import Task as TaskModel
from ..schemas.task_producer import (
    TaskConfig,
    TaskData,
    TaskSubmissionRequest,
    TaskSubmissionResponse,
)

logger = logging.getLogger(__name__)


class TaskProducer:
    """
    极简任务生产者 - 无特殊情况分支的实现

    这是Linus式"好品味"设计的典型例子：
    - 单一职责：只负责任务提交
    - 无条件分支：所有任务类型统一处理
    - 数据结构驱动：通过TaskData统一抽象
    - 配置驱动：队列选择和参数通过配置控制
    """

    def __init__(
        self,
        celery_app: Optional[Celery] = None,
        task_config: Optional[TaskConfig] = None,
    ):
        """
        初始化任务生产者

        Args:
            celery_app: Celery应用实例
            task_config: 任务配置
        """
        self.celery = celery_app or get_celery_app()
        self.config = task_config or TaskConfig.default_config()

        logger.info("TaskProducer初始化完成")

    async def submit_analysis_task(
        self,
        request: TaskSubmissionRequest,
        db: AsyncSession,
        user_context: Optional["UserContext"] = None,
    ) -> TaskSubmissionResponse:
        """
        统一任务提交接口 - 0层特殊情况

        这是核心方法，体现了"消除特殊情况"的设计哲学：
        - 所有任务类型都走同一个提交流程
        - 配置驱动队列选择，无硬编码分支
        - 统一的错误处理机制

        Args:
            request: 任务提交请求
            db: 数据库会话
            user_context: 用户上下文（修复硬编码用户ID）

        Returns:
            TaskSubmissionResponse: 任务提交响应

        Raises:
            TaskProducerError: 任务提交相关错误
            DatabaseError: 数据库操作错误
        """
        logger.info(f"开始提交分析任务，产品描述长度: {len(request.product_description)}")

        try:
            # 获取或设置用户上下文
            if user_context is None:
                from ..core.user_context import get_current_user_context

                user_context = get_current_user_context()

            # 第1步：创建统一任务数据结构
            task_data = TaskData.from_request(
                request=request,
                task_type="analysis",  # 当前版本固定类型，简化设计
                queue_config=self.config.queue_mapping,
            )

            # 第2步：创建数据库任务记录（统一处理）
            db_task = await self._create_task_record(task_data, db, user_context)

            # 第3步：提交Celery任务（统一队列）
            celery_result = await self._submit_celery_task(task_data)

            # 第4步：构建统一响应
            response = TaskSubmissionResponse(
                task_id=task_data.task_id,
                status="queued",
                queue_name=task_data.queue_name,
                estimated_start_time=self._estimate_start_time(task_data.queue_name),
                submitted_at=task_data.created_at,
            )

            logger.info(f"任务提交成功: {task_data.task_id}, 用户: {user_context}")
            return response

        except SQLAlchemyError as e:
            logger.error(f"任务提交失败-数据库: {e}", exc_info=True)
            raise DatabaseError(f"数据库操作失败: {e}") from e
        except (TaskProducerError, Retry, ValueError, RuntimeError, KeyError, TypeError) as e:
            logger.error(f"任务提交失败: {e}", exc_info=True)
            raise TaskProducerError(f"任务提交失败: {e}") from e

    async def _create_task_record(
        self,
        task_data: TaskData,
        db: AsyncSession,
        user_context: Optional["UserContext"] = None,
    ) -> TaskModel:
        """
        创建数据库任务记录 - 统一数据库操作

        Args:
            task_data: 任务数据
            db: 数据库会话
            user_context: 用户上下文（修复硬编码用户ID）

        Returns:
            TaskModel: 创建的任务记录

        Raises:
            DatabaseError: 数据库操作失败
        """
        try:
            # 获取用户上下文，修复hardcoded用户ID问题
            if user_context is None:
                from ..core.user_context import get_current_user_context

                user_context = get_current_user_context()

            # 使用任务数据中的task_id，确保与Celery任务ID一致
            db_task = TaskModel(
                id=task_data.task_id,
                user_id=user_context.user_id,  # 使用真实的用户上下文，而非硬编码
                product_description=task_data.payload["product_description"],
                status="queued",  # 初始状态为已入队
                created_at=task_data.created_at,
                updated_at=task_data.created_at,
                metadata={
                    "priority": task_data.priority,
                    "queue_name": task_data.queue_name,
                    "task_type": task_data.task_type,
                    "user_type": (
                        "system"
                        if user_context.is_system_user
                        else (
                            "anonymous"
                            if user_context.is_anonymous
                            else "authenticated"
                        )
                    ),
                    **task_data.metadata,
                },
            )

            db.add(db_task)
            await db.commit()
            await db.refresh(db_task)

            logger.debug(f"数据库任务记录创建成功: {task_data.task_id}, 用户: {user_context}")
            return db_task

        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"创建任务记录失败: {e}", exc_info=True)
            raise DatabaseError(f"数据库操作失败: {e}") from e

    async def _submit_celery_task(self, task_data: TaskData) -> Any:
        """
        提交Celery任务 - 统一异步任务提交

        Args:
            task_data: 任务数据

        Returns:
            AsyncResult: Celery异步结果

        Raises:
            TaskProducerError: 任务提交失败
        """
        try:
            # 获取Celery任务调用参数
            celery_kwargs = task_data.to_celery_kwargs()

            # 提交任务到指定队列
            celery_result = self.celery.send_task(
                "analysis_tasks.analyze_product", **celery_kwargs
            )

            logger.debug(
                f"Celery任务提交成功: {task_data.task_id}, 队列: {task_data.queue_name}"
            )
            return celery_result

        except (CeleryError, Retry, ValueError, RuntimeError, KeyError, TypeError) as e:
            logger.error(f"Celery任务提交失败: {e}", exc_info=True)
            raise TaskProducerError(f"任务队列提交失败: {e}") from e

    def _estimate_start_time(self, queue_name: str) -> Optional[datetime]:
        """
        估算任务开始时间 - Linus修复：配置化参数

        基于队列当前长度和处理速度预估任务开始时间
        修复前: 硬编码2分钟平均处理时间
        修复后: 从TaskConfig获取配置参数

        Args:
            queue_name: 队列名称

        Returns:
            Optional[datetime]: 预估开始时间
        """
        try:
            # 获取队列长度
            from ..core.celery_app import get_queue_lengths

            queue_lengths = get_queue_lengths()

            current_queue_length = queue_lengths.get(queue_name, 0)

            # 使用配置化的平均任务处理时间
            average_task_duration = self.config.average_task_duration_minutes
            estimated_minutes = current_queue_length * average_task_duration

            if estimated_minutes > 0:
                return datetime.now(timezone.utc) + timedelta(minutes=estimated_minutes)
            else:
                return datetime.now(timezone.utc)  # 立即开始

        except (RuntimeError, ValueError, KeyError, TypeError) as e:
            logger.warning(f"估算任务开始时间失败: {e}")
            return None

    def get_task_status(self, task_id: str) -> "Mapping[str, Any]":
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            Dict: 任务状态信息
        """
        try:
            from ..core.celery_app import get_task_status

            return get_task_status(task_id)
        except (RuntimeError, ValueError) as e:
            logger.error(f"获取任务状态失败 {task_id}: {e}")
            return {"task_id": task_id, "state": "UNKNOWN", "error": str(e)}

    async def cancel_task(self, task_id: str, db: AsyncSession) -> bool:
        """
        取消任务

        Args:
            task_id: 任务ID
            db: 数据库会话

        Returns:
            bool: 是否成功取消
        """
        try:
            # 取消Celery任务
            self.celery.control.revoke(task_id, terminate=True)

            # 更新数据库状态
            task = await db.get(TaskModel, task_id)
            if task:
                task.status = "cancelled"
                task.updated_at = datetime.now(timezone.utc)
                await db.commit()

            logger.info(f"任务已取消: {task_id}")
            return True

        except (CeleryError, SQLAlchemyError, RuntimeError, ValueError) as e:
            logger.error(f"取消任务失败 {task_id}: {e}")
            return False


class TaskProducerFactory:
    """
    任务生产者工厂 - Linus修复：移除单例反模式

    修复前: 全局可变状态 _instance
    修复后: 工厂方法，每次创建新实例
    """

    @classmethod
    def create_default(cls) -> TaskProducer:
        """
        创建默认配置的TaskProducer

        Returns:
            TaskProducer: 新的任务生产者实例
        """
        return TaskProducer()

    @classmethod
    def create_with_config(cls, config: TaskConfig) -> TaskProducer:
        """
        创建带有自定义配置的TaskProducer

        Args:
            config: 任务配置

        Returns:
            TaskProducer: 任务生产者实例
        """
        return TaskProducer(task_config=config)


# 便捷函数，用于依赖注入
def get_task_producer() -> TaskProducer:
    """
    获取任务生产者实例 - Linus修复：移除单例反模式

    用于FastAPI依赖注入，每次创建新实例
    避免全局可变状态导致的并发问题

    Returns:
        TaskProducer: 新的任务生产者实例
    """
    return TaskProducerFactory.create_default()


# 批量任务提交器
class BatchTaskProducer(TaskProducer):
    """
    批量任务生产者

    继承TaskProducer，添加批量提交功能
    """

    async def submit_batch_analysis(
        self, requests: list[TaskSubmissionRequest], batch_id: str, db: AsyncSession
    ) -> Mapping[str, Any]:
        """
        批量提交分析任务

        Args:
            requests: 任务请求列表
            batch_id: 批次ID
            db: 数据库会话

        Returns:
            Dict: 批次提交结果
        """
        logger.info(f"开始批量任务提交，批次: {batch_id}, 任务数量: {len(requests)}")

        results = []
        success_count = 0
        failed_count = 0

        for i, request in enumerate(requests):
            try:
                response = await self.submit_analysis_task(request, db)
                results.append(
                    {
                        "index": i + 1,
                        "task_id": response.task_id,
                        "status": "submitted",
                        "queue_name": response.queue_name,
                    }
                )
                success_count += 1

            except (TaskProducerError, ValueError, RuntimeError) as e:
                logger.error(f"批量任务第{i+1}项提交失败: {e}")
                results.append({"index": i + 1, "status": "failed", "error": str(e)})
                failed_count += 1

        return {
            "batch_id": batch_id,
            "total_tasks": len(requests),
            "success_count": success_count,
            "failed_count": failed_count,
            "results": results,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
