from __future__ import annotations

from datetime import datetime, timezone

import pytest
from starlette.requests import Request

from app.models.user import User
from app.models.task import Task
from app.api.v1.endpoints.admin_analysis import get_analysis_summary, get_analysis_detail


def _dummy_bcrypt() -> str:
    # 符合正则 ^\$2[aby]\$[0-9]{2}\$[./A-Za-z0-9]{53}$
    return "$2b$12$" + ("A" * 53)


@pytest.mark.asyncio
async def test_admin_analysis_summary_contract(sync_db_session: "object") -> None:
    # 插入一个用户与任务
    u = User(email="test@example.com", password_hash=_dummy_bcrypt())
    sync_db_session.add(u)
    sync_db_session.flush()
    t = Task(user_id=u.id, product_description="demo")
    sync_db_session.add(t)
    sync_db_session.commit()

    scope = {"type": "http", "method": "GET", "path": "/api/v1/admin/analysis/summary", "headers": []}
    request = Request(scope)
    request.state.permissions = ["admin"]
    request.state.request_id = "trace-test"

    resp = await get_analysis_summary(request, q=None, sort="ascore_desc", offset=0, limit=10)
    assert getattr(resp, "code", None) == 0
    assert hasattr(resp, "data") and hasattr(resp.data, "items") and hasattr(resp.data, "total")
    assert resp.data.total >= 1


@pytest.mark.asyncio
async def test_admin_analysis_detail_contract(sync_db_session: "object") -> None:
    u = User(email="user2@example.com", password_hash=_dummy_bcrypt())
    sync_db_session.add(u)
    sync_db_session.flush()
    t = Task(user_id=u.id, product_description="demo2")
    sync_db_session.add(t)
    sync_db_session.commit()

    scope = {"type": "http", "method": "GET", "path": f"/api/v1/admin/analysis/{t.id}", "headers": []}
    request = Request(scope)
    request.state.permissions = ["admin"]
    request.state.request_id = "trace-test-2"

    resp = await get_analysis_detail(request, task_id=str(t.id))
    assert resp.task_id == str(t.id)
    assert 0 <= resp.a_score <= 100
    assert hasattr(resp, "must")
