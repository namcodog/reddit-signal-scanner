"""性能基准：关键轻量操作微基准

说明：
- 使用内存 Fake 运行小规模循环，记录吞吐
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any
import importlib

import pytest

from tests.performance import baseline_recorder as perf

if TYPE_CHECKING:
    pass  # Type imports for static analysis


class FastRedis:
    def __init__(self) -> None:
        self.store: dict[str, Any] = {}

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        self.store[key] = (value, ttl)
        return True

    async def exists(self, key: str) -> bool:  # noqa: D401
        return key in self.store


@pytest.mark.asyncio
@pytest.mark.performance
async def test_blacklist_revoke_micro_benchmark(monkeypatch: Any) -> None:
    mod = importlib.import_module("app.services.token_blacklist_service")
    get_token_blacklist_service = getattr(mod, "get_token_blacklist_service")

    async def _fake_get_redis_client() -> FastRedis:
        return FastRedis()

    monkeypatch.setattr(
        "app.services.token_blacklist_service.get_redis_client",
        _fake_get_redis_client,
    )

    svc = get_token_blacklist_service()

    N = 200
    case_id = "perf:bench:blacklist_revoke:N200"
    start = time.perf_counter()

    async def _one(i: int) -> None:
        ok = await svc.revoke_token(jti=f"j{i}", token_type="access", expires_delta=60)
        assert ok is True

    await asyncio.gather(*[asyncio.create_task(_one(i)) for i in range(N)])
    elapsed = time.perf_counter() - start
    throughput = N / elapsed if elapsed > 0 else float("inf")

    perf.record(
        case_id,
        duration_ms=round(elapsed * 1000.0, 3),
        ops=N,
        throughput_ops=round(throughput, 2),
    )
