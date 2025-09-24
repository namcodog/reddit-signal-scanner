"""Admin statistics aggregation service."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List

import math
import statistics
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.feedback_event import FeedbackEvent
from ...models.task import Task, TaskStatus
from ...schemas.admin.stats import (
    BehaviorReasonCount,
    BehaviorSummary,
    ErrorCategorySummary,
    ErrorLogEntry,
    ErrorLogSummary,
    PerformanceMetrics,
    PerformanceSample,
    UsageSeriesPoint,
    UsageStats,
)


async def build_behavior_summary(session: AsyncSession, days: int = 30) -> BehaviorSummary:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    type_stmt = (
        select(FeedbackEvent.event_type, func.count())
        .where(FeedbackEvent.created_at >= since)
        .group_by(FeedbackEvent.event_type)
    )
    rows = await session.execute(type_stmt)
    by_type: Dict[str, int] = {str(event_type): int(count) for event_type, count in rows.all()}
    total = sum(by_type.values())

    reason_counter: Counter[str] = Counter()
    payload_stmt = select(FeedbackEvent.payload).where(FeedbackEvent.created_at >= since)
    payload_rows = await session.execute(payload_stmt)
    for (payload,) in payload_rows.fetchall():
        reason = payload.get('reason') if isinstance(payload, dict) else None
        if isinstance(reason, str) and reason:
            reason_counter[reason] += 1
    top_reasons = [BehaviorReasonCount(reason=reason, count=count) for reason, count in reason_counter.most_common(5)]

    return BehaviorSummary(total_events=total, by_type=by_type, top_reasons=top_reasons)


async def build_usage_stats(session: AsyncSession, days: int = 7) -> UsageStats:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    day_stmt = (
        select(
            func.date(Task.created_at),
            func.count(),
            func.count(func.distinct(Task.user_id)),
        )
        .where(Task.created_at >= since)
        .group_by(func.date(Task.created_at))
        .order_by(func.date(Task.created_at))
    )
    rows = await session.execute(day_stmt)
    series = [
        UsageSeriesPoint(
            bucket=row_date,
            tasks_created=int(task_count),
            active_users=int(user_count),
        )
        for row_date, task_count, user_count in rows.all()
    ]

    weekly_tasks_stmt = select(func.count()).where(Task.created_at >= since)
    weekly_tasks = int((await session.execute(weekly_tasks_stmt)).scalar() or 0)

    weekly_users_stmt = select(func.count(func.distinct(Task.user_id))).where(Task.created_at >= since)
    weekly_active_users = int((await session.execute(weekly_users_stmt)).scalar() or 0)

    return UsageStats(daily=series, weekly_tasks=weekly_tasks, weekly_active_users=weekly_active_users)


async def build_error_summary(session: AsyncSession, limit: int = 20) -> ErrorLogSummary:
    category_stmt = (
        select(Task.failure_category, func.count())
        .where(Task.status == TaskStatus.FAILED)
        .group_by(Task.failure_category)
    )
    rows = await session.execute(category_stmt)
    categories = [
        ErrorCategorySummary(category=str(category or 'unknown'), count=int(count))
        for category, count in rows.all()
    ]
    total_failed = sum(item.count for item in categories)

    recent_stmt = (
        select(Task.id, Task.error_message, Task.failure_category, Task.updated_at)
        .where(Task.status == TaskStatus.FAILED)
        .order_by(Task.updated_at.desc())
        .limit(limit)
    )
    recent_rows = await session.execute(recent_stmt)
    recent = [
        ErrorLogEntry(
            task_id=str(task_id),
            error_message=error_message,
            failure_category=failure_category,
            happened_at=updated_at,
        )
        for task_id, error_message, failure_category, updated_at in recent_rows.all()
    ]

    return ErrorLogSummary(total_failed=total_failed, categories=categories, recent=recent)


async def build_performance_metrics(session: AsyncSession, hours: int = 24) -> PerformanceMetrics:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    stmt = (
        select(Task.started_at, Task.completed_at)
        .where(
            Task.status == TaskStatus.COMPLETED,
            Task.started_at.is_not(None),
            Task.completed_at.is_not(None),
            Task.completed_at >= since,
        )
        .order_by(Task.completed_at)
    )
    rows = await session.execute(stmt)
    buckets: Dict[datetime, List[float]] = defaultdict(list)
    for started_at, completed_at in rows.all():
        if not started_at or not completed_at:
            continue
        duration = float((completed_at - started_at).total_seconds())
        bucket = completed_at.replace(minute=0, second=0, microsecond=0)
        buckets[bucket].append(duration)

    samples: List[PerformanceSample] = []
    for timestamp, durations in sorted(buckets.items()):
        if not durations:
            continue
        avg = float(statistics.fmean(durations)) if len(durations) > 1 else durations[0]
        p95 = _percentile(sorted(durations), 0.95)
        samples.append(
            PerformanceSample(
                timestamp=timestamp,
                avg_duration=avg,
                p95_duration=p95,
            )
        )

    return PerformanceMetrics(samples=samples)


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
