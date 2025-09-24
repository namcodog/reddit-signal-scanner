from __future__ import annotations

from starlette.requests import Request
import pytest

from app.api.v1.endpoints.admin_analysis import get_analysis_detail


@pytest.mark.asyncio
async def test_admin_analysis_detail_invalid_uuid_returns_400() -> None:
    scope = {"type": "http", "method": "GET", "path": "/api/v1/admin/analysis/invalid", "headers": []}
    req = Request(scope)
    req.state.permissions = ["admin"]
    resp = await get_analysis_detail(req, task_id="not-a-uuid")
    assert hasattr(resp, "status_code") and resp.status_code == 400


def test_admin_analysis_detail_missing_returns_404(monkeypatch: "object", client: "object") -> None:
    # 跳过权限检查
    import app.middleware.jwt_middleware as jm
    import app.api.v1.endpoints.admin_analysis as mod

    monkeypatch.setattr(jm, "has_permission_in_request", lambda *a, **k: True, raising=False)
    monkeypatch.setattr(mod, "has_permission_in_request", lambda *a, **k: True, raising=False)

    resp = client.get("/api/v1/admin/analysis/00000000-0000-0000-0000-000000000001")
    assert resp.status_code == 404

