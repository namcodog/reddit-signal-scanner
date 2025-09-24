from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api.v1.endpoints.admin_session import get_admin_session
from app.core.auth import CurrentUser


@pytest.mark.asyncio
async def test_admin_session_requires_permission() -> None:
    scope = {"type": "http", "method": "GET", "path": "/api/v1/admin/session", "headers": []}
    request = Request(scope)
    request.state.permissions = []

    with pytest.raises(HTTPException) as exc:
        await get_admin_session(request)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_session_returns_roles() -> None:
    scope = {"type": "http", "method": "GET", "path": "/api/v1/admin/session", "headers": []}
    request = Request(scope)
    request.state.permissions = ["admin", "admin:write"]
    request.state.request_id = "trace-admin-session"
    request.state.auth = CurrentUser(
        user_id="user-123",
        tenant_id="tenant-xyz",
        email="admin@example.com",
        permissions=["admin", "admin:write"],
        token_type="access",
        auth_time=datetime.utcnow(),
    )

    response = await get_admin_session(request)
    assert response.code == 0
    assert response.trace_id == "trace-admin-session"
    assert response.data.user_id == "user-123"
    assert "operations" in response.data.roles
    assert "technical" in response.data.roles
