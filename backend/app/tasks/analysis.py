"""
占位模块：保证 Celery include=["app.tasks.analysis", ...] 可导入。
显式导出 analysis_tasks 中需要的任务，以兼容现有配置并避免 import *。
"""

"""
占位模块：保证 Celery include=["app.tasks.analysis", ...] 可导入。
兼容性导出：analysis_tasks 中并无 execute_analysis_task/schedule_analysis_task，
测试/旧代码引用它们导致 mypy 报错。这里提供最小的转发/占位实现。
"""

from typing import Any, Dict

from .analysis_tasks import (
    analyze_product as execute_analysis_task,  # 向后兼容别名
)


def schedule_analysis_task(payload: Dict[str, Any]) -> Any:
    """向后兼容的调度函数：直接转发到 Celery 任务 delay。

    提醒：如需高级调度（ETA/Countdown/路由），请在调用处使用
    celery 的 apply_async。
    """
    return execute_analysis_task.delay(payload=payload)

__all__ = [
    "execute_analysis_task",
    "schedule_analysis_task",
]
