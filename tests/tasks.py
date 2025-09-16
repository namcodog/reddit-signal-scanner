"""Test-local Celery tasks used by integration tests (PRD-08-05)."""

from __future__ import annotations

import time
from typing import Any, Dict, cast

from celery.app.task import Task as CeleryTask

from backend.app.core.celery_app import get_celery_app


celery_app = get_celery_app()


def _quick_echo(payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return {"ok": True, "payload": payload or {}}


def _sleep_task(duration: float = 0.8) -> str:
    time.sleep(max(0.0, float(duration)))
    return "slept"


def _flaky_task(self: CeleryTask) -> str:
    if int(getattr(self.request, "retries", 0)) < 2:
        raise ConnectionError("temporary network issue")
    return "ok"


def _always_fail() -> str:
    raise RuntimeError("permanent failure for testing")


quick_echo = cast(
    CeleryTask,
    celery_app.task(name="tests.quick_echo", queue="monitoring_queue")(_quick_echo),
)
sleep_task = cast(
    CeleryTask,
    celery_app.task(name="tests.sleep", queue="analysis_queue")(_sleep_task),
)
flaky_task = cast(
    CeleryTask,
    celery_app.task(
        bind=True,
        name="tests.flaky",
        queue="analysis_queue",
        autoretry_for=(ConnectionError,),
        retry_backoff=True,
        retry_backoff_max=10,
        max_retries=3,
    )(_flaky_task),
)
always_fail = cast(
    CeleryTask,
    celery_app.task(name="tests.always_fail", queue="analysis_queue", max_retries=0)(_always_fail),
)


__all__ = ["quick_echo", "sleep_task", "flaky_task", "always_fail"]
