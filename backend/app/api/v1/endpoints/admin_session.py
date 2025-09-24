"""Admin session endpoint for front-end guards."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ....api.deps.admin_guard import ensure_admin_read_access
from ....middleware.jwt_middleware import get_current_user_from_request
from ....schemas.admin.session import AdminSessionData, AdminSessionResponse

router = APIRouter(prefix="/admin", tags=["Admin-会话"])


@router.get("/session", response_model=AdminSessionResponse)
async def get_admin_session(request: Request) -> AdminSessionResponse:
    guard_ctx = ensure_admin_read_access(request)
    user = get_current_user_from_request(request)
    if user is None:
        raise HTTPException(status_code=401, detail="unauthenticated")

    payload = AdminSessionData(
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        email=user.email,
        roles=guard_ctx.roles,
        permissions=guard_ctx.permissions,
    )
    trace_id = getattr(request.state, "request_id", None)
    return AdminSessionResponse(data=payload, trace_id=trace_id)
