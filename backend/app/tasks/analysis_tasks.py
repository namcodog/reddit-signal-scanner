"""
分析任务定义 - prd04-02实现
@celery.task装饰的分析任务，支持异步Reddit信号分析

基于Linus设计哲学：
1. 任务职责单一 - 每个任务只做一件事
2. 统一错误处理 - 消除特殊情况的错误处理
3. 配置驱动 - 所有参数通过配置传入
4. 简单胜过聪明 - 直观的任务逻辑
"""

import logging
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional, cast

from celery import Task
from celery.app.task import Task as CeleryTask
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.celery_app import get_celery_app
from ..core.database import get_session_sync
from ..core.task_base import BaseUnifiedTask
from ..models.task import Task as TaskModel
from ..services.analysis_engine import AnalysisEngine

logger = logging.getLogger(__name__)


# =========================
# Pydantic响应模型 - 基于Context7最佳实践
# =========================


class AnalysisTaskResponse(BaseModel):
    """产品分析任务响应模型"""

    task_id: str
    status: str
    product_description: str
    analysis_result: Dict[str, Any]
    execution_time: float
    completed_at: str
    metadata: Dict[str, Any]


class BatchAnalysisResponse(BaseModel):
    """批量分析任务响应模型"""

    batch_id: str
    total_products: int
    submitted_count: int
    failed_count: int
    results: List[Dict[str, Any]]
    completed_at: str


class HealthCheckResponse(BaseModel):
    """健康检查响应模型"""

    service: str
    status: str
    timestamp: str
    version: str


class DeadLetterOperationResponse(BaseModel):
    """死信队列操作响应模型"""

    operation: str
    moved_count: int
    processed_tasks: List[Dict[str, Any]]
    timestamp: str


class RetryTaskResponse(BaseModel):
    """重试任务响应模型"""

    success: bool
    task_id: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None
    timestamp: str


class DeadLetterStatsResponse(BaseModel):
    """死信队列统计响应模型"""

    total_dead_letters: int
    by_category: Dict[str, int]
    recent_tasks: List[Dict[str, Any]]
    timestamp: str


# 获取Celery应用实例
celery_app = get_celery_app()


