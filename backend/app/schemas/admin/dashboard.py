"""Schemas for admin dashboard overview and metrics."""

from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field

from ...models.task import TaskStatus


class AdminUserSummary(BaseModel):
    user_id: str = Field(..., description="用户ID")
    email: str = Field(..., description="用户邮箱")
    membership_level: str = Field(..., description="会员等级")
    created_at: datetime = Field(..., description="创建时间")
    total_tasks: int = Field(..., ge=0)
    active_tasks: int = Field(..., ge=0)
    completed_tasks: int = Field(..., ge=0)
    failed_tasks: int = Field(..., ge=0)
    last_activity_at: datetime | None = Field(default=None, description="最近活动时间")


class AdminRecentTask(BaseModel):
    task_id: str
    user_email: str
    status: TaskStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None


class AdminTaskStatusCounts(BaseModel):
    pending: int = 0
    processing: int = 0
    completed: int = 0
    failed: int = 0
    dead_letter: int = 0


class AdminDashboardOverviewData(BaseModel):
    users: List[AdminUserSummary]
    recent_tasks: List[AdminRecentTask]
    status_counts: AdminTaskStatusCounts


class AdminDashboardOverviewResponse(BaseModel):
    code: int = Field(default=0)
    data: AdminDashboardOverviewData
    trace_id: str | None = None


class AdminDurationStats(BaseModel):
    average: float = 0.0
    p50: float = 0.0
    p95: float = 0.0


class AdminQueueStats(BaseModel):
    pending: int = 0
    processing: int = 0
    completed_last_hour: int = 0
    failed_last_hour: int = 0


class AdminSystemMetricsData(BaseModel):
    generated_at: datetime
    queue: AdminQueueStats
    durations: AdminDurationStats


class AdminSystemMetricsResponse(BaseModel):
    code: int = Field(default=0)
    data: AdminSystemMetricsData
    trace_id: str | None = None
