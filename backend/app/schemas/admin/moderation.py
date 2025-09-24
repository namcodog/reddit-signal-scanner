"""Schemas for admin task moderation actions."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ...models.task import TaskStatus

ModerationAction = Literal['reject', 'delete']


class AdminTaskModerationRequest(BaseModel):
    action: ModerationAction = Field(..., description="审核动作：reject/delete")
    reason: str | None = Field(default=None, max_length=500)


class AdminTaskModerationResult(BaseModel):
    task_id: str
    new_status: TaskStatus
    event_id: str | None = None


class AdminTaskModerationResponse(BaseModel):
    code: int = 0
    data: AdminTaskModerationResult
    trace_id: str | None = None
