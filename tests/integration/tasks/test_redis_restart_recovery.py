import os
import subprocess
import time
from typing import Any

import pytest

pytestmark = pytest.mark.integration


RUN = os.getenv("RUN_REDIS_RESTART_TESTS") == "1"


@pytest.mark.skipif(not RUN, reason="Set RUN_REDIS_RESTART_TESTS=1 to enable Redis restart test")
def test_redis_restart_recovery(celery_setup: Any) -> None:
    """Experimental: restart Redis and ensure a new task can still run.

    Disabled by default; requires Docker and a container named 'redis'.
    """
    from tests import tasks as test_tasks

    # Sanity: run a quick task before restart
    assert test_tasks.quick_echo.delay({"pre": True}).get(timeout=30)["ok"] is True

    # Restart Redis using Docker (assumes container is named 'redis')
    try:
        subprocess.run(["docker", "restart", "redis"], check=True, capture_output=True)
    except Exception:
        pytest.skip("Unable to restart Redis (docker missing or container not named 'redis')")

    # Wait a bit for Redis to come back
    time.sleep(2.0)

    # Run another task; worker/broker should reconnect and succeed
    out = test_tasks.quick_echo.delay({"post": True}).get(timeout=60)
    assert out["ok"] is True
