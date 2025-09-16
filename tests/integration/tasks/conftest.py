"""
Celery integration test fixtures for PRD-08-05

Goals:
- Bind pytest-celery to our project Celery app
- Register project and test-local tasks to the worker
- Isolate broker/backend to a test Redis DB
- Gracefully skip if Redis/pytest-celery is unavailable
"""

import os
from typing import Any, Set

import pytest


# Ensure broker/result backend isolation before any Celery app is created
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
# Provide a sensible default DATABASE_URL for sync/async DB access in tasks
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/reddit_test"
)


def _redis_available() -> bool:
    try:
        import redis  # type: ignore

        r = redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/15"))
        r.ping()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session", autouse=True)
def _skip_if_missing_runtime() -> None:
    """Skip this test suite if runtime prerequisites are missing."""
    try:
        import pytest_celery  # noqa: F401
    except Exception:
        pytest.skip("pytest-celery not installed; skip Celery integration tests")

    if not _redis_available():
        pytest.skip("Redis unavailable at REDIS_URL; skip Celery integration tests")


@pytest.fixture
def default_worker_app():  # type: ignore[override]
    """Provide our project Celery app to pytest-celery default worker.

    Returning the app instance allows the plugin to spawn a worker with our
    configuration (queues, acks_late, prefetch, etc.).
    """
    from backend.app.core.celery_app import get_celery_app

    app = get_celery_app()
    # Keep worker deterministic and robust for tests
    app.conf.worker_prefetch_multiplier = 1
    app.conf.task_acks_late = True
    app.conf.task_reject_on_worker_lost = True
    return app


@pytest.fixture
def default_worker_tasks(default_worker_tasks: Set[Any]) -> Set[Any]:  # type: ignore[override]
    """Register project and test-local tasks modules to the worker container."""
    # Test-local tasks (defined under tests/tasks.py)
    from tests import tasks as test_tasks

    # Project task modules
    import backend.app.tasks.analysis_tasks as analysis_tasks
    import backend.app.tasks.maintenance as maintenance_tasks

    default_worker_tasks.update({test_tasks, analysis_tasks, maintenance_tasks})
    return default_worker_tasks

