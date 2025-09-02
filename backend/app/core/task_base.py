"""
统一任务基类模块 - Reddit Signal Scanner
基于Linus设计原则：消除特殊情况，统一处理逻辑

核心功能：
- 统一的错误处理和重试机制
- 标准化的任务监控和日志记录
- 可配置的告警和通知系统
- 任务生命周期管理
"""

import logging
from typing import Any, Dict, Optional, Tuple
from datetime import datetime
import traceback

from celery import Task
from sqlalchemy.exc import SQLAlchemyError

from .celery_config import get_celery_config

logger = logging.getLogger(__name__)


class BaseUnifiedTask(Task):
    """
    统一任务基类 - 消除所有任务类型的特殊情况

    基于Linus原则：
    - 统一的错误处理逻辑（消除重复的try-catch）
    - 配置驱动的重试策略（消除硬编码）
    - 标准化的监控和日志（统一接口）
    """

    def __init__(self) -> None:
        super().__init__()
        self.config = get_celery_config()

        # 从配置加载重试设置
        self.autoretry_for = tuple(self._get_exception_classes())
        self.retry_kwargs = {
            "max_retries": self.config.retry.max_retries,
            "countdown": self.config.retry.countdown,
        }
        self.retry_backoff = self.config.retry.backoff
        self.retry_backoff_max = self.config.retry.backoff_max

    def _get_exception_classes(self) -> list:
        """从配置获取需要重试的异常类"""
        exception_classes = []
        for exc_name in self.config.retry.autoretry_for:
            try:
                module_name, class_name = exc_name.rsplit(".", 1)
                module = __import__(module_name, fromlist=[class_name])
                exc_class = getattr(module, class_name)
                exception_classes.append(exc_class)
            except (ImportError, AttributeError) as e:
                logger.warning(f"无法导入异常类 {exc_name}: {e}")

        # 添加基础异常类
        exception_classes.extend([SQLAlchemyError, ConnectionError])
        return exception_classes

    def on_success(self, retval: Any, task_id: str, args: Tuple, kwargs: Dict) -> None:
        """任务成功回调 - 统一的成功处理逻辑"""
        task_name = self.get_task_name()
        duration = self._get_task_duration()

        logger.info(
            f"任务执行成功: {task_name} [{task_id}]",
            extra={
                "task_id": task_id,
                "task_name": task_name,
                "duration_seconds": duration,
                "result_size": len(str(retval)) if retval else 0,
                "success": True,
            },
        )

        # 记录任务统计
        self._record_task_stats(task_id, task_name, "success", duration, retval)

    def on_failure(
        self, exc: Exception, task_id: str, args: Tuple, kwargs: Dict, einfo: Any
    ) -> None:
        """任务失败回调 - 统一的失败处理逻辑"""
        task_name = self.get_task_name()
        duration = self._get_task_duration()
        retry_count = self.request.retries if hasattr(self, "request") else 0

        logger.error(
            f"任务执行失败: {task_name} [{task_id}]: {exc}",
            extra={
                "task_id": task_id,
                "task_name": task_name,
                "exception": str(exc),
                "exception_type": type(exc).__name__,
                "retry_count": retry_count,
                "duration_seconds": duration,
                "traceback": traceback.format_exc(),
                "success": False,
            },
        )

        # 记录任务统计
        self._record_task_stats(task_id, task_name, "failure", duration, None, str(exc))

        # 发送失败告警（如果需要）
        if retry_count >= self.config.retry.max_retries:
            self._send_failure_alert(task_id, exc, task_name, args, kwargs)

    def on_retry(
        self, exc: Exception, task_id: str, args: Tuple, kwargs: Dict, einfo: Any
    ) -> None:
        """任务重试回调 - 统一的重试处理逻辑"""
        task_name = self.get_task_name()
        retry_count = self.request.retries if hasattr(self, "request") else 0

        logger.warning(
            f"任务重试: {task_name} [{task_id}]: {exc}",
            extra={
                "task_id": task_id,
                "task_name": task_name,
                "exception": str(exc),
                "exception_type": type(exc).__name__,
                "retry_count": retry_count,
                "max_retries": self.config.retry.max_retries,
                "next_retry_delay": self._calculate_retry_delay(retry_count),
                "retrying": True,
            },
        )

    def get_task_name(self) -> str:
        """获取任务名称 - 统一命名规范"""
        if hasattr(self, "name") and self.name:
            return self.name
        return self.__class__.__name__.replace("Task", "").lower()

    def _get_task_duration(self) -> float:
        """计算任务执行时间"""
        if not hasattr(self, "request") or not hasattr(self.request, "started_at"):
            return 0.0

        try:
            start_time = datetime.fromisoformat(self.request.started_at)
            return (datetime.now() - start_time).total_seconds()
        except (ValueError, TypeError):
            return 0.0

    def _calculate_retry_delay(self, retry_count: int) -> int:
        """计算重试延迟时间"""
        if not self.config.retry.backoff:
            return self.config.retry.countdown

        # 指数退避算法
        delay = self.config.retry.countdown * (2**retry_count)
        return min(delay, self.config.retry.backoff_max)

    def _record_task_stats(
        self,
        task_id: str,
        task_name: str,
        status: str,
        duration: float,
        result: Any = None,
        error: Optional[str] = None,
    ) -> None:
        """记录任务统计信息"""
        if not self.config.monitoring.task_stats_enable:
            return

        try:
            # 这里可以集成具体的统计系统
            # 比如写入Redis、数据库或发送到监控系统
            stats_data = {
                "task_id": task_id,
                "task_name": task_name,
                "status": status,
                "duration": duration,
                "timestamp": datetime.utcnow().isoformat(),
                "result_available": result is not None,
                "error": error,
            }

            # 简单实现：记录到日志
            logger.info(f"任务统计: {stats_data}")

            # TODO: 可以扩展到具体的统计后端
            # self._send_to_stats_backend(stats_data)

        except Exception as e:
            logger.error(f"记录任务统计失败: {e}")

    def _send_failure_alert(
        self, task_id: str, exc: Exception, task_name: str, args: Tuple, kwargs: Dict
    ) -> None:
        """发送任务失败告警"""
        try:
            # 构造告警信息
            alert_data = {
                "task_id": task_id,
                "task_name": task_name,
                "exception": str(exc),
                "exception_type": type(exc).__name__,
                "args": str(args)[:500],  # 限制长度
                "kwargs": str(kwargs)[:500],
                "timestamp": datetime.utcnow().isoformat(),
                "retry_count": getattr(self.request, "retries", 0),
            }

            # TODO: 集成具体的告警系统
            # 可以发送邮件、Slack消息、钉钉消息等
            logger.error(f"任务失败告警: {alert_data}")

            # 示例：如果有通知服务，可以这样调用
            # from ..services.notification_service import send_task_failure_alert
            # send_task_failure_alert(alert_data)

        except Exception as e:
            logger.error(f"发送失败告警异常: {e}")


