"""
任务调度器 - Reddit Signal Scanner
统一管理所有定时任务，包括数据清理、缓存维护等

基于Linus设计原则：
- 简单的调度器接口，复杂的逻辑在任务层
- 统一的任务状态管理
- 完整的监控和告警机制
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from celery import Celery
from celery.result import AsyncResult
from celery.schedules import crontab

from .types import JsonValue

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态枚举"""

    PENDING = "PENDING"
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RETRY = "RETRY"
    REVOKED = "REVOKED"


class SchedulerConfig:
    """调度器配置"""

    # 默认清理配置
    DEFAULT_CLEANUP_CONFIG = {
        "completed_task_days": 30,
        "failed_task_days": 7,
        "orphan_analysis_hours": 1.0,
        "inactive_user_days": 365,
    }

    # 紧急清理配置
    EMERGENCY_CLEANUP_CONFIG = {
        "completed_task_days": 15,
        "failed_task_days": 3,
        "orphan_analysis_hours": 0.5,
        "inactive_user_days": 180,
    }

    # 任务优先级
    TASK_PRIORITIES = {
        "emergency_cleanup": 10,
        "daily_cleanup": 5,
        "cache_cleanup": 3,
        "preview_report": 2,
        "health_check": 1,
    }


class TaskScheduler:
    """
    任务调度器 - 统一管理定时任务

    功能：
    - 管理数据清理任务的调度
    - 监控任务执行状态
    - 提供手动触发接口
    - 任务失败告警和恢复
    """

    def __init__(self, celery_app: Celery) -> None:
        self.celery_app = celery_app
        self.config = SchedulerConfig()

    def schedule_daily_cleanup(
        self, schedule_time: str = "2:00", config: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        调度每日清理任务

        Args:
            schedule_time: 调度时间 "HH:MM"
            config: 清理配置，默认使用DEFAULT_CLEANUP_CONFIG

        Returns:
            str: 任务调度ID
        """
        hour, minute = map(int, schedule_time.split(":"))
        cleanup_config = config or self.config.DEFAULT_CLEANUP_CONFIG

        logger.info(f"调度每日清理任务: {schedule_time}, 配置: {cleanup_config}")

        # 更新Celery Beat调度
        self.celery_app.conf.beat_schedule["daily-data-cleanup"] = {
            "task": "execute_daily_cleanup",
            "schedule": crontab(hour=hour, minute=minute),
            "options": {
                "queue": "cleanup",
                "priority": self.config.TASK_PRIORITIES["daily_cleanup"],
            },
            "kwargs": cleanup_config,
        }

        return "daily-data-cleanup"

    def trigger_emergency_cleanup(
        self, aggressive: bool = False, reason: str = "manual_trigger"
    ) -> str:
        """
        触发紧急清理

        Args:
            aggressive: 是否使用激进清理策略
            reason: 触发原因

        Returns:
            str: 任务ID
        """
        logger.warning(f"触发紧急清理: aggressive={aggressive}, reason={reason}")

        from ..core.celery_app import get_celery_app

        app = get_celery_app()
        result: Any = app.send_task(
            "emergency_cleanup", kwargs={"force_aggressive": aggressive}
        )

        # 记录紧急清理触发
        self._log_emergency_trigger(result.id, aggressive, reason)

        return str(result.id)

    def trigger_category_cleanup(
        self,
        category: str,
        days_old: Optional[int] = None,
        hours_old: Optional[float] = None,
        priority: int = 5,
    ) -> str:
        """
        触发分类清理

        Args:
            category: 清理类别
            days_old: 保留天数
            hours_old: 保留小时数
            priority: 任务优先级

        Returns:
            str: 任务ID
        """
        logger.info(f"触发分类清理: {category}")

        from ..core.celery_app import get_celery_app

        app = get_celery_app()
        result: Any = app.send_task(
            "cleanup_by_category_task",
            args=[category],
            kwargs={"days_old": days_old, "hours_old": hours_old},
            priority=priority,
            queue="cleanup",
        )

        return str(result.id)

    def get_task_status(self, task_id: str) -> dict[str, "JsonValue"]:
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            Dict: 任务状态信息
        """
        result = AsyncResult(task_id, app=self.celery_app)

        status_info = {
            "task_id": task_id,
            "state": result.state,
            "successful": result.successful(),
            "failed": result.failed(),
            "ready": result.ready(),
            "result": None,
            "error": None,
            "created_at": None,
            "started_at": None,
            "completed_at": None,
        }

        # 获取任务结果或错误信息
        if result.ready():
            if result.successful():
                status_info["result"] = result.result
                status_info["completed_at"] = datetime.utcnow().isoformat()
            elif result.failed():
                status_info["error"] = str(result.info)

        # 获取任务元信息
        if hasattr(result, "info") and isinstance(result.info, dict):
            status_info.update(
                {
                    "created_at": result.info.get("created_at"),
                    "started_at": result.info.get("started_at"),
                }
            )

        return status_info

    def get_active_tasks(self) -> list[dict[str, "JsonValue"]]:
        """
        获取活跃任务列表

        Returns:
            List: 活跃任务信息
        """
        active_tasks = []

        # 获取Celery工作节点信息
        inspect = self.celery_app.control.inspect()

        # 获取活跃任务
        active = inspect.active()
        if active:
            for worker, tasks in active.items():
                for task in tasks:
                    if "cleanup" in task.get("name", ""):
                        active_tasks.append(
                            {
                                "worker": worker,
                                "task_id": task.get("id"),
                                "name": task.get("name"),
                                "args": task.get("args"),
                                "kwargs": task.get("kwargs"),
                                "time_start": task.get("time_start"),
                            }
                        )

        return active_tasks

    def get_scheduled_tasks(self) -> list[dict[str, "JsonValue"]]:
        """
        获取已调度任务列表

        Returns:
            List: 已调度任务信息
        """
        scheduled_tasks = []

        # 从Beat调度中获取任务信息
        beat_schedule = self.celery_app.conf.beat_schedule

        for task_name, schedule_info in beat_schedule.items():
            if "cleanup" in schedule_info.get("task", ""):
                scheduled_tasks.append(
                    {
                        "name": task_name,
                        "task": schedule_info.get("task"),
                        "schedule": str(schedule_info.get("schedule")),
                        "options": schedule_info.get("options", {}),
                        "kwargs": schedule_info.get("kwargs", {}),
                    }
                )

        return scheduled_tasks

    def cancel_task(self, task_id: str, terminate: bool = False) -> bool:
        """
        取消任务

        Args:
            task_id: 任务ID
            terminate: 是否强制终止

        Returns:
            bool: 是否成功取消
        """
        logger.info(f"取消任务: {task_id}, terminate={terminate}")

        try:
            if terminate:
                self.celery_app.control.terminate(task_id)
            else:
                self.celery_app.control.revoke(task_id, terminate=False)

            return True

        except Exception as e:
            logger.error(f"取消任务失败: {task_id}, error: {e}")
            return False

    def get_task_history(
        self, task_type: Optional[str] = None, limit: int = 50
    ) -> list[dict[str, "JsonValue"]]:
        """
        获取任务历史记录

        Args:
            task_type: 任务类型过滤
            limit: 返回记录数限制

        Returns:
            List: 任务历史记录
        """
        from ..services.data_cleanup_service import get_cleanup_history

        try:
            # 从数据库获取清理历史
            history = get_cleanup_history(days=30)

            # 转换为统一格式
            task_history: list[dict[str, "JsonValue"]] = []
            for record in history[:limit]:
                task_history.append(
                    {
                        "task_type": "cleanup",
                        "executed_at": record.get("executed_at"),
                        "success": record.get("success"),
                        "result": record.get("breakdown"),
                        "duration": record.get("duration_seconds"),
                        "error": record.get("error_message"),
                    }
                )

            return task_history

        except Exception as e:
            logger.error(f"获取任务历史失败: {e}")
            return []

    def get_scheduler_status(self) -> dict[str, "JsonValue"]:
        """
        获取调度器状态

        Returns:
            Dict: 调度器状态信息
        """
        try:
            inspect = self.celery_app.control.inspect()

            # 获取工作节点状态
            stats = inspect.stats()
            active = inspect.active()
            scheduled = inspect.scheduled()

            status: dict[str, "JsonValue"] = {
                "workers": {
                    "total": len(stats) if stats else 0,
                    "active_tasks": (
                        sum(len(tasks) for tasks in active.values()) if active else 0
                    ),
                    "scheduled_tasks": (
                        sum(len(tasks) for tasks in scheduled.values())
                        if scheduled
                        else 0
                    ),
                },
                "beat_schedule": {
                    "total_scheduled": len(self.celery_app.conf.beat_schedule),
                    "cleanup_tasks": len(
                        [
                            name
                            for name, info in self.celery_app.conf.beat_schedule.items()
                            if "cleanup" in info.get("task", "")
                        ]
                    ),
                },
                "health": {
                    "broker_connected": self._check_broker_connection(),
                    "workers_available": len(stats) > 0 if stats else False,
                },
            }

            return status

        except Exception as e:
            logger.error(f"获取调度器状态失败: {e}")
            return {
                "error": str(e),
                "health": {"broker_connected": False, "workers_available": False},
            }

    def _log_emergency_trigger(
        self, task_id: str, aggressive: bool, reason: str
    ) -> None:
        """记录紧急清理触发日志"""
        logger.warning(
            "紧急清理已触发",
            extra={
                "task_id": task_id,
                "aggressive": aggressive,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        # TODO: 发送告警通知

    def _check_broker_connection(self) -> bool:
        """检查Broker连接状态"""
        try:
            # 发送ping命令检查连接
            result = self.celery_app.control.ping(timeout=1.0)
            return bool(result)
        except Exception:
            return False


class CleanupScheduler:
    """清理任务专用调度器 - 便捷接口"""

    def __init__(self, celery_app: Celery) -> None:
        self.scheduler = TaskScheduler(celery_app)

    def setup_default_schedule(self) -> None:
        """设置默认的清理调度"""
        logger.info("设置默认清理调度")

        # 每日清理：凌晨2点
        self.scheduler.schedule_daily_cleanup("2:00")

        # 缓存清理：每4小时
        self.schedule_cache_cleanup(interval_hours=4)

        logger.info("默认清理调度设置完成")

    def schedule_cache_cleanup(self, interval_hours: int = 4) -> None:
        """调度缓存清理任务"""
        self.scheduler.celery_app.conf.beat_schedule["cache-cleanup"] = {
            "task": "cleanup_by_category",
            "schedule": crontab(minute=0, hour=f"*/{interval_hours}"),
            "options": {"queue": "cleanup", "priority": 3},
            "kwargs": {"category": "expired_cache"},
        }

    def emergency_cleanup_now(self, reason: str = "manual") -> str:
        """立即执行紧急清理"""
        return self.scheduler.trigger_emergency_cleanup(aggressive=False, reason=reason)

    def aggressive_cleanup_now(self, reason: str = "emergency") -> str:
        """立即执行激进清理"""
        return self.scheduler.trigger_emergency_cleanup(aggressive=True, reason=reason)


# 全局调度器实例
_scheduler_instance: Optional[TaskScheduler] = None


def get_scheduler(celery_app: Optional[Celery] = None) -> TaskScheduler:
    """获取全局调度器实例"""
    global _scheduler_instance

    if _scheduler_instance is None:
        if celery_app is None:
            from ..core.celery_app import get_celery_app

            celery_app = get_celery_app()

        _scheduler_instance = TaskScheduler(celery_app)

    return _scheduler_instance


def get_cleanup_scheduler(celery_app: Optional[Celery] = None) -> CleanupScheduler:
    """获取清理调度器实例"""
    if celery_app is None:
        from ..core.celery_app import get_celery_app

        celery_app = get_celery_app()

    return CleanupScheduler(celery_app)


# 导出接口
__all__ = [
    "TaskScheduler",
    "CleanupScheduler",
    "TaskStatus",
    "SchedulerConfig",
    "get_scheduler",
    "get_cleanup_scheduler",
]
