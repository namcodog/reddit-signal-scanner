"""
统一Celery应用实例 - Reddit Signal Scanner
基于Linus设计原则：单一职责，消除重复实例

核心功能：
- 全局唯一的Celery应用实例
- 配置驱动的自动化设置
- 统一的任务发现和注册
- Beat调度配置集中管理
"""

import logging
from typing import Dict, Any

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_ready, worker_shutdown, task_prerun, task_postrun

from .celery_config import get_celery_settings
from .task_base import BaseUnifiedTask

logger = logging.getLogger(__name__)

# 全局唯一Celery应用实例
celery_app: Celery = None


def create_celery_app() -> Celery:
    """
    创建统一的Celery应用实例

    基于Linus原则：
    - 单一实例，消除多个celery_app的混乱
    - 配置驱动，消除硬编码配置
    - 自动发现，消除手动注册任务的特殊情况

    Returns:
        Celery: 配置完整的Celery应用实例
    """
    global celery_app

    if celery_app is not None:
        return celery_app

    logger.info("初始化统一Celery应用")

    # 创建Celery实例
    celery_app = Celery(
        "reddit_signal_scanner",
        # 自动发现任务模块
        include=[
            "app.tasks.data_cleanup",
            "app.tasks.analysis",
            "app.tasks.maintenance",
            "app.services.analysis_engine",
            "app.services.data_cleanup_service",
        ],
    )

    # 加载配置
    settings = get_celery_settings()
    celery_app.conf.update(settings)

    # 设置默认任务基类
    celery_app.Task = BaseUnifiedTask

    # 配置Beat调度
    _configure_beat_schedule(celery_app)

    # 注册信号处理器
    _register_signal_handlers()

    logger.info("Celery应用初始化完成")
    return celery_app


def get_celery_app() -> Celery:
    """
    获取全局Celery应用实例

    Returns:
        Celery: 全局唯一的Celery应用实例
    """
    if celery_app is None:
        return create_celery_app()
    return celery_app


def _configure_beat_schedule(app: Celery) -> None:
    """
    配置Celery Beat调度任务

    基于Linus原则：配置集中管理，消除分散定义

    Args:
        app: Celery应用实例
    """
    beat_schedule = {
        # 每日数据清理 - 凌晨2点执行
        "daily-data-cleanup": {
            "task": "app.tasks.data_cleanup.execute_daily_cleanup",
            "schedule": crontab(hour=2, minute=0),
            "options": {"queue": "cleanup_queue", "priority": 5},
            "kwargs": {
                "completed_task_days": 30,
                "failed_task_days": 7,
                "orphan_analysis_hours": 1.0,
                "inactive_user_days": 365,
            },
        },
        # 每周清理预览 - 周一凌晨1点执行
        "weekly-cleanup-preview": {
            "task": "app.tasks.data_cleanup.cleanup_preview_report",
            "schedule": crontab(hour=1, minute=0, day_of_week=1),
            "options": {"queue": "cleanup_queue", "priority": 3},
        },
        # 缓存维护 - 每4小时执行
        "cache-maintenance": {
            "task": "app.tasks.maintenance.cache_maintenance",
            "schedule": crontab(minute=0, hour="*/4"),
            "options": {"queue": "maintenance_queue", "priority": 4},
        },
        # 系统健康检查 - 每小时执行
        "system-health-check": {
            "task": "app.tasks.monitoring.system_health_check",
            "schedule": crontab(minute=30),  # 每小时的30分钟执行
            "options": {"queue": "monitoring_queue", "priority": 2},
        },
        # 任务队列监控 - 每5分钟执行
        "queue-monitoring": {
            "task": "app.tasks.monitoring.queue_monitoring",
            "schedule": crontab(minute="*/5"),
            "options": {"queue": "monitoring_queue", "priority": 1},
        },
    }

    app.conf.beat_schedule = beat_schedule
    app.conf.timezone = "UTC"

    logger.info(f"配置了 {len(beat_schedule)} 个定时任务")


