import os
from typing import Any, Dict

import pytest

pytestmark = pytest.mark.integration


def test_health_check_task_executes(celery_setup: Any) -> None:
    """Smoke test: worker is up, and a built-in task executes successfully."""
    from backend.app.tasks.analysis_tasks import analysis_health_check

    result = analysis_health_check.delay()
    data: Dict[str, Any] = result.get(timeout=30)
    assert isinstance(data, dict)
    assert data.get("service") == "analysis_tasks"
    assert data.get("status") in {"healthy", "unhealthy"}


def test_quick_echo_task_executes(celery_setup: Any) -> None:
    """Sanity: a test-local task runs on the worker and returns payload."""
    from tests import tasks as test_tasks

    payload = {"value": 42}
    result = test_tasks.quick_echo.delay(payload)
    data = result.get(timeout=30)
    assert data["ok"] is True
    assert data["payload"] == payload