class AnalysisTask(BaseUnifiedTask):
    """分析任务基类 - 继承统一基类的所有特性"""

    def __init__(self) -> None:
        super().__init__()
        # 分析任务的特定配置
        self.queue = "analysis_queue"

    def validate_analysis_input(self, *args, **kwargs) -> bool:
        """验证分析任务输入 - 分析任务的通用验证逻辑"""
        try:
            # 基础输入验证
            if not args and not kwargs:
                raise ValueError("分析任务缺少输入参数")

            # 可以扩展具体的验证规则
            return True

        except Exception as e:
            logger.error(f"分析任务输入验证失败: {e}")
            return False


class MaintenanceTask(BaseUnifiedTask):
    """维护任务基类 - 继承统一基类的所有特性"""

    def __init__(self) -> None:
        super().__init__()
        # 维护任务的特定配置
        self.queue = "maintenance_queue"
        # 维护任务通常重试次数更多
        self.retry_kwargs["max_retries"] = self.config.retry.max_retries + 2


class CleanupTask(BaseUnifiedTask):
    """清理任务基类 - 继承统一基类的所有特性"""

    def __init__(self) -> None:
        super().__init__()
        # 清理任务的特定配置
        self.queue = "cleanup_queue"

    def acquire_cleanup_lock(self, timeout: int = 3600) -> bool:
        """获取清理锁 - 防止并发清理任务"""
        try:
            from ..core.cleanup_lock import get_cleanup_lock

            cleanup_lock = get_cleanup_lock()
            task_info = {
                "task_id": self.request.id if hasattr(self, "request") else "unknown",
                "task_type": self.get_task_name(),
                "timestamp": datetime.utcnow().isoformat(),
            }

            # 尝试获取锁
            return cleanup_lock.acquire(timeout=timeout, task_info=task_info)

        except Exception as e:
            logger.error(f"获取清理锁失败: {e}")
            return False


class MonitoringTask(BaseUnifiedTask):
    """监控任务基类 - 继承统一基类的所有特性"""

    def __init__(self) -> None:
        super().__init__()
        # 监控任务的特定配置
        self.queue = "monitoring_queue"
        # 监控任务失败不需要过多重试
        self.retry_kwargs["max_retries"] = 1


# 便捷函数 - 用于外部创建任务
def create_analysis_task(func):
    """装饰器：创建分析任务"""

    class AnalysisTaskWrapper(AnalysisTask):
        def run(self, *args, **kwargs):
            if not self.validate_analysis_input(*args, **kwargs):
                raise ValueError("分析任务输入验证失败")
            return func(*args, **kwargs)

    return AnalysisTaskWrapper()


def create_maintenance_task(func):
    """装饰器：创建维护任务"""

    class MaintenanceTaskWrapper(MaintenanceTask):
        def run(self, *args, **kwargs):
            return func(*args, **kwargs)

    return MaintenanceTaskWrapper()


def create_cleanup_task(func):
    """装饰器：创建清理任务"""

    class CleanupTaskWrapper(CleanupTask):
        def run(self, *args, **kwargs):
            if not self.acquire_cleanup_lock():
                raise RuntimeError("无法获取清理锁，任务跳过")
            return func(*args, **kwargs)

    return CleanupTaskWrapper()


def create_monitoring_task(func):
    """装饰器：创建监控任务"""

    class MonitoringTaskWrapper(MonitoringTask):
        def run(self, *args, **kwargs):
            return func(*args, **kwargs)

    return MonitoringTaskWrapper()
