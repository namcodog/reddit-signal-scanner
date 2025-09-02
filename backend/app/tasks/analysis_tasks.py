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
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from celery import Task
from sqlalchemy.orm import Session

from ..core.celery_app import get_celery_app
from ..core.database import get_db_session
from ..models.task import Task as TaskModel
from ..services.analysis_engine import AnalysisEngine
from ..core.task_base import BaseUnifiedTask

logger = logging.getLogger(__name__)

# 获取Celery应用实例
celery_app = get_celery_app()


@celery_app.task(
    bind=True,
    base=BaseUnifiedTask,
    name="analysis_tasks.analyze_product",
    queue="analysis_queue",
    max_retries=3,
    default_retry_delay=60,
    time_limit=300,  # 5分钟超时
    soft_time_limit=240,  # 4分钟软超时
    serializer="json",
    compression="gzip",
)
def analyze_product(
    self: Task, payload: Dict[str, Any], task_data: Optional[Dict[str, Any]] = None
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
    task_id = task_data.get("task_id") if task_data else self.request.id
    product_description = payload.get("product_description", "")

    # Linus修复：从TaskConfig获取配置参数
    from ..schemas.task_producer import TaskConfig

    config = TaskConfig.default_config()

    logger.info(f"开始产品分析任务: {task_id}")
    start_time = time.time()

    # 更新任务状态为进行中 - 使用同步调用异步函数的方式
    import asyncio

    asyncio.run(
        _update_task_status(
            task_id,
            "processing",
            {"started_at": datetime.now(timezone.utc).isoformat()},
        )
    )

    try:
        # 第1步：参数验证（统一验证逻辑）
        if not product_description or len(product_description.strip()) < 10:
            raise ValueError("产品描述不能为空且长度必须至少10个字符")

        # 第2步：初始化分析引擎
        analysis_engine = AnalysisEngine()

        # 第3步：执行分析（核心业务逻辑）
        analysis_result = analysis_engine.analyze_product_signals(
            product_description=product_description.strip(), task_id=task_id
        )

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
        asyncio.run(
            _update_task_status(
                task_id,
                "completed",
                {
                    "result": analysis_result,
                    "execution_time": result_data["execution_time"],
                    "completed_at": result_data["completed_at"],
                },
            )
        )

        logger.info(f"任务完成: {task_id}, 耗时: {result_data['execution_time']:.2f}秒")
        return result_data

    except ValueError as e:
        # 参数验证错误 - 不可重试
        error_msg = f"参数验证失败: {str(e)}"
        logger.error(f"任务 {task_id} 参数错误: {error_msg}")

        asyncio.run(
            _update_task_status(
                task_id,
                "failed",
                {"error": error_msg, "error_type": "validation_error"},
            )
        )

        # 不重试参数错误
        raise ValueError(error_msg)

    except ConnectionError as e:
        # 网络连接错误 - 可重试
        error_msg = f"网络连接失败: {str(e)}"
        logger.warning(f"任务 {task_id} 网络错误: {error_msg}")

        asyncio.run(
            _update_task_status(
                task_id,
                "retrying",
                {"error": error_msg, "retry_count": self.request.retries},
            )
        )

        # 重试机制 - Linus修复：使用配置化的重试延迟
        if self.request.retries < config.max_retries:
            # 使用配置的重试延迟序列
            if self.request.retries < len(config.retry_delays):
                countdown = config.retry_delays[self.request.retries]
            else:
                # 如果重试次数超过配置的延迟序列，使用最后一个值
                countdown = config.retry_delays[-1]

            logger.info(
                f"任务 {task_id} 将在 {countdown}秒后重试（第{self.request.retries + 1}次）"
            )
            raise self.retry(countdown=countdown, exc=e)
        else:
            # 重试次数用尽，标记为失败
            asyncio.run(
                _update_task_status(
                    task_id,
                    "failed",
                    {
                        "error": f"重试次数用尽: {error_msg}",
                        "error_type": "network_error",
                    },
                )
            )
            raise ConnectionError(f"重试次数用尽: {error_msg}")

    except Exception as e:
        # 未预期的错误
        error_msg = f"分析任务异常: {str(e)}"
        logger.exception(f"任务 {task_id} 未知错误: {error_msg}")

        asyncio.run(
            _update_task_status(
                task_id, "failed", {"error": error_msg, "error_type": "unknown_error"}
            )
        )

        # 对于未知错误也尝试重试一次
        if self.request.retries < 1:
            # 使用配置的第一个重试延迟
            countdown = config.retry_delays[0] if config.retry_delays else 120
            logger.info(f"任务 {task_id} 未知错误，尝试重试一次")
            raise self.retry(countdown=countdown, exc=e)
        else:
            raise Exception(error_msg)


@celery_app.task(
    bind=True,
    base=BaseUnifiedTask,
    name="analysis_tasks.batch_analyze",
    queue="analysis_queue",
    max_retries=2,
    time_limit=900,  # 15分钟
    soft_time_limit=800,
)
def batch_analyze_products(
    self: Task,
    product_list: list[str],
    batch_id: str,
    task_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
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
            result = analyze_product.delay(
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

    return {
        "batch_id": batch_id,
        "total_products": len(product_list),
        "submitted_count": len(product_list) - failed_count,
        "failed_count": failed_count,
        "results": results,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


async def _update_task_status(
    task_id: str, status: str, additional_data: Optional[Dict[str, Any]] = None
) -> None:
    """
    统一的任务状态更新函数 - Linus修复：统一异步数据库连接

    修复前: 混用同步和异步连接，连接池泄露风险
    修复后: 统一使用异步连接，线程安全

    Args:
        task_id: 任务ID
        status: 新状态
        additional_data: 额外的状态数据
    """
    try:
        from ..core.database import get_async_db_session
        from sqlalchemy import select, update

        # 使用异步数据库会话，避免连接池混乱
        async with get_async_db_session() as db:
            # 使用update语句，避免先查询再更新
            stmt = (
                update(TaskModel)
                .where(TaskModel.id == task_id)
                .values(status=status, updated_at=datetime.now(timezone.utc))
            )

            result = await db.execute(stmt)

            if result.rowcount > 0:
                # 如果有额外数据，单独更新metadata
                if additional_data:
                    task_stmt = select(TaskModel).where(TaskModel.id == task_id)
                    result = await db.execute(task_stmt)
                    task = result.scalar_one_or_none()

                    if task:
                        metadata = task.metadata or {}
                        metadata.update(additional_data)

                        metadata_stmt = (
                            update(TaskModel)
                            .where(TaskModel.id == task_id)
                            .values(metadata=metadata)
                        )
                        await db.execute(metadata_stmt)

                await db.commit()
                logger.debug(f"任务状态已更新: {task_id} -> {status}")
            else:
                logger.warning(f"任务不存在，无法更新状态: {task_id}")

    except Exception as e:
        logger.error(f"更新任务状态失败 {task_id}: {e}", exc_info=True)
        # 数据库更新失败不影响任务执行，只记录日志
        # 数据库更新失败不影响任务执行，只记录日志


# 任务健康检查
@celery_app.task(name="analysis_tasks.health_check", queue="monitoring_queue")
def analysis_health_check() -> Dict[str, Any]:
    """
    分析任务健康检查

    用于监控系统检查分析任务的健康状态

    Returns:
        Dict: 健康状态报告
    """
    return {
        "service": "analysis_tasks",
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
    }