def _analyze_product_typed(
    self: BaseUnifiedTask,
    payload: Dict[str, Any],
    task_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    产品分析Celery任务 - Reddit信号分析的核心任务

    这是用户请求的最终执行者，负责：
    1. Reddit数据采集
    2. 信号提取和分析
    3. 结果生成和存储
    4. 状态更新

    Args:
        payload: 任务载荷数据，包含product_description等
        task_data: 任务元数据，包含task_id等信息

    Returns:
        Dict[str, Any]: 分析结果

    Raises:
        AnalysisError: 分析过程中的错误
        DatabaseError: 数据库操作错误
        RetryError: 需要重试的临时错误
    """
    # 使用合法UUID，若传入非UUID则回退为当前request.id
    import uuid

    raw_task_id = (
        (task_data.get("task_id") if task_data else self.request.id)
        if task_data
        else self.request.id
    )
    try:
        task_uuid = uuid.UUID(str(raw_task_id))
        task_id: str = str(task_uuid)
    except Exception:
        task_id = str(self.request.id)
    product_description = payload.get("product_description", "")

    # Linus修复：从TaskConfig获取配置参数
    from ..schemas.task_producer import TaskConfig

    config = TaskConfig.default_config()

    logger.info(f"开始产品分析任务: {task_id}")
    start_time = time.time()

    # 更新任务状态为进行中
    _update_task_status_sync(
        task_id,
        "processing",
        {"started_at": datetime.now(timezone.utc).isoformat()},
    )

    try:
        # 第1步：参数验证（统一验证逻辑）
        if not product_description or len(product_description.strip()) < 10:
            raise ValueError("产品描述不能为空且长度必须至少10个字符")

        # 第2步：初始化分析引擎
        # 在任务内确保分析引擎可用（构造函数内会保证配置已加载）
        analysis_engine = AnalysisEngine()

        # 第3步：执行分析（核心业务逻辑）
        import asyncio

        analysis_report = asyncio.run(
            analysis_engine.analyze(product_description=product_description.strip())
        )
        # 将 AnalysisReport 转为可序列化的最小字典，避免Pydantic校验/JSON序列化问题
        analysis_result: Dict[str, Any] = {
            "report_id": analysis_report.report_id,
            "summary": analysis_report.get_executive_summary(),
            "confidence_score": analysis_report.confidence_score,
            "total_posts": analysis_report.total_posts_analyzed,
            "communities": analysis_report.communities_scanned,
        }

        # 第4步：处理分析结果
        result_data = {
            "task_id": task_id,
            "status": "completed",
            "product_description": product_description,
            "analysis_result": analysis_result,
            "execution_time": time.time() - start_time,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "metadata": task_data or {},
        }

        # 第5步：更新数据库状态
        _update_task_status_sync(
            task_id,
            "completed",
            {
                "result": analysis_result,
                "execution_time": result_data["execution_time"],
                "completed_at": result_data["completed_at"],
            },
        )

        logger.info(f"任务完成: {task_id}, 耗时: {result_data['execution_time']:.2f}秒")
        return result_data

    except ValueError as e:
        # 参数验证错误 - 不可重试
        error_msg = f"参数验证失败: {str(e)}"
        logger.error(f"任务 {task_id} 参数错误: {error_msg}")

        _update_task_status_sync(
            task_id,
            "failed",
            {"error": error_msg, "error_type": "validation_error"},
        )

        # 不重试参数错误
        raise ValueError(error_msg)

    except (ConnectionError, TimeoutError, OSError) as e:
        # 这些异常会被autoretry_for自动处理，无需手动重试
        error_msg = f"临时性错误，将自动重试: {str(e)}"
        logger.warning(f"任务 {task_id} 临时错误: {error_msg}")

        # 更新数据库记录重试信息
        _update_task_status_sync(
            task_id,
            "retrying",
            {
                "error": error_msg,
                "retry_count": self.request.retries,
                "error_type": "temporary_error",
            },
        )

        # 让Celery的autoretry_for处理重试逻辑
        raise  # 直接重新抛出异常，由Celery处理

    except Exception as e:
        # 其他异常不自动重试，直接失败
        error_msg = f"分析任务失败: {str(e)}"
        logger.error(f"任务 {task_id} 不可重试错误: {error_msg}")

        _update_task_status_sync(
            task_id,
            "failed",
            {
                "error": error_msg,
                "error_type": "permanent_error",
                "retry_count": self.request.retries,
            },
        )

        # 直接失败，不重试
        raise


# 使用注册方式创建 Celery 任务，避免装饰器导致的 mypy 未类型化报错
analyze_product_task = celery_app.task(
    bind=True,
    base=BaseUnifiedTask,
    name="analysis_tasks.analyze_product",
    queue="analysis_queue",
    autoretry_for=(ConnectionError, TimeoutError, OSError),
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    time_limit=300,
    soft_time_limit=240,
    serializer="json",
    compression="gzip",
)(_analyze_product_typed)


def _batch_analyze_products_typed(
    self: BaseUnifiedTask,
    product_list: List[str],
    batch_id: str,
    task_data: Optional[Dict[str, Any]] = None,
) -> BatchAnalysisResponse:
    """
    批量产品分析任务

    处理多个产品的批量分析请求，用于未来扩展

    Args:
        product_list: 产品描述列表
        batch_id: 批次ID
        task_data: 任务元数据

    Returns:
        Dict: 批量分析结果
    """
    logger.info(f"开始批量分析任务: {batch_id}, 产品数量: {len(product_list)}")

    results = []
    failed_count = 0

    for i, product_description in enumerate(product_list):
        try:
            # 为每个产品创建子任务
            sub_task_id = f"{batch_id}_item_{i+1}"

            # 调用单个产品分析
            result = cast(Any, analyze_product_task).delay(
                payload={"product_description": product_description},
                task_data={"task_id": sub_task_id, "batch_id": batch_id},
            )

            results.append(
                {
                    "index": i + 1,
                    "product": product_description[:50] + "...",
                    "sub_task_id": sub_task_id,
                    "status": "submitted",
                }
            )

        except Exception as e:
            failed_count += 1
            logger.error(f"批量任务 {batch_id} 第{i+1}项提交失败: {e}")

            results.append(
                {
                    "index": i + 1,
                    "product": product_description[:50] + "...",
                    "status": "failed",
                    "error": str(e),
                }
            )

    return BatchAnalysisResponse(
        batch_id=batch_id,
        total_products=len(product_list),
        submitted_count=len(product_list) - failed_count,
        failed_count=failed_count,
        results=results,
        completed_at=datetime.now(timezone.utc).isoformat(),
    )


batch_analyze_products = celery_app.task(
    bind=True,
    base=BaseUnifiedTask,
    name="analysis_tasks.batch_analyze",
    queue="analysis_queue",
    max_retries=2,
    time_limit=900,  # 15分钟
    soft_time_limit=800,
)(_batch_analyze_products_typed)


def _update_task_status_sync(
    task_id: str, status: str, additional_data: Optional[Dict[str, Any]] = None
) -> None:
    """
    统一的任务状态更新函数 - 基于Context7最佳实践的同步版本

    Args:
        task_id: 任务ID
        status: 新状态
        additional_data: 额外的状态数据
    """
    try:
        from sqlalchemy import update

        # 使用同步数据库会话，符合Celery任务的同步特性
        with _get_sync_session() as db:
            from uuid import UUID as UUIDType

            from sqlalchemy.sql.elements import ColumnElement

            # 确保task_id是UUID类型
            task_uuid = UUIDType(task_id) if isinstance(task_id, str) else task_id

            stmt = (
                update(TaskModel)
                .where(TaskModel.id == task_uuid)
                .values(status=status, updated_at=datetime.now(timezone.utc))
            )

            result = db.execute(stmt)

            if result.rowcount > 0:
                # 目前 Task 模型不包含 metadata 字段，记录日志而不写库
                if additional_data:
                    logger.debug(
                        "additional_data provided but Task model has no metadata column: %s",
                        list(additional_data.keys()),
                    )

                db.commit()
                logger.debug(f"任务状态已更新: {task_id} -> {status}")
            else:
                logger.warning(f"任务不存在，无法更新状态: {task_id}")

    except Exception as e:
        logger.error(f"更新任务状态失败 {task_id}: {e}", exc_info=True)
        # 数据库更新失败不影响任务执行，只记录日志


@contextmanager
def _get_sync_session() -> Generator[Session, None, None]:
    """同步数据库会话上下文管理器 - 基于Context7最佳实践"""
    session = get_session_sync()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"数据库操作失败: {e}")
        raise
    finally:
        session.close()


# 任务健康检查（注册方式）
def _analysis_health_check_typed() -> HealthCheckResponse:
    """
    分析任务健康检查

    用于监控系统检查分析任务的健康状态

    Returns:
        Dict: 健康状态报告
    """
    # 为保证Celery JSON序列化兼容，返回Pydantic模型的可序列化字典
    model = HealthCheckResponse(
        service="analysis_tasks",
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="1.0.0",
    )
    return model


analysis_health_check = celery_app.task(
    name="analysis_tasks.health_check", queue="monitoring_queue"
)(_analysis_health_check_typed)

# 兼容导出：测试导入 analyze_product
analyze_product = analyze_product_task


# ========== prd04-05: 简化的死信队列和恢复机制 ==========


def _move_failed_tasks_to_dead_letter_typed() -> DeadLetterOperationResponse:
    """
    将重试失败的任务移至死信队列

    这个任务定期运行，查找状态为failed且retry_count达到最大值的任务，
    将其移至DEAD_LETTER状态。简化版实现，基于Celery最佳实践。

    Returns:
        处理结果统计
    """
    # get_db_session 已在模块级别修复
    from ..models.task import FailureCategory, TaskStatus

    logger.info("开始检查需要移至死信队列的任务")

    moved_count = 0
    processed_tasks = []

    try:
        with _get_sync_session() as db:
            # 查找状态为failed且重试次数已满的任务
            from sqlalchemy.sql.elements import ColumnElement

            failed_tasks = (
                db.query(TaskModel)
                .filter(TaskModel.status == TaskStatus.FAILED.value)
                .filter(TaskModel.retry_count >= 3)
                .limit(100)
                .all()
            )  # 批量处理，避免过载

            for task in failed_tasks:
                try:
                    # 移至死信队列
                    setattr(task, "status", TaskStatus.DEAD_LETTER.value)
                    setattr(task, "dead_letter_at", datetime.now(timezone.utc))

                    # 分析失败原因（简化版）
                    error_msg = task.error_message or "未知错误"
                    if (
                        "网络" in error_msg
                        or "连接" in error_msg
                        or "timeout" in error_msg.lower()
                    ):
                        setattr(
                            task,
                            "failure_category",
                            FailureCategory.NETWORK_ERROR.value,
                        )
                    elif "验证" in error_msg or "validation" in error_msg.lower():
                        setattr(
                            task,
                            "failure_category",
                            FailureCategory.DATA_VALIDATION_ERROR.value,
                        )
                    else:
                        setattr(
                            task, "failure_category", FailureCategory.SYSTEM_ERROR.value
                        )

                    processed_tasks.append(
                        {
                            "task_id": str(task.id),
                            "failure_category": task.failure_category,
                            "retry_count": task.retry_count,
                        }
                    )

                    moved_count += 1

                except Exception as e:
                    logger.error(f"移动任务到死信队列失败 {task.id}: {e}")

            # 提交所有更改
            if moved_count > 0:
                db.commit()
                logger.info(f"成功移动 {moved_count} 个任务到死信队列")

    except Exception as e:
        logger.error(f"死信队列处理异常: {e}")

    return DeadLetterOperationResponse(
        operation="move_to_dead_letter",
        moved_count=moved_count,
        processed_tasks=processed_tasks,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


move_failed_tasks_to_dead_letter = celery_app.task(
    name="analysis_tasks.move_to_dead_letter",
    queue="maintenance_queue",
    max_retries=1,
)(_move_failed_tasks_to_dead_letter_typed)


def _retry_dead_letter_task_typed(task_id: str) -> RetryTaskResponse:
    """
    手动重试死信队列中的任务

    简化实现：重置任务状态，让其重新进入正常处理流程。
    基于Context7最佳实践的最小可行实现。

    Args:
        task_id: 要重试的任务ID

    Returns:
        重试结果
    """
    logger.info(f"开始重试死信队列任务: {task_id}")

    from ..models.task import TaskStatus

    try:
        from uuid import UUID as UUIDType

        # 确保task_id是UUID类型
        task_uuid = UUIDType(task_id) if isinstance(task_id, str) else task_id

        with _get_sync_session() as db:
            # 查找死信队列中的任务
            from sqlalchemy.sql.elements import ColumnElement

            task = (
                db.query(TaskModel)
                .filter(
                    TaskModel.id == task_uuid,
                    TaskModel.status == TaskStatus.DEAD_LETTER.value,
                )
                .first()
            )

            if not task:
                return RetryTaskResponse(
                    success=False,
                    error=f"任务不存在或不在死信队列: {task_id}",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

            # 重置任务状态，给其新的机会
            setattr(task, "status", TaskStatus.PENDING.value)
            setattr(task, "retry_count", 0)  # 重置重试计数
            setattr(task, "error_message", None)
            setattr(task, "dead_letter_at", None)
            setattr(task, "last_retry_at", datetime.now(timezone.utc))

            db.commit()

            # 重新提交任务到队列
            cast(Any, analyze_product_task).delay(
                payload={"product_description": task.product_description},
                task_data={"task_id": str(task.id)},
            )

            logger.info(f"成功重试死信队列任务: {task_id}")

            return RetryTaskResponse(
                success=True,
                task_id=task_id,
                message="任务已重新提交处理",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

    except Exception as e:
        logger.error(f"重试死信队列任务失败 {task_id}: {e}")
        return RetryTaskResponse(
            success=False,
            error=str(e),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


retry_dead_letter_task = celery_app.task(
    name="analysis_tasks.retry_dead_letter",
    queue="maintenance_queue",
    max_retries=2,
)(_retry_dead_letter_task_typed)


def _get_dead_letter_statistics_typed() -> DeadLetterStatsResponse:
    """
    获取死信队列统计信息

    简化的监控功能，提供死信队列的基本统计数据。

    Returns:
        统计信息
    """
    from ..models.task import TaskStatus

    try:
        with _get_sync_session() as db:
            # 总数统计
            from sqlalchemy.sql.elements import ColumnElement

            total_dead_letters = (
                db.query(TaskModel)
                .filter(TaskModel.status == TaskStatus.DEAD_LETTER.value)
                .count()
            )

            # 按失败类型统计（如果有）
            category_stats = {}
            if total_dead_letters > 0:
                from sqlalchemy import func

                results = (
                    db.query(cast(Any, TaskModel.failure_category), func.count())
                    .filter(TaskModel.status == TaskStatus.DEAD_LETTER.value)
                    .group_by(TaskModel.failure_category)
                    .all()
                )

                category_stats = {
                    category or "unknown": count for category, count in results
                }

            # 最近的死信任务
            from sqlalchemy import desc

            recent_dead_letters = (
                db.query(TaskModel)
                .filter(TaskModel.status == TaskStatus.DEAD_LETTER.value)
                .filter(cast(Any, TaskModel.dead_letter_at).is_not(None))
                .order_by(cast(Any, TaskModel.dead_letter_at).desc())
                .limit(5)
                .all()
            )

            recent_tasks = [
                {
                    "task_id": str(task.id),
                    "failure_category": task.failure_category,
                    "dead_letter_at": (
                        task.dead_letter_at.isoformat() if task.dead_letter_at else None
                    ),
                    "retry_count": task.retry_count,
                }
                for task in recent_dead_letters
            ]

            return DeadLetterStatsResponse(
                total_dead_letters=total_dead_letters,
                by_category=category_stats,
                recent_tasks=recent_tasks,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

    except Exception as e:
        logger.error(f"获取死信队列统计失败: {e}")
        return DeadLetterStatsResponse(
            total_dead_letters=0,
            by_category={},
            recent_tasks=[],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


get_dead_letter_statistics = celery_app.task(
    name="analysis_tasks.get_dead_letter_stats", queue="monitoring_queue"
)(_get_dead_letter_statistics_typed)
