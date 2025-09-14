"""
Test-local Celery tasks used by integration tests (PRD-08-05).

These tasks are registered to the test worker via the
`default_worker_tasks` fixture in tests/integration/tasks/conftest.py.
"""

import time
from typing import Any, Dict

from backend.app.core.celery_app import get_celery_app


celery_app = get_celery_app()


@celery_app.task(name="tests.quick_echo", queue="monitoring_queue")
def quick_echo(payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """A quick task that echoes the payload for sanity checks."""
    return {"ok": True, "payload": payload or {}}


@celery_app.task(name="tests.sleep", queue="analysis_queue")
def sleep_task(duration: float = 0.8) -> str:
    """Sleep for given seconds to simulate a running task."""
    time.sleep(max(0.0, float(duration)))
    return "slept"


@celery_app.task(
    bind=True,
    name="tests.flaky",
    queue="analysis_queue",
    autoretry_for=(ConnectionError,),
    retry_backoff=True,
    retry_backoff_max=10,
    max_retries=3,
)
def flaky_task(self) -> str:  # type: ignore[no-redef]
    """Fail with ConnectionError for first attempts, then succeed.

    Uses Celery's built-in `self.request.retries` to determine attempt number,
    so it works reliably across worker processes.
    """
    if int(getattr(self.request, "retries", 0)) < 2:
        raise ConnectionError("temporary network issue")
    return "ok"


@celery_app.task(name="tests.always_fail", queue="analysis_queue", max_retries=0)
def always_fail() -> str:
    """Always raise to simulate a permanent failure."""
    raise RuntimeError("permanent failure for testing")

