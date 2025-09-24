from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feedback_event import FeedbackEvent
from app.models.task import Task, TaskStatus
from app.models.user import User
from app.services.admin.stats_service import (
    build_behavior_summary,
    build_error_summary,
    build_performance_metrics,
    build_usage_stats,
)
from backend.tests.conftest import DatabaseTestFactory


@pytest.mark.asyncio
async def test_build_behavior_summary(db_session: AsyncSession) -> None:
    user = User(**DatabaseTestFactory.minimal_valid_user(email='behavior@example.com'))
    db_session.add(user)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    events = [
        FeedbackEvent(
            source='admin',
            event_type='analysis_rating',
            user_id=str(user.id),
            task_id='t1',
            payload={'reason': 'quality_low'},
            created_at=now,
        ),
        FeedbackEvent(
            source='user',
            event_type='analysis_rating',
            task_id='t2',
            payload={'reason': 'quality_low'},
            created_at=now,
        ),
        FeedbackEvent(
            source='admin',
            event_type='metric',
            task_id='t3',
            payload={'metric_name': 'latency', 'metric_value': 1.0},
            created_at=now,
        ),
    ]
    db_session.add_all(events)
    await db_session.commit()

    summary = await build_behavior_summary(db_session, days=1)
    assert summary.total_events == 3
    assert summary.by_type['analysis_rating'] == 2
    assert summary.top_reasons and summary.top_reasons[0].reason == 'quality_low'


@pytest.mark.asyncio
async def test_build_usage_stats(db_session: AsyncSession) -> None:
    user = User(**DatabaseTestFactory.minimal_valid_user(email='usage@example.com'))
    db_session.add(user)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    for offset in range(3):
        task = Task(
            **DatabaseTestFactory.minimal_valid_task(
                user_id=user.id,
                created_at=now - timedelta(days=offset),
            )
        )
        db_session.add(task)
    await db_session.commit()

    usage = await build_usage_stats(db_session, days=7)
    assert usage.daily
    assert usage.weekly_tasks >= 3
    assert usage.weekly_active_users >= 1


@pytest.mark.asyncio
async def test_build_error_summary(db_session: AsyncSession) -> None:
    user = User(**DatabaseTestFactory.minimal_valid_user(email='error@example.com'))
    db_session.add(user)
    await db_session.flush()

    failed = Task(
        **DatabaseTestFactory.minimal_valid_task(
            user_id=user.id,
            status=TaskStatus.FAILED,
            failure_category='network_error',
            error_message='timeout',
            updated_at=datetime.now(timezone.utc),
        )
    )
    db_session.add(failed)
    await db_session.commit()

    summary = await build_error_summary(db_session, limit=5)
    assert summary.total_failed >= 1
    assert summary.categories
    assert summary.recent


@pytest.mark.asyncio
async def test_build_performance_metrics(db_session: AsyncSession) -> None:
    user = User(**DatabaseTestFactory.minimal_valid_user(email='perf@example.com'))
    db_session.add(user)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    task = Task(
        **DatabaseTestFactory.minimal_valid_task(
            user_id=user.id,
            status=TaskStatus.COMPLETED,
            started_at=now - timedelta(minutes=10),
            completed_at=now,
        )
    )
    db_session.add(task)
    await db_session.commit()

    metrics = await build_performance_metrics(db_session, hours=4)
    assert metrics.samples
    assert metrics.samples[0].avg_duration >= 0.0
