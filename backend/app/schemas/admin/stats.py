"""Schemas for admin analytics statistics endpoints."""

from __future__ import annotations

from datetime import datetime, date
from typing import Dict, List

from pydantic import BaseModel, Field


class BehaviorReasonCount(BaseModel):
    reason: str
    count: int


class BehaviorSummary(BaseModel):
    total_events: int
    by_type: Dict[str, int]
    top_reasons: List[BehaviorReasonCount]


class BehaviorSummaryResponse(BaseModel):
    code: int = 0
    data: BehaviorSummary
    trace_id: str | None = None


class UsageSeriesPoint(BaseModel):
    bucket: date
    tasks_created: int
    active_users: int


class UsageStats(BaseModel):
    daily: List[UsageSeriesPoint]
    weekly_tasks: int
    weekly_active_users: int


class UsageStatsResponse(BaseModel):
    code: int = 0
    data: UsageStats
    trace_id: str | None = None


class ErrorCategorySummary(BaseModel):
    category: str
    count: int


class ErrorLogEntry(BaseModel):
    task_id: str
    error_message: str | None = None
    failure_category: str | None = None
    happened_at: datetime


class ErrorLogSummary(BaseModel):
    total_failed: int
    categories: List[ErrorCategorySummary]
    recent: List[ErrorLogEntry]


class ErrorLogResponse(BaseModel):
    code: int = 0
    data: ErrorLogSummary
    trace_id: str | None = None


class PerformanceSample(BaseModel):
    timestamp: datetime
    avg_duration: float
    p95_duration: float


class PerformanceMetrics(BaseModel):
    samples: List[PerformanceSample]


class PerformanceMetricsResponse(BaseModel):
    code: int = 0
    data: PerformanceMetrics
    trace_id: str | None = None
