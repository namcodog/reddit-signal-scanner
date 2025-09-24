from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task, TaskStatus
from app.models.user import User
from app.services.admin.dashboard_service import build_dashboard_overview, build_system_metrics
from backend.tests.conftest import DatabaseTestFactory


@pytest.mark.asyncio
async def test_build_dashboard_overview(db_session: AsyncSession) -> None:
    user_a = User(**DatabaseTestFactory.minimal_valid_user(email="ops@example.com"))
    user_b = User(**DatabaseTestFactory.minimal_valid_user(email="support@example.com"))
    db_session.add_all([user_a, user_b])
    await db_session.flush()

    now = datetime.now(timezone.utc)
    task_a1 = Task(
        **DatabaseTestFactory.minimal_valid_task(
            user_id=user_a.id,
            status=TaskStatus.COMPLETED,
            started_at=now - timedelta(minutes=15),
            completed_at=now - timedelta(minutes=5),
        )
    )
    task_a2 = Task(
        **DatabaseTestFactory.minimal_valid_task(
            user_id=user_a.id,
            status=TaskStatus.PROCESSING,
            started_at=now - timedelta(minutes=3),
        )
    )
    task_b1 = Task(
        **DatabaseTestFactory.minimal_valid_task(
            user_id=user_b.id,
            status=TaskStatus.FAILED,
        )
    )

    db_session.add_all([task_a1, task_a2, task_b1])
    await db_session.commit()

    overview = await build_dashboard_overview(db_session, user_limit=10, task_limit=10)

    assert overview.users
    emails = {user.email for user in overview.users}
    assert "ops@example.com" in emails
    assert "support@example.com" in emails

    # 最近任务包含我们插入的任务
    task_ids = {task.task_id for task in overview.recent_tasks}
    assert str(task_a1.id) in task_ids
    assert str(task_b1.id) in task_ids

    # 状态计数统计准确
    counts = overview.status_counts
    assert counts.completed >= 1
    assert counts.processing >= 1
    assert counts.failed >= 1


@pytest.mark.asyncio
async def test_build_system_metrics(db_session: AsyncSession) -> None:
    user = User(**DatabaseTestFactory.minimal_valid_user(email='metrics@example.com'))
    db_session.add(user)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    completed_task = Task(
        **DatabaseTestFactory.minimal_valid_task(
            user_id=user.id,
            status=TaskStatus.COMPLETED,
            started_at=now - timedelta(minutes=10),
            completed_at=now - timedelta(minutes=5),
        )
    )
    pending_task = Task(
        **DatabaseTestFactory.minimal_valid_task(
            user_id=user.id,
            status=TaskStatus.PENDING,
        )
    )
    processing_task = Task(
        **DatabaseTestFactory.minimal_valid_task(
            user_id=user.id,
            status=TaskStatus.PROCESSING,
            started_at=now - timedelta(minutes=2),
        )
    )
    failed_task = Task(
        **DatabaseTestFactory.minimal_valid_task(
            user_id=user.id,
            status=TaskStatus.FAILED,
        )
    )

    db_session.add_all([completed_task, pending_task, processing_task, failed_task])
    await db_session.commit()

    metrics = await build_system_metrics(db_session)

    assert metrics.queue.pending >= 1
    assert metrics.queue.processing >= 1
    assert metrics.queue.completed_last_hour >= 1
    assert metrics.durations.average >= 0.0
