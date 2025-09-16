"""业务场景：分析任务提交并发基线"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncIterator, List, cast

import httpx
import pytest

from tests.performance import baseline_recorder as perf


@pytest.fixture
async def api_client() -> AsyncIterator[httpx.AsyncClient]:
    from backend.app.main import app
    from backend.app.middleware.jwt_middleware import JWTMiddleware

    JWTMiddleware.SKIP_AUTH_PATHS.update({"/api/v1/analyze/"})

    transport = httpx.ASGITransport(app=cast(Any, app))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


def _patch_analyze_dependencies(monkeypatch: Any) -> None:
    mod = __import__("backend.app.api.v1.endpoints.analyze", fromlist=["dummy"])

    class FakeResp:
        def __init__(self, i: int) -> None:
            self.task_id = f"t-{i}"
            self.submitted_at = datetime.now(timezone.utc)
            self.estimated_start_time = None
            self.queue_name = "default"

    class FakeManager:
        async def create_task(self, *_args: Any, **kwargs: Any) -> FakeResp:
            return FakeResp(kwargs.get("i", 0))

    async def fake_get_db() -> AsyncIterator[object]:
        yield object()

    monkeypatch.setattr(mod, "get_task_manager", lambda: FakeManager())
    monkeypatch.setattr(mod, "get_db", fake_get_db)


@pytest.mark.asyncio
@pytest.mark.performance
async def test_analyze_submit_concurrency(
    api_client: httpx.AsyncClient, monkeypatch: Any
) -> None:
    _patch_analyze_dependencies(monkeypatch)

    async def _one(i: int) -> int:
        payload = {"product_description": f"desc {i} about developer tools"}
        resp = await api_client.post("/api/v1/analyze/", json=payload)
        assert resp.status_code == 200
        return resp.status_code

    for level in (10, 50, 100):
        case_id = f"api:analyze:submit_concurrency:{level}"
        async with perf.async_time_block(case_id):
            res: List[int] = await asyncio.gather(*[asyncio.create_task(_one(i)) for i in range(level)])
        perf.record(case_id, ok=sum(1 for status in res if status == 200), concurrency=level)
