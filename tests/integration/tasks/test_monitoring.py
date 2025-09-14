import time
from typing import Any, Dict

import pytest

from backend.app.core.celery_app import get_task_status

pytestmark = pytest.mark.integration


def test_get_task_status_flow(celery_setup: Any) -> None:
    from tests import tasks as test_tasks

    res = test_tasks.sleep_task.delay(0.8)
    # Immediately query status
    s1: Dict[str, Any] = get_task_status(res.id)
    assert s1["task_id"] == res.id
    assert s1["state"] in {"PENDING", "RECEIVED", "STARTED", "SUCCESS"}

    # Wait and query again
    final = res.get(timeout=30)
    assert final == "slept"
    s2: Dict[str, Any] = get_task_status(res.id)
    assert s2["successful"] is True
    assert s2["state"] in {"SUCCESS"}

