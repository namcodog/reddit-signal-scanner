import os
import time

import pytest

pytestmark = pytest.mark.integration


RUN = os.getenv("RUN_WORKER_CRASH_TESTS") == "1"


@pytest.mark.skipif(not RUN, reason="Set RUN_WORKER_CRASH_TESTS=1 to enable crash recovery test")
def test_worker_crash_and_recover(celery_setup):
    """Experimental: simulate worker stop and restart during a running task.

    This test relies on pytest-celery's worker control APIs and may be flaky
    across environments. Disabled by default.
    """
    from tests import tasks as test_tasks

    # Start a long-running task
    res = test_tasks.sleep_task.delay(5.0)

    # Attempt to stop the worker shortly after the task starts
    worker = getattr(celery_setup, "worker", None)
    if worker is None or not hasattr(worker, "teardown"):
        pytest.skip("celery_setup.worker control not available; skip")

    time.sleep(0.5)
    try:
        worker.teardown()  # stop current worker
    except Exception:
        # best-effort stop; continue
        pass

    # Start a new worker instance
    from celery import Celery
    from pytest_celery import CeleryTestWorker  # type: ignore

    app: Celery = celery_setup.app  # reuse configured app
    new_worker = CeleryTestWorker(celery_setup.container, app=app)
    try:
        # The task should either complete or be re-executed due to acks_late
        assert res.get(timeout=60) == "slept"
    finally:
        new_worker.teardown()

