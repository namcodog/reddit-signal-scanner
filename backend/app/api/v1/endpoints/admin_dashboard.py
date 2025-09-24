"""Admin dashboard endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, Request, HTTPException

from ....api.deps.admin_guard import ensure_admin_read_access, ensure_admin_write_access
from ....core.database import get_session_factory
from ....schemas.admin.dashboard import (
    AdminDashboardOverviewResponse,
    AdminSystemMetricsResponse,
)
from ....schemas.admin.moderation import (
    AdminTaskModerationRequest,
    AdminTaskModerationResponse,
    AdminTaskModerationResult,
)
from ....services.admin.dashboard_service import build_dashboard_overview, build_system_metrics
from ....services.admin.moderation_service import apply_moderation_action, TaskNotFoundError

router = APIRouter(prefix="/admin/dashboard", tags=["Admin-仪表盘"])


@router.get("/overview", response_model=AdminDashboardOverviewResponse)
async def get_admin_dashboard_overview(
    request: Request,
    user_limit: int = Query(default=20, ge=1, le=100),
    task_limit: int = Query(default=20, ge=1, le=100),
) -> AdminDashboardOverviewResponse:
    guard_ctx = ensure_admin_read_access(request)
    trace_id = getattr(request.state, "request_id", None)

    session_factory = get_session_factory()
    async with session_factory() as session:
        data = await build_dashboard_overview(session, user_limit=user_limit, task_limit=task_limit)

    return AdminDashboardOverviewResponse(code=0, data=data, trace_id=trace_id)


@router.get('/metrics', response_model=AdminSystemMetricsResponse)
async def get_admin_system_metrics(request: Request) -> AdminSystemMetricsResponse:
    guard_ctx = ensure_admin_read_access(request)
    trace_id = getattr(request.state, 'request_id', None)

    session_factory = get_session_factory()
    async with session_factory() as session:
        data = await build_system_metrics(session)

    return AdminSystemMetricsResponse(code=0, data=data, trace_id=trace_id)


@router.post('/tasks/{task_id}/moderation', response_model=AdminTaskModerationResponse)
async def moderate_admin_task(
    request: Request, task_id: str, payload: AdminTaskModerationRequest
) -> AdminTaskModerationResponse:
    ensure_admin_write_access(request)
    trace_id = getattr(request.state, 'request_id', None)
    user_id = getattr(request.state, 'user_id', None)

    try:
        task_uuid = UUID(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail='invalid task_id') from exc

    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            task, event_id = await apply_moderation_action(
                session,
                task_uuid,
                payload.action,
                payload.reason,
                user_id,
                trace_id,
            )
            await session.commit()
        except TaskNotFoundError as exc:
            await session.rollback()
            raise HTTPException(status_code=404, detail='task not found') from exc
        except Exception:
            await session.rollback()
            raise

    result = AdminTaskModerationResult(
        task_id=str(task.id),
        new_status=task.status,
        event_id=event_id,
    )
    return AdminTaskModerationResponse(code=0, data=result, trace_id=trace_id)
