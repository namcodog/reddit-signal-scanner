from typing import Any

import pytest

pytestmark = pytest.mark.integration


def test_autoretry_flaky_task_succeeds_after_retries(celery_setup: Any) -> None:
    """Flaky task should succeed via Celery autoretry/backoff after a few attempts."""
    from tests import tasks as test_tasks

    res = test_tasks.flaky_task.delay()
    assert res.get(timeout=120) == "ok"
    assert res.successful() is True
