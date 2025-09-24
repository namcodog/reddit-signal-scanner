from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task, TaskStatus
from app.models.user import User
from app.services.admin.moderation_service import (
    TaskNotFoundError,
    apply_moderation_action,
)
from backend.tests.conftest import DatabaseTestFactory


@pytest.mark.asyncio
async def test_apply_moderation_reject(db_session: AsyncSession) -> None:
    user = User(**DatabaseTestFactory.minimal_valid_user(email='moderator@example.com'))
    db_session.add(user)
    await db_session.flush()

    task = Task(
        **DatabaseTestFactory.minimal_valid_task(
            user_id=user.id,
            status=TaskStatus.PROCESSING,
            started_at=datetime.now(timezone.utc) - timedelta(minutes=5)
        )
    )
    db_session.add(task)
    await db_session.commit()

    updated_task, event_id = await apply_moderation_action(
        db_session,
        task.id,
        'reject',
        reason='内容不合规',
        user_id=str(user.id),
        request_id='trace-mod-1',
    )
    await db_session.commit()

    assert updated_task.status == TaskStatus.FAILED
    assert event_id is not None


@pytest.mark.asyncio
async def test_apply_moderation_delete_marks_dead_letter(db_session: AsyncSession) -> None:
    user = User(**DatabaseTestFactory.minimal_valid_user(email='deleter@example.com'))
    db_session.add(user)
    await db_session.flush()

    task = Task(
        **DatabaseTestFactory.minimal_valid_task(
            user_id=user.id,
            status=TaskStatus.PENDING,
        )
    )
    db_session.add(task)
    await db_session.commit()

    updated_task, _ = await apply_moderation_action(
        db_session,
        task.id,
        'delete',
        reason=None,
        user_id=str(user.id),
        request_id=None,
    )
    await db_session.commit()

    assert updated_task.status == TaskStatus.DEAD_LETTER
    assert updated_task.dead_letter_at is not None


@pytest.mark.asyncio
async def test_apply_moderation_missing_task(db_session: AsyncSession) -> None:
    with pytest.raises(TaskNotFoundError):
        await apply_moderation_action(
            db_session,
            uuid4(),
            'reject',
            reason=None,
            user_id=None,
            request_id=None,
        )
