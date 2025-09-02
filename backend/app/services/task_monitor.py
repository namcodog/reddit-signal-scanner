"""
Reddit Signal Scanner - 任务监控服务 (统一SSE架构)

基于极简设计的任务状态监控：
- 集成统一SSE推送系统
- 数据库状态变化监听
- 自动进度推送和连接管理
"""

import logging
from typing import Dict, Optional

from ..core.sse import (
    get_sse_service,
    create_progress_event_sync,
    create_completed_event_sync,
    create_error_event_sync,
)

logger = logging.getLogger(__name__)


class TaskMonitor:
    """任务监控服务 - 极简设计

    职责：
    - 监听任务状态变化
    - 自动推送SSE事件
    - 管理任务生命周期
    """

    def __init__(self) -> None:
        self.monitored_tasks: Dict[str, str] = {}  # task_id -> last_status
        self.sse_service = get_sse_service()
        logger.info("TaskMonitor initialized with unified SSE")

    def start_monitoring(self, task_id: str) -> None:
        """开始监控任务

        Args:
            task_id: 任务ID
        """
        self.monitored_tasks[task_id] = "started"
        create_progress_event_sync(task_id, 0, "任务监控已启动")
        logger.info(f"Started monitoring task: {task_id}")

    def update_progress(self, task_id: str, progress: int, message: str) -> None:
        """更新任务进度

        Args:
            task_id: 任务ID
            progress: 进度百分比 (0-100)
            message: 进度描述
        """
        if task_id in self.monitored_tasks:
            create_progress_event_sync(task_id, progress, message)
            self.monitored_tasks[task_id] = f"progress_{progress}"
            logger.debug(f"Updated progress for {task_id}: {progress}% - {message}")

    def complete_task(self, task_id: str, message: str = "任务完成") -> None:
        """标记任务完成

        Args:
            task_id: 任务ID
            message: 完成消息
        """
        if task_id in self.monitored_tasks:
            create_completed_event_sync(task_id, message)
            self.monitored_tasks[task_id] = "completed"
            logger.info(f"Task completed: {task_id}")

    def fail_task(self, task_id: str, error_message: str) -> None:
        """标记任务失败

        Args:
            task_id: 任务ID
            error_message: 错误信息
        """
        if task_id in self.monitored_tasks:
            create_error_event_sync(task_id, error_message)
            self.monitored_tasks[task_id] = "failed"
            logger.error(f"Task failed: {task_id} - {error_message}")

    def stop_monitoring(self, task_id: str) -> None:
        """停止监控任务

        Args:
            task_id: 任务ID
        """
        if task_id in self.monitored_tasks:
            del self.monitored_tasks[task_id]
            logger.info(f"Stopped monitoring task: {task_id}")

    def get_monitored_tasks(self) -> Dict[str, str]:
        """获取当前监控的任务列表

        Returns:
            任务ID到状态的映射
        """
        return self.monitored_tasks.copy()

    def get_connection_count(self) -> int:
        """获取SSE连接数

        Returns:
            当前活跃连接数
        """
        return self.sse_service.get_connection_count()


# 全局任务监控器实例
_task_monitor: Optional[TaskMonitor] = None


def get_task_monitor() -> TaskMonitor:
    """获取全局任务监控器实例"""
    global _task_monitor
    if _task_monitor is None:
        _task_monitor = TaskMonitor()
    return _task_monitor


# 便捷接口
def start_task_monitoring(task_id: str) -> None:
    """开始监控任务 - 便捷接口"""
    monitor = get_task_monitor()
    monitor.start_monitoring(task_id)


def update_task_progress(task_id: str, progress: int, message: str) -> None:
    """更新任务进度 - 便捷接口"""
    monitor = get_task_monitor()
    monitor.update_progress(task_id, progress, message)


def complete_task(task_id: str, message: str = "任务完成") -> None:
    """完成任务 - 便捷接口"""
    monitor = get_task_monitor()
    monitor.complete_task(task_id, message)


def fail_task(task_id: str, error_message: str) -> None:
    """任务失败 - 便捷接口"""
    monitor = get_task_monitor()
    monitor.fail_task(task_id, error_message)


# 使用示例：
#
# # 开始监控
# start_task_monitoring("task-123")
#
# # 更新进度
# update_task_progress("task-123", 25, "正在处理数据")
#
# # 完成任务
# complete_task("task-123", "数据处理完成")
#
# # 或者任务失败
# fail_task("task-123", "数据源连接失败")
