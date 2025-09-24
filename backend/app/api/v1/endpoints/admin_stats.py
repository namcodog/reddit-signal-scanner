"""Admin statistics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from ....api.deps.admin_guard import ensure_admin_read_access
from ....core.database import get_session_factory
from ....schemas.admin.stats import (
    BehaviorSummaryResponse,
    ErrorLogResponse,
    PerformanceMetricsResponse,
    UsageStatsResponse,
)
from ....services.admin.stats_service import (
    build_behavior_summary,
    build_error_summary,
    build_performance_metrics,
    build_usage_stats,
)

router = APIRouter(prefix="/admin/stats", tags=["Admin-统计"])


@router.get("/behavior", response_model=BehaviorSummaryResponse)
async def get_behavior_summary(request: Request, days: int = Query(default=30, ge=1, le=90)) -> BehaviorSummaryResponse:
    ensure_admin_read_access(request)
    trace_id = getattr(request.state, "request_id", None)
    session_factory = get_session_factory()
    async with session_factory() as session:
        summary = await build_behavior_summary(session, days=days)
    return BehaviorSummaryResponse(code=0, data=summary, trace_id=trace_id)


@router.get("/usage", response_model=UsageStatsResponse)
async def get_usage_stats(request: Request, days: int = Query(default=7, ge=1, le=30)) -> UsageStatsResponse:
    ensure_admin_read_access(request)
    trace_id = getattr(request.state, "request_id", None)
    session_factory = get_session_factory()
    async with session_factory() as session:
        stats = await build_usage_stats(session, days=days)
    return UsageStatsResponse(code=0, data=stats, trace_id=trace_id)


@router.get("/errors", response_model=ErrorLogResponse)
async def get_error_summary(request: Request, limit: int = Query(default=20, ge=1, le=100)) -> ErrorLogResponse:
    ensure_admin_read_access(request)
    trace_id = getattr(request.state, "request_id", None)
    session_factory = get_session_factory()
    async with session_factory() as session:
        summary = await build_error_summary(session, limit=limit)
    return ErrorLogResponse(code=0, data=summary, trace_id=trace_id)


@router.get("/performance", response_model=PerformanceMetricsResponse)
async def get_performance_metrics(request: Request, hours: int = Query(default=24, ge=1, le=168)) -> PerformanceMetricsResponse:
    ensure_admin_read_access(request)
    trace_id = getattr(request.state, "request_id", None)
    session_factory = get_session_factory()
    async with session_factory() as session:
        metrics = await build_performance_metrics(session, hours=hours)
    return PerformanceMetricsResponse(code=0, data=metrics, trace_id=trace_id)