def _register_signal_handlers() -> None:
    """
    注册Celery信号处理器 - 统一的监控和日志处理

    基于Linus原则：统一处理，消除重复的信号处理逻辑
    """

    @worker_ready.connect
    def worker_ready_handler(sender=None, **kwargs):
        """Worker启动信号处理"""
        logger.info(f"Celery Worker已启动: {sender}")

        # 可以在这里执行初始化检查
        _perform_startup_checks()

    @worker_shutdown.connect
    def worker_shutdown_handler(sender=None, **kwargs):
        """Worker关闭信号处理"""
        logger.info(f"Celery Worker正在关闭: {sender}")

        # 可以在这里执行清理工作
        _perform_shutdown_cleanup()

    @task_prerun.connect
    def task_prerun_handler(task_id=None, task=None, args=None, kwargs=None, **extra):
        """任务执行前信号处理"""
        logger.debug(f"任务开始执行: {task.name if task else 'unknown'} [{task_id}]")

        # 记录任务开始时间（用于持续时间计算）
        if task and hasattr(task, "request"):
            task.request.started_at = str(
                task.request.called_directly or task.request.eta
            )

    @task_postrun.connect
    def task_postrun_handler(
        task_id=None,
        task=None,
        args=None,
        kwargs=None,
        retval=None,
        state=None,
        **extra,
    ):
        """任务执行后信号处理"""
        logger.debug(
            f"任务执行完成: {task.name if task else 'unknown'} [{task_id}] - 状态: {state}"
        )


def _perform_startup_checks() -> None:
    """执行启动时的系统检查"""
    try:
        # 检查Redis连接
        from ..core.redis_client import get_redis_client

        redis_client = get_redis_client()
        redis_client.ping()
        logger.info("Redis连接检查通过")

        # 检查数据库连接
        from ..core.database import SessionLocal

        with SessionLocal() as db:
            db.execute("SELECT 1")
        logger.info("数据库连接检查通过")

        # 检查任务注册
        registered_tasks = list(celery_app.tasks.keys())
        logger.info(f"已注册任务数量: {len(registered_tasks)}")

    except Exception as e:
        logger.error(f"启动检查失败: {e}")


def _perform_shutdown_cleanup() -> None:
    """执行关闭时的清理工作"""
    try:
        logger.info("执行Celery Worker关闭清理")

        # 可以在这里添加清理逻辑
        # 比如：关闭数据库连接池、清理临时文件等

    except Exception as e:
        logger.error(f"关闭清理失败: {e}")


# 任务状态查询工具函数
def get_task_status(task_id: str) -> Dict[str, Any]:
    """
    获取任务状态信息

    Args:
        task_id: 任务ID

    Returns:
        Dict: 任务状态信息
    """
    from celery.result import AsyncResult

    app = get_celery_app()
    result = AsyncResult(task_id, app=app)

    return {
        "task_id": task_id,
        "state": result.state,
        "result": result.result,
        "traceback": result.traceback,
        "successful": result.successful(),
        "failed": result.failed(),
        "ready": result.ready(),
        "info": result.info,
    }


def get_active_tasks() -> Dict[str, Any]:
    """
    获取活跃任务信息

    Returns:
        Dict: 活跃任务统计
    """
    app = get_celery_app()

    # 获取活跃任务
    inspect = app.control.inspect()
    active_tasks = inspect.active()
    scheduled_tasks = inspect.scheduled()
    reserved_tasks = inspect.reserved()

    return {
        "active": active_tasks,
        "scheduled": scheduled_tasks,
        "reserved": reserved_tasks,
        "total_active": sum(len(tasks) for tasks in (active_tasks or {}).values()),
        "total_scheduled": sum(
            len(tasks) for tasks in (scheduled_tasks or {}).values()
        ),
        "total_reserved": sum(len(tasks) for tasks in (reserved_tasks or {}).values()),
    }


def get_queue_lengths() -> Dict[str, int]:
    """
    获取队列长度信息

    Returns:
        Dict: 各队列的任务数量
    """
    try:
        from ..core.redis_client import get_redis_client

        redis_client = get_redis_client()

        queues = [
            "analysis_queue",
            "maintenance_queue",
            "cleanup_queue",
            "monitoring_queue",
        ]
        queue_lengths = {}

        for queue in queues:
            length = redis_client.llen(queue)
            queue_lengths[queue] = length

        return queue_lengths

    except Exception as e:
        logger.error(f"获取队列长度失败: {e}")
        return {}


# 立即创建全局实例（延迟导入时使用）
def init_celery_app():
    """初始化Celery应用（供外部调用）"""
    return create_celery_app()


# 向后兼容性：导出celery_app实例
def get_legacy_celery_app():
    """
    获取向后兼容的celery_app实例
    用于现有代码的平滑迁移
    """
    return get_celery_app()


# 便捷导入
app = get_celery_app  # 便捷函数引用
