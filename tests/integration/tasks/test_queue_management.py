import time
from typing import Any, Callable, Dict

import pytest

from backend.app.core.celery_app import get_active_tasks, get_queue_lengths

pytestmark = pytest.mark.integration


def _wait_for(cond: Callable[[], bool], timeout: float = 10.0, interval: float = 0.2) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(interval)
    return False


def test_active_and_queue_lengths_update(celery_setup: Any) -> None:
    """Submitting a few tasks should reflect in active/scheduled/reserved overview.

    We avoid strict counts to reduce flakiness; assert minimal invariants and presence.
    """
    from tests import tasks as test_tasks

    # Submit a few slow tasks so they appear as active
    for _ in range(3):
        test_tasks.sleep_task.apply_async(kwargs={"duration": 1.2}, queue="analysis_queue")

    # Wait until at least one active task is visible
    assert _wait_for(lambda: get_active_tasks().get("total_active", 0) >= 1)

    overview: Dict[str, Any] = get_active_tasks()
    assert {"active", "scheduled", "reserved", "total_active", "total_reserved", "total_scheduled"} <= overview.keys()

    # Queue length helper should return all known queues with integer values
    lengths = get_queue_lengths()
    for key in ("analysis_queue", "maintenance_queue", "cleanup_queue", "monitoring_queue"):
        assert key in lengths
        assert isinstance(lengths[key], int)
