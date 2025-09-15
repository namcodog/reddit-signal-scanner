"""恢复时间测量：Redis客户端重连近似恢复时长

说明：
- 模拟 Redis 客户端多次不健康，connect() 带固定延迟
- 记录从首次调用到健康为 True 的时间
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from tests.performance import baseline_recorder as perf


@pytest.mark.asyncio
@pytest.mark.performance
async def test_redis_recovery_time(monkeypatch: Any) -> None:
    from backend.app.core import redis_client as rc

    class FakeClient:
        def __init__(self) -> None:
            self.connected = False
            self.ping_called = 0

        async def connect(self) -> None:
            # 模拟连接耗时 30ms
            await asyncio.sleep(0.03)
            self.connected = True

        async def is_healthy(self) -> bool:
            # 前 3 次不健康，第 4 次健康
            self.ping_called += 1
            return self.ping_called >= 4

    fake = FakeClient()
    monkeypatch.setattr(rc, "_redis_client", fake)

    case_id = "infra:redis:recovery_time"
    t0 = time.perf_counter()
    client = await rc.get_redis_client()
    dt_ms = (time.perf_counter() - t0) * 1000.0

    assert client is fake
    assert fake.connected is True
    perf.record(case_id, recovery_time_ms=round(dt_ms, 2), attempts=fake.ping_called)

