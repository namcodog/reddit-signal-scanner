"""
数据清理Celery任务 - Reddit Signal Scanner
使用统一的Celery架构实现自动化的定时数据清理

基于Linus设计原则：
- 使用统一的Celery应用实例，消除重复配置
- 继承统一的任务基类，消除重复错误处理逻辑
- 简单的任务定义，复杂的逻辑在服务层
- 配置驱动的参数管理
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging

from ..core.celery_app import get_celery_app
from ..core.task_base import CleanupTask
from ..services.data_cleanup_service import execute_cleanup, get_cleanup_preview

logger = logging.getLogger(__name__)

# 使用统一的Celery应用实例
celery_app = get_celery_app()


# 使用统一的清理任务基类，无需重复定义
# BaseCleanupTask功能已整合到 CleanupTask 中


@celery_app.task(bind=True, base=CleanupTask, name="execute_daily_cleanup")
def execute_daily_cleanup(
    self,
    completed_task_days: int = 30,
    failed_task_days: int = 7,
    orphan_analysis_hours: float = 1.0,
    inactive_user_days: int = 365,
) -> Dict[str, Any]:
    """
    每日数据清理任务 - 凌晨2点执行

    Args:
        completed_task_days: 完成任务保留天数
        failed_task_days: 失败任务保留天数
        orphan_analysis_hours: 孤儿分析记录保留小时数
        inactive_user_days: 非活跃用户保留天数

    Returns:
        Dict: 清理结果统计
    """
    from ..core.cleanup_lock import get_cleanup_lock, CleanupLockError

    task_id = self.request.id
    logger.info(f"开始执行每日数据清理任务 [{task_id}]")

    # 获取清理锁，防止并发执行
    cleanup_lock = get_cleanup_lock()
    task_info = {
        "task_id": task_id,
        "task_type": "daily_cleanup",
        "params": {
            "completed_task_days": completed_task_days,
            "failed_task_days": failed_task_days,
            "orphan_analysis_hours": orphan_analysis_hours,
            "inactive_user_days": inactive_user_days,
        },
    }

    try:
        with cleanup_lock.acquire(timeout=3600, task_info=task_info):  # 1小时锁定
            # 执行数据清理
            results = execute_cleanup(
                dry_run=False,
                completed_task_days=completed_task_days,
                failed_task_days=failed_task_days,
                orphan_analysis_hours=orphan_analysis_hours,
                inactive_user_days=inactive_user_days,
            )

            logger.info(f"每日清理完成 [{task_id}]: {results}")

            # 发送清理成功摘要
            try:
                from ..services.notification_service import send_cleanup_success_summary

                send_cleanup_success_summary(results, "daily_cleanup")
            except Exception as e:
                logger.warning(f"发送清理成功摘要失败: {e}")

            # 检查清理结果是否异常
            total_cleaned = results.get("total_cleaned", 0)
            if total_cleaned > 50000:  # 单次清理超过5万条记录
                logger.warning(f"单次清理记录数异常: {total_cleaned}")
                # 可以发送告警或暂停后续清理

            return results

    except CleanupLockError as e:
        logger.warning(f"清理任务获取锁失败 [{task_id}]: {e}")
        raise self.retry(countdown=300, max_retries=2)  # 5分钟后重试，最多2次

    except Exception as e:
        logger.error(f"每日清理失败 [{task_id}]: {e}")
        raise


@celery_app.task(bind=True, base=CleanupTask, name="cleanup_preview_report")
def cleanup_preview_report(self) -> Dict[str, Any]:
    """
    清理预览报告任务 - 每周执行，生成清理预览

    Returns:
        Dict: 清理预览数据
    """
    task_id = self.request.id
    logger.info(f"开始生成清理预览报告 [{task_id}]")

    try:
        preview = get_cleanup_preview()

        logger.info(f"清理预览完成 [{task_id}]: {preview}")

        # 检查是否需要告警
        total_to_clean = preview.get("total_cleaned", 0)
        if total_to_clean > 100000:  # 预计清理超过10万条记录
            logger.warning(f"预计清理记录数过多: {total_to_clean}")
            # 发送预警通知

        return preview

    except Exception as e:
        logger.error(f"清理预览失败 [{task_id}]: {e}")
        raise


@celery_app.task(bind=True, base=CleanupTask, name="emergency_cleanup")
def emergency_cleanup(self, force_aggressive: bool = False) -> Dict[str, Any]:
    """
    紧急清理任务 - 手动触发或告警触发

    Args:
        force_aggressive: 是否强制使用更激进的清理策略

    Returns:
        Dict: 紧急清理结果
    """
    task_id = self.request.id
    logger.warning(f"执行紧急数据清理 [{task_id}]")

    try:
        # 更激进的清理策略
        if force_aggressive:
            results = execute_cleanup(
                dry_run=False,
                completed_task_days=15,  # 15天
                failed_task_days=3,  # 3天
                orphan_analysis_hours=0.5,  # 30分钟
                inactive_user_days=180,  # 6个月
            )
        else:
            results = execute_cleanup(
                dry_run=False,
                completed_task_days=20,  # 20天
                failed_task_days=5,  # 5天
                orphan_analysis_hours=0.5,  # 30分钟
                inactive_user_days=270,  # 9个月
            )

        logger.info(f"紧急清理完成 [{task_id}]: {results}")
        return results

    except Exception as e:
        logger.error(f"紧急清理失败 [{task_id}]: {e}")
        raise


@celery_app.task(bind=True, base=CleanupTask, name="cleanup_by_category")
def cleanup_by_category_task(
    self,
    category: str,
    days_old: Optional[int] = None,
    hours_old: Optional[float] = None,
) -> int:
    """
    按类别清理数据任务

    Args:
        category: 清理类别
        days_old: 保留天数
        hours_old: 保留小时数

    Returns:
        int: 清理的记录数
    """
    task_id = self.request.id
    logger.info(f"执行分类清理任务 [{task_id}]: {category}")

    try:
        from ..services.data_cleanup_service import CleanupManager

        with CleanupManager() as cleanup_service:
            deleted_count = cleanup_service.cleanup_by_category(
                category=category, days_old=days_old, hours_old=hours_old
            )

        logger.info(f"分类清理完成 [{task_id}]: {category} -> {deleted_count} 条记录")
        return deleted_count

    except Exception as e:
        logger.error(f"分类清理失败 [{task_id}]: {e}")
        raise


@celery_app.task(name="health_check_cleanup")
def health_check_cleanup() -> Dict[str, Any]:
    """清理系统健康检查任务"""
    try:
        from ..services.data_cleanup_service import get_cleanup_stats

        stats = get_cleanup_stats()

        # 检查清理系统健康状态
        summary = stats.get("summary", {})
        success_rate = summary.get("avg_success_rate", 0)

        health_status = {
            "status": "healthy" if success_rate >= 95 else "degraded",
            "success_rate": success_rate,
            "last_cleanup": summary.get("last_cleanup"),
            "checks": {
                "success_rate_ok": success_rate >= 95,
                "recent_cleanup_ok": summary.get("last_cleanup") is not None,
            },
        }

        logger.info(f"清理系统健康检查: {health_status}")
        return health_status

    except Exception as e:
        logger.error(f"清理系统健康检查失败: {e}")
        return {"status": "unhealthy", "error": str(e)}


# Beat调度配置已移到统一的 celery_app.py 中管理
# 实现配置集中化，消除重复定义


# 信号处理已统一到 celery_app.py 中管理
# 实现全局统一的信号处理逻辑


# 便捷函数 - 手动触发清理任务
def trigger_emergency_cleanup(aggressive: bool = False) -> str:
    """触发紧急清理"""
    result = emergency_cleanup.delay(force_aggressive=aggressive)
    return result.id


def trigger_category_cleanup(category: str, **kwargs) -> str:
    """触发分类清理"""
    result = cleanup_by_category_task.delay(category=category, **kwargs)
    return result.id


def get_cleanup_task_status(task_id: str) -> Dict[str, Any]:
    """获取清理任务状态"""
    from celery.result import AsyncResult

    result = AsyncResult(task_id, app=celery_app)
    return {
        "task_id": task_id,
        "state": result.state,
        "result": result.result,
        "successful": result.successful(),
        "failed": result.failed(),
    }


# 导出接口
__all__ = [
    "celery_app",
    "execute_daily_cleanup",
    "cleanup_preview_report",
    "emergency_cleanup",
    "cleanup_by_category_task",
    "health_check_cleanup",
    "trigger_emergency_cleanup",
    "trigger_category_cleanup",
    "get_cleanup_task_status",
]
