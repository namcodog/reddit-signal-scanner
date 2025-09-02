"""
数据清理任务层 - Reddit Signal Scanner (Linus架构合规版)
Celery任务定义层，专门负责任务调度和执行协调

职责边界：
- 任务层：只负责Celery任务定义、参数验证、结果转换
- 服务层：具体的清理业务逻辑
- 锁管理层：并发控制
- 数据库层：SQL执行

基于Linus设计原则：
- 明确的层次边界，避免跨层调用
- 简单的任务接口，复杂的业务逻辑在服务层
- 统一的错误处理和日志记录
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from celery import Task
from celery.signals import task_success, task_failure
import logging
import json

# 导入服务层
from ..services.data_cleanup_service_v2 import (
    DataCleanupService,
    CleanupManager,
    CleanupResult,
    BatchCleanupResult,
)
from ..core.database import get_db
from ..core.config import settings

logger = logging.getLogger(__name__)


class BaseCleanupTask(Task):
    """
    基础清理任务类 - 统一的任务行为

    职责：
    - 任务重试策略
    - 错误处理
    - 状态报告
    """

    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 3, "countdown": 60}
    retry_backoff = True
    retry_backoff_max = 600

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """任务失败处理"""
        logger.error(
            f"清理任务失败 [{task_id}]: {exc}",
            extra={"task_args": args, "task_kwargs": kwargs},
        )

        # 发送失败警报（如果配置了）
        try:
            self._send_failure_alert(task_id, exc, args, kwargs)
        except Exception as alert_error:
            logger.error(f"发送任务失败警报失败: {alert_error}")

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """任务重试处理"""
        logger.warning(
            f"清理任务重试 [{task_id}]: {exc}",
            extra={"retry_count": self.request.retries},
        )

    def _send_failure_alert(
        self, task_id: str, exc: Exception, args: tuple, kwargs: dict
    ):
        """发送失败警报（可扩展）"""
        # TODO: 集成实际的告警系统（钉钉、企微、邮件等）
        logger.info(f"任务失败警报已记录: {task_id}")


# Celery应用实例
from ..core.celery_app import celery_app


@celery_app.task(bind=True, base=BaseCleanupTask, name="execute_daily_cleanup")
def execute_daily_cleanup(
    self,
    completed_task_days: int = 30,
    failed_task_days: int = 7,
    orphan_analysis_hours: float = 1.0,
    inactive_user_days: int = 365,
) -> Dict[str, Any]:
    """
    每日数据清理任务 - 任务层接口

    职责：
    - 参数验证和标准化
    - 调用服务层执行清理
    - 结果转换和日志记录
    - 通知发送

    Args:
        completed_task_days: 完成任务保留天数
        failed_task_days: 失败任务保留天数
        orphan_analysis_hours: 孤儿分析记录保留小时数
        inactive_user_days: 非活跃用户保留天数

    Returns:
        Dict: 清理结果统计
    """
    task_id = self.request.id
    logger.info(f"开始执行每日数据清理任务 [{task_id}]")

    # 任务层职责：参数验证和标准化
    task_params = _validate_and_normalize_params(
        completed_task_days=completed_task_days,
        failed_task_days=failed_task_days,
        orphan_analysis_hours=orphan_analysis_hours,
        inactive_user_days=inactive_user_days,
    )

    try:
        # 任务层职责：调用服务层
        with CleanupManager() as cleanup_service:
            result: BatchCleanupResult = cleanup_service.execute_full_cleanup(
                **task_params
            )

        # 任务层职责：结果转换（服务层返回TypedDict，任务层转换为普通dict）
        task_result = _convert_batch_result_to_dict(result)

        # 任务层职责：发送成功通知
        _send_success_notification(task_result, task_id)

        # 任务层职责：异常数据检查
        _check_cleanup_anomalies(task_result, task_id)

        logger.info(
            f"每日清理任务完成 [{task_id}]: 总计清理 {task_result['total_records_cleaned']} 条记录"
        )
        return task_result

    except Exception as e:
        logger.error(f"每日清理任务失败 [{task_id}]: {e}")
        # 让BaseCleanupTask处理重试逻辑
        raise


@celery_app.task(bind=True, base=BaseCleanupTask, name="cleanup_preview_report")
def cleanup_preview_report(self) -> Dict[str, Any]:
    """
    清理预览报告任务 - 任务层接口

    Returns:
        Dict: 预览结果
    """
    task_id = self.request.id
    logger.info(f"生成清理预览报告 [{task_id}]")

    try:
        with CleanupManager() as cleanup_service:
            preview: BatchCleanupResult = cleanup_service.get_cleanup_preview()

        result = _convert_batch_result_to_dict(preview)

        # 计算预览摘要
        total_to_clean = result["total_records_cleaned"]
        logger.info(f"清理预览完成 [{task_id}]: 预计清理 {total_to_clean} 条记录")

        return result

    except Exception as e:
        logger.error(f"清理预览失败 [{task_id}]: {e}")
        raise


@celery_app.task(bind=True, base=BaseCleanupTask, name="emergency_cleanup")
def emergency_cleanup(self, force_aggressive: bool = False) -> Dict[str, Any]:
    """
    紧急数据清理任务 - 任务层接口

    Args:
        force_aggressive: 是否强制激进清理

    Returns:
        Dict: 清理结果
    """
    task_id = self.request.id
    logger.warning(
        f"开始执行紧急数据清理任务 [{task_id}] - 激进模式: {force_aggressive}"
    )

    try:
        # 紧急清理使用更短的保留期
        params = {
            "completed_task_days": 7 if force_aggressive else 14,
            "failed_task_days": 1 if force_aggressive else 3,
            "orphan_analysis_hours": 0.5 if force_aggressive else 1.0,
            "inactive_user_days": 90 if force_aggressive else 180,
        }

        with CleanupManager() as cleanup_service:
            result: BatchCleanupResult = cleanup_service.execute_full_cleanup(**params)

        task_result = _convert_batch_result_to_dict(result)

        # 紧急清理需要立即通知
        _send_emergency_notification(task_result, task_id, force_aggressive)

        logger.warning(
            f"紧急清理完成 [{task_id}]: 总计清理 {task_result['total_records_cleaned']} 条记录"
        )
        return task_result

    except Exception as e:
        logger.error(f"紧急清理失败 [{task_id}]: {e}")
        raise


@celery_app.task(bind=True, base=BaseCleanupTask, name="cleanup_by_category_task")
def cleanup_by_category_task(
    self,
    category: str,
    days_old: Optional[int] = None,
    hours_old: Optional[float] = None,
) -> Dict[str, Any]:
    """
    按类别清理数据任务 - 任务层接口

    Args:
        category: 清理类别
        days_old: 保留天数
        hours_old: 保留小时数

    Returns:
        Dict: 清理结果
    """
    task_id = self.request.id
    logger.info(f"开始执行分类清理任务 [{task_id}] - 类别: {category}")

    try:
        # 构建清理参数
        cleanup_params = {}
        if days_old is not None:
            cleanup_params["days_old"] = days_old
        if hours_old is not None:
            cleanup_params["hours_old"] = hours_old

        with CleanupManager() as cleanup_service:
            result: CleanupResult = cleanup_service.cleanup_by_category(
                category, **cleanup_params
            )

        # 转换单个清理结果
        task_result = dict(result)

        logger.info(
            f"分类清理完成 [{task_id}]: {category} 清理了 {result['records_cleaned']} 条记录"
        )
        return task_result

    except Exception as e:
        logger.error(f"分类清理失败 [{task_id}]: {e}")
        raise


@celery_app.task(name="health_check_cleanup")
def health_check_cleanup() -> Dict[str, Any]:
    """
    清理系统健康检查任务

    Returns:
        Dict: 健康检查结果
    """
    logger.info("执行清理系统健康检查")

    try:
        with CleanupManager() as cleanup_service:
            # 获取清理统计信息
            stats = cleanup_service.get_cleanup_statistics()

            # 生成健康检查摘要
            summary = stats.get("summary", {})
            success_rate = summary.get("avg_success_rate", 0)

            health_status = (
                "healthy"
                if success_rate > 90
                else "warning" if success_rate > 70 else "unhealthy"
            )

            result = {
                "health_status": health_status,
                "success_rate": success_rate,
                "last_cleanup": summary.get("last_cleanup"),
                "total_runs": summary.get("total_cleanup_runs", 0),
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }

            logger.info(
                f"健康检查完成 - 状态: {health_status}, 成功率: {success_rate}%"
            )
            return result

    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            "health_status": "unhealthy",
            "success_rate": 0,
            "error": str(e),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }


# ===============================
# 任务层辅助函数（内部职责边界）
# ===============================


def _validate_and_normalize_params(**params) -> Dict[str, Any]:
    """任务层职责：参数验证和标准化"""
    normalized = {}

    # 验证完成任务保留天数
    completed_days = params.get("completed_task_days", 30)
    if (
        not isinstance(completed_days, int)
        or completed_days < 1
        or completed_days > 365
    ):
        raise ValueError(f"完成任务保留天数无效: {completed_days}，有效范围: [1, 365]")
    normalized["completed_task_days"] = completed_days

    # 验证失败任务保留天数
    failed_days = params.get("failed_task_days", 7)
    if not isinstance(failed_days, int) or failed_days < 1 or failed_days > 365:
        raise ValueError(f"失败任务保留天数无效: {failed_days}，有效范围: [1, 365]")
    normalized["failed_task_days"] = failed_days

    # 验证孤儿分析保留小时数
    orphan_hours = params.get("orphan_analysis_hours", 1.0)
    if (
        not isinstance(orphan_hours, (int, float))
        or orphan_hours < 0.1
        or orphan_hours > 168
    ):
        raise ValueError(
            f"孤儿分析保留小时数无效: {orphan_hours}，有效范围: [0.1, 168]"
        )
    normalized["orphan_analysis_hours"] = float(orphan_hours)

    # 验证非活跃用户保留天数
    inactive_days = params.get("inactive_user_days", 365)
    if not isinstance(inactive_days, int) or inactive_days < 30 or inactive_days > 1095:
        raise ValueError(
            f"非活跃用户保留天数无效: {inactive_days}，有效范围: [30, 1095]"
        )
    normalized["inactive_user_days"] = inactive_days

    return normalized


def _convert_batch_result_to_dict(result: BatchCleanupResult) -> Dict[str, Any]:
    """任务层职责：TypedDict转换为普通dict"""
    return {
        "total_records_cleaned": result["total_records_cleaned"],
        "execution_time_seconds": result["execution_time_seconds"],
        "success": result["success"],
        "breakdown": [dict(item) for item in result["breakdown"]],
        "database_stats": result["database_stats"],
    }


def _send_success_notification(result: Dict[str, Any], task_id: str):
    """任务层职责：发送成功通知"""
    try:
        # TODO: 集成实际的通知系统
        total_cleaned = result["total_records_cleaned"]
        execution_time = result["execution_time_seconds"]

        logger.info(
            f"清理任务成功通知 [{task_id}]: "
            f"清理 {total_cleaned} 条记录，耗时 {execution_time} 秒"
        )
    except Exception as e:
        logger.warning(f"发送成功通知失败: {e}")


def _send_emergency_notification(
    result: Dict[str, Any], task_id: str, force_aggressive: bool
):
    """任务层职责：发送紧急清理通知"""
    try:
        # TODO: 集成实际的紧急通知系统（更高优先级）
        total_cleaned = result["total_records_cleaned"]
        mode = "激进模式" if force_aggressive else "标准模式"

        logger.warning(
            f"紧急清理通知 [{task_id}]: " f"{mode}清理 {total_cleaned} 条记录"
        )
    except Exception as e:
        logger.error(f"发送紧急通知失败: {e}")


def _check_cleanup_anomalies(result: Dict[str, Any], task_id: str):
    """任务层职责：异常数据检查"""
    total_cleaned = result["total_records_cleaned"]

    # 单次清理记录数异常检查
    if total_cleaned > 100000:  # 10万条记录
        logger.warning(
            f"清理数量异常警告 [{task_id}]: "
            f"单次清理 {total_cleaned} 条记录，超过正常阈值"
        )
        # TODO: 发送异常告警

    # 检查各类别清理结果异常
    for item in result["breakdown"]:
        if not item["success"]:
            logger.error(
                f"清理类别失败 [{task_id}]: "
                f"{item['category']} - {item['error_message']}"
            )


# ===============================
# Celery信号处理（任务层职责）
# ===============================


@task_success.connect
def task_success_handler(
    sender=None, task_id=None, result=None, retries=None, einfo=None, **kwargs
):
    """任务成功信号处理"""
    logger.info(f"清理任务成功完成: {task_id}")


@task_failure.connect
def task_failure_handler(
    sender=None,
    task_id=None,
    exception=None,
    args=None,
    kwargs=None,
    einfo=None,
    **extra_kwargs,
):
    """任务失败信号处理"""
    logger.error(f"清理任务执行失败: {task_id} - {exception}")


# ===============================
# 任务层便捷函数（外部接口）
# ===============================


def trigger_emergency_cleanup(aggressive: bool = False):
    """触发紧急清理的便捷函数"""
    result = emergency_cleanup.delay(force_aggressive=aggressive)
    return {"task_id": result.id, "status": "submitted"}


def trigger_category_cleanup(category: str, **kwargs):
    """触发分类清理的便捷函数"""
    result = cleanup_by_category_task.delay(category, **kwargs)
    return {"task_id": result.id, "status": "submitted"}


def get_cleanup_task_status(task_id: str):
    """获取清理任务状态的便捷函数"""
    from celery.result import AsyncResult

    result = AsyncResult(task_id, app=celery_app)
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None,
    }


# ===============================
# 导出接口（明确对外边界）
# ===============================

__all__ = [
    # Celery任务
    "execute_daily_cleanup",
    "cleanup_preview_report",
    "emergency_cleanup",
    "cleanup_by_category_task",
    "health_check_cleanup",
    # 便捷函数
    "trigger_emergency_cleanup",
    "trigger_category_cleanup",
    "get_cleanup_task_status",
    # 基础类
    "BaseCleanupTask",
]
