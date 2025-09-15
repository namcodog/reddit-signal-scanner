"""资源趋势：分析提交循环的内存/CPU趋势（近似）

说明：
- 使用 tracemalloc + process_time 测量内存分配与CPU时间增量
- 通过 ASGI 客户端连续提交 200 次 /api/v1/analyze/
"""

from __future__ import annotations

import time
import tracemalloc
from datetime import datetime, timezone
from typing import Any, AsyncIterator

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


def _patch_fast_analyze(monkeypatch: Any) -> None:
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
        async def create_task(self, *_args: Any, **kwargs: Any) -> FakeResp:
            return FakeResp(kwargs.get("i", 0))

    async def fake_get_db():  # type: ignore[no-untyped-def]
        yield object()

    monkeypatch.setattr(mod, "get_task_manager", lambda: FakeManager())
    monkeypatch.setattr(mod, "get_db", fake_get_db)


@pytest.mark.asyncio
@pytest.mark.performance
async def test_resource_trend_on_analyze_loop(api_client: AsyncClient, monkeypatch: Any) -> None:
    _patch_fast_analyze(monkeypatch)

    tracemalloc.start()
    cpu_start = time.process_time()

    N = 200
    for i in range(N):
        payload = {"product_description": f"perf resource trend {i}"}
        r = await api_client.post("/api/v1/analyze/", json=payload)
        assert r.status_code == 200

    cpu_end = time.process_time()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # 记录 KiB 指标与 CPU 秒
    case_id = "api:analyze:resource_trend:N200"
    perf.record(
        case_id,
        mem_current_kib=round(current / 1024.0, 2),
        mem_peak_kib=round(peak / 1024.0, 2),
        cpu_seconds=round(cpu_end - cpu_start, 3),
        ops=N,
    )
