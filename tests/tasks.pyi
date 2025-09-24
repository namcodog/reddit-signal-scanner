from celery.app.task import Task as CeleryTask
from typing import Dict, Any

quick_echo: CeleryTask
sleep_task: CeleryTask
flaky_task: CeleryTask
always_fail: CeleryTask

__all__: list[str]
