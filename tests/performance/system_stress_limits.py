"""系统级压力：阈值与近似崩溃点识别

策略：
- 对 /api/v1/analyze/ 进行并发阶梯 [10, 50, 100, 200, 400]
- 使用 Fake TaskManager 并在 create_task 内注入微小延时，模拟处理开销
- 统计每阶梯批次的平均延迟，记录第一个超过 200ms 的并发级作为近似崩溃点
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional, cast

import httpx
import pytest

from tests.performance import baseline_recorder as perf


@pytest.fixture
async def api_client() -> AsyncIterator[httpx.AsyncClient]:
    from backend.app.main import app
    from backend.app.middleware.jwt_middleware import JWTMiddleware

    JWTMiddleware.SKIP_AUTH_PATHS.update({
        "/api/v1/analyze/",
    })

    transport = httpx.ASGITransport(app=cast(Any, app))
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client


def _patch_with_delay(monkeypatch: Any, sleep_ms: float) -> None:
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
            # 模拟微小处理延迟
            await asyncio.sleep(sleep_ms / 1000.0)
            return FakeResp(kwargs.get("i", 0))

    async def fake_get_db() -> AsyncIterator[object]:
        yield object()

    monkeypatch.setattr(mod, "get_task_manager", lambda: FakeManager())
    monkeypatch.setattr(mod, "get_db", fake_get_db)


@pytest.mark.asyncio
@pytest.mark.performance
async def test_analyze_stress_crash_point(api_client: httpx.AsyncClient, monkeypatch: Any) -> None:
    # 注入 5ms 微延迟
    _patch_with_delay(monkeypatch, sleep_ms=5.0)

    async def _one(i: int) -> float:
        payload = {"product_description": f"dev tools perf {i}"}
        t0 = time.perf_counter()
        r = await api_client.post("/api/v1/analyze/", json=payload)
        dt = (time.perf_counter() - t0) * 1000.0
        assert r.status_code == 200
        return dt

    crash_point: Optional[int] = None
    per_level_avg: Dict[int, float] = {}
    levels = [10, 50, 100, 200, 400]

    for level in levels:
        times: List[float] = []
        async with perf.async_time_block(f"api:analyze:stress_level:{level}"):
            res = await asyncio.gather(
                *[asyncio.create_task(_one(i)) for i in range(level)]
            )
            times.extend(res)
        avg = sum(times) / len(times)
        per_level_avg[level] = round(avg, 3)
        if crash_point is None and avg >= 200.0:
            crash_point = level

    perf.record(
        "api:analyze:stress_crash_point",
        crash_point=crash_point or -1,
        per_level_avg_ms=per_level_avg,
    )
