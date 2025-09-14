"""业务场景：分析任务提交并发基线

说明：
- 使用 Fake TaskManager + Fake DB，避免外部依赖
- 10/50/100 并发下提交 /api/v1/analyze/，记录近似吞吐
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncIterator, List

import pytest
from httpx import ASGITransport, AsyncClient

from tests.performance import baseline_recorder as perf


@pytest.fixture
async def api_client() -> AsyncIterator[AsyncClient]:
    from backend.app.main import app
    from backend.app.middleware.jwt_middleware import JWTMiddleware

    JWTMiddleware.SKIP_AUTH_PATHS.update({
        "/api/v1/analyze/",
    })

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client


def _patch_analyze_dependencies(monkeypatch: Any) -> None:
    mod = __import__(
        "backend.app.api.v1.endpoints.analyze",
        fromlist=["dummy"],
    )

    class FakeResp:
        def __init__(self, i: int) -> None:
            self.task_id = f"t-{i}"
            self.submitted_at = datetime.now(timezone.utc)
            self.estimated_start_time = None
            self.queue_name = "default"

    class FakeManager:
        async def create_task(self, *_args: Any, **_kwargs: Any) -> FakeResp:
            # 快速返回，模拟入队成功
            return FakeResp(_kwargs.get("i", 0))

    async def fake_get_db() -> AsyncIterator[object]:
        yield object()

    monkeypatch.setattr(mod, "get_task_manager", lambda: FakeManager())
    monkeypatch.setattr(mod, "get_db", fake_get_db)


@pytest.mark.asyncio
@pytest.mark.performance
async def test_analyze_submit_concurrency(api_client: AsyncClient, monkeypatch: Any) -> None:
    _patch_analyze_dependencies(monkeypatch)

    async def _one(i: int) -> int:
        payload = {"product_description": f"desc {i} about developer tools"}
        r = await api_client.post("/api/v1/analyze/", json=payload)
        assert r.status_code == 200
        return r.status_code

    for level in (10, 50, 100):
        case_id = f"api:analyze:submit_concurrency:{level}"
        async with perf.async_time_block(case_id):
            res: List[int] = await asyncio.gather(
                *[asyncio.create_task(_one(i)) for i in range(level)]
            )
        perf.record(case_id, ok=sum(1 for s in res if s == 200), concurrency=level)
