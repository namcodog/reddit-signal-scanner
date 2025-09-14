"""API 性能：端点响应时间基线

覆盖：
- POST /api/v1/analyze/ < 200ms （使用快速依赖替换）
- GET  /health < 50ms （健康检查）
"""

from __future__ import annotations

import time
import types
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from tests.performance import baseline_recorder as perf


@pytest.fixture
async def api_client() -> AsyncIterator[AsyncClient]:
    # 与集成测试保持一致的ASGI传输
    from backend.app.main import app
    from backend.app.middleware.jwt_middleware import JWTMiddleware

    # 放宽测试路径的认证要求
    JWTMiddleware.SKIP_AUTH_PATHS.update({
        "/api/v1/analyze/",
        "/api/v1/monitoring/tasks/stats",
        "/health",
    })

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client


@pytest.mark.asyncio
@pytest.mark.performance
async def test_analyze_endpoint_latency(api_client: AsyncClient, monkeypatch: Any) -> None:
    # 依赖替换：TaskManager 和 get_db
    mod = __import__(
        "backend.app.api.v1.endpoints.analyze",
        fromlist=["dummy"],
    )

    class FakeResp:
        def __init__(self) -> None:
            self.task_id = "t-123"
            self.submitted_at = datetime.now(timezone.utc)
            self.estimated_start_time = None
            self.queue_name = "default"

    class FakeManager:
        async def create_task(self, *_args: Any, **_kwargs: Any) -> FakeResp:
            return FakeResp()

    async def fake_get_db() -> AsyncIterator[object]:
        # 简化：不访问真实数据库
        yield object()

    # 替换模块内依赖符号
    monkeypatch.setattr(mod, "get_task_manager", lambda: FakeManager())
    monkeypatch.setattr(mod, "get_db", fake_get_db)

    payload = {"product_description": "awesome product for developers"}

    case_id = "api:latency:analyze"
    start = time.perf_counter()
    resp = await api_client.post("/api/v1/analyze/", json=payload)
    elapsed = (time.perf_counter() - start) * 1000.0

    assert resp.status_code == 200
    assert elapsed < 200.0
    perf.record(case_id, duration_ms=round(elapsed, 3))


@pytest.mark.asyncio
@pytest.mark.performance
async def test_health_latency(api_client: AsyncClient) -> None:
    case_id = "api:latency:health"
    start = time.perf_counter()
    resp = await api_client.get("/health")
    elapsed = (time.perf_counter() - start) * 1000.0
    assert resp.status_code == 200
    assert elapsed < 50.0
    perf.record(case_id, duration_ms=round(elapsed, 3))
