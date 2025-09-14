import time

import pytest

pytestmark = pytest.mark.integration


def test_concurrent_short_tasks_finish_within_budget(celery_setup):
    """Submit multiple short tasks; expect completion within a lenient budget.

    This is a minimal concurrency sanity check, not a benchmark.
    """
    from tests import tasks as test_tasks

    N = 8
    D = 0.6
    start = time.time()
    results = [test_tasks.sleep_task.delay(D) for _ in range(N)]
    for r in results:
        assert r.get(timeout=30) == "slept"
    duration = time.time() - start

    # Lenient upper bound to avoid flakiness across environments
    assert duration < 20.0

