import os
from typing import Any

import pytest

pytestmark = pytest.mark.integration


def test_permanent_failure_is_reported(celery_setup: Any) -> None:
    """A permanently failing task should end in FAILURE state."""
    from tests import tasks as test_tasks

    res = test_tasks.always_fail.delay()
    with pytest.raises(Exception):
        _ = res.get(timeout=30)
    assert res.failed() is True


def _db_available() -> bool:
    try:
        # Use the sync session from the code under test to probe DB connectivity
        from backend.app.core.database import get_session_sync
        from sqlalchemy import text

        sess = get_session_sync()
        try:
            sess.execute(text("SELECT 1"))
            return True
        finally:
            sess.close()
    except Exception:
        return False


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL unavailable; skip DB-backed DLQ test")
def test_dead_letter_move_and_retry_via_tasks(celery_setup: Any) -> None:
    """End-to-end DLQ path using project helpers if DB is available.

    1) Create a failed task row with retry_count>=3
    2) Run `move_failed_tasks_to_dead_letter`
    3) Retry the moved task via `retry_dead_letter_task`
    """
    from uuid import uuid4

    from sqlalchemy import select
    from backend.app.core.database import get_session_sync
    from backend.app.models.task import Task, TaskStatus
    from backend.app.models.user import User
    from backend.app.tasks.analysis_tasks import (
        move_failed_tasks_to_dead_letter,
        retry_dead_letter_task,
    )

    # Prepare a user and a failed task row
    sess = get_session_sync()
    try:
        user = User(
            email=f"dlq_test_{uuid4().hex[:8]}@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        sess.add(user)
        sess.commit()
        sess.refresh(user)

        task = Task(
            user_id=user.id,
            product_description="Dead-letter testcase product",
            status=TaskStatus.FAILED.value,
            error_message="temporary network timeout",
            retry_count=3,
        )
        sess.add(task)
        sess.commit()
        sess.refresh(task)
        task_id = str(task.id)
    finally:
        sess.close()

    # Move to dead-letter via maintenance task
    res1 = move_failed_tasks_to_dead_letter.delay()
    out1 = res1.get(timeout=60)
    assert out1["moved_count"] >= 1

    # Retry the dead-lettered task
    res2 = retry_dead_letter_task.delay(task_id)
    out2 = res2.get(timeout=60)
    assert out2["success"] is True

