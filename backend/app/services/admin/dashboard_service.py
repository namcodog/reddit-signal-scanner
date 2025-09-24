"""Admin dashboard aggregation helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

import math
import statistics
from sqlalchemy import case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.task import Task, TaskStatus
from ...models.user import User
from ...schemas.admin.dashboard import (
    AdminDashboardOverviewData,
    AdminDurationStats,
    AdminQueueStats,
    AdminRecentTask,
    AdminSystemMetricsData,
    AdminTaskStatusCounts,
    AdminUserSummary,
)


async def build_dashboard_overview(
    session: AsyncSession,
    user_limit: int = 20,
    task_limit: int = 20,
) -> AdminDashboardOverviewData:
    users = await _load_user_summaries(session, user_limit)
    recent_tasks = await _load_recent_tasks(session, task_limit)
    status_counts = await _load_status_counts(session)
    return AdminDashboardOverviewData(
        users=users,
        recent_tasks=recent_tasks,
        status_counts=status_counts,
    )


async def _load_user_summaries(session: AsyncSession, limit: int) -> List[AdminUserSummary]:
    active_case = case((Task.status == TaskStatus.PROCESSING, 1), else_=0)
    completed_case = case((Task.status == TaskStatus.COMPLETED, 1), else_=0)
    failed_case = case((Task.status == TaskStatus.FAILED, 1), else_=0)

    stmt = (
        select(
            User.id,
            User.email,
            User.membership_level,
            User.created_at,
            func.count(Task.id),
            func.coalesce(func.sum(active_case), 0),
            func.coalesce(func.sum(completed_case), 0),
            func.coalesce(func.sum(failed_case), 0),
            func.max(Task.updated_at),
        )
        .outerjoin(Task, Task.user_id == User.id)
        .group_by(User.id)
        .order_by(desc(func.max(Task.updated_at)), desc(User.created_at))
        .limit(limit)
    )

    rows = await session.execute(stmt)
    summaries: List[AdminUserSummary] = []
    for (
        user_id,
        email,
        membership_level,
        created_at,
        total_tasks,
        active_tasks,
        completed_tasks,
        failed_tasks,
        last_activity,
    ) in rows.all():
        summaries.append(
            AdminUserSummary(
                user_id=str(user_id),
                email=str(email),
                membership_level=str(membership_level),
                created_at=created_at,
                total_tasks=int(total_tasks or 0),
                active_tasks=int(active_tasks or 0),
                completed_tasks=int(completed_tasks or 0),
                failed_tasks=int(failed_tasks or 0),
                last_activity_at=last_activity,
            )
        )
    return summaries


async def _load_recent_tasks(session: AsyncSession, limit: int) -> List[AdminRecentTask]:
    stmt = (
        select(
            Task.id,
            User.email,
            Task.status,
            Task.created_at,
            Task.started_at,
            Task.completed_at,
        )
        .join(User, Task.user_id == User.id)
        .order_by(desc(Task.created_at))
        .limit(limit)
    )

    rows = await session.execute(stmt)
    tasks: List[AdminRecentTask] = []
    for task_id, email, status, created_at, started_at, completed_at in rows.all():
        duration: float | None = None
        if started_at and completed_at:
            duration = float((completed_at - started_at).total_seconds())
        status_enum = status if isinstance(status, TaskStatus) else TaskStatus(str(status))
        tasks.append(
            AdminRecentTask(
                task_id=str(task_id),
                user_email=str(email),
                status=status_enum,
                created_at=created_at,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration,
            )
        )
    return tasks


async def _load_status_counts(session: AsyncSession) -> AdminTaskStatusCounts:
    stmt = select(Task.status, func.count()).group_by(Task.status)
    rows = await session.execute(stmt)
    counts = AdminTaskStatusCounts()
    for status_value, count in rows.all():
        status = status_value if isinstance(status_value, TaskStatus) else TaskStatus(str(status_value))
        if status == TaskStatus.PENDING:
            counts.pending = int(count)
        elif status == TaskStatus.PROCESSING:
            counts.processing = int(count)
        elif status == TaskStatus.COMPLETED:
            counts.completed = int(count)
        elif status == TaskStatus.FAILED:
            counts.failed = int(count)
        elif status == TaskStatus.DEAD_LETTER:
            counts.dead_letter = int(count)
    return counts


async def build_system_metrics(session: AsyncSession) -> AdminSystemMetricsData:
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)

    pending_count = await _count_tasks(session, TaskStatus.PENDING)
    processing_count = await _count_tasks(session, TaskStatus.PROCESSING)
    completed_last_hour = await _count_tasks(session, TaskStatus.COMPLETED, since=one_hour_ago)
    failed_last_hour = await _count_tasks(session, TaskStatus.FAILED, since=one_hour_ago)

    durations = await _completed_task_durations(session, limit=200)
    average = float(statistics.fmean(durations)) if durations else 0.0
    p50 = _percentile(durations, 0.5) if durations else 0.0
    p95 = _percentile(durations, 0.95) if durations else 0.0

    queue = AdminQueueStats(
        pending=pending_count,
        processing=processing_count,
        completed_last_hour=completed_last_hour,
        failed_last_hour=failed_last_hour,
    )
    duration_stats = AdminDurationStats(average=average, p50=p50, p95=p95)

    return AdminSystemMetricsData(
        generated_at=now,
        queue=queue,
        durations=duration_stats,
    )


async def _count_tasks(
    session: AsyncSession, status: TaskStatus, since: datetime | None = None
) -> int:
    stmt = select(func.count()).where(Task.status == status)
    if since is not None:
        if status == TaskStatus.COMPLETED:
            stmt = stmt.where(Task.completed_at >= since)
        else:
            stmt = stmt.where(Task.updated_at >= since)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


async def _completed_task_durations(session: AsyncSession, limit: int) -> List[float]:
    stmt = (
        select(Task.started_at, Task.completed_at)
        .where(
            Task.status == TaskStatus.COMPLETED,
            Task.started_at.is_not(None),
            Task.completed_at.is_not(None),
        )
        .order_by(desc(Task.completed_at))
        .limit(limit)
    )
    rows = await session.execute(stmt)
    durations: List[float] = []
    for started_at, completed_at in rows.all():
        if started_at and completed_at:
            durations.append(float((completed_at - started_at).total_seconds()))
    durations.sort()
    return durations


def _percentile(values: List[float], percentile: float) -> float:
    if not values:
        return 0.0
    k = (len(values) - 1) * percentile
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(values[int(k)])
    d0 = values[f] * (c - k)
    d1 = values[c] * (k - f)
    return float(d0 + d1)
