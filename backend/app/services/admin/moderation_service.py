"""Service helpers for admin task moderation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ...models.task import Task, TaskStatus
from ...schemas.admin.moderation import ModerationAction
from ...schemas.feedback import FeedbackEventRequest, FeedbackEventType, FeedbackSource
from ...services.feedback_event_store import create_event as store_event


class TaskNotFoundError(LookupError):
    """Raised when the requested task does not exist."""


async def apply_moderation_action(
    session: AsyncSession,
    task_id: UUID,
    action: ModerationAction,
    reason: Optional[str],
    user_id: Optional[str],
    request_id: Optional[str],
) -> tuple[Task, str | None]:
    task = await session.get(Task, task_id)
    if task is None:
        raise TaskNotFoundError(str(task_id))

    match action:
        case 'reject':
            task.status = TaskStatus.FAILED
            task.error_message = reason or 'Rejected by admin moderation'
            task.completed_at = None
            task.dead_letter_at = None
        case 'delete':
            task.status = TaskStatus.DEAD_LETTER
            task.dead_letter_at = datetime.now(timezone.utc)
            task.error_message = reason or 'Removed by admin moderation'
        case _:
            raise ValueError(f'Unsupported moderation action: {action}')

    event_request = FeedbackEventRequest(
        source=FeedbackSource.admin,
        event_type=FeedbackEventType.moderation_action,
        task_id=str(task.id),
        user_id=user_id,
        reason=reason,
        context={'action': action},
    )

    event_id: str | None = await store_event(session, event_request, request_id=request_id)
    return task, event_id
