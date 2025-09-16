"""容量规划：并发阶梯采样

说明：
- 以不同并发阶梯调用轻量路径，记录吞吐趋势（近似）
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, Optional
import importlib

import pytest

from tests.performance import baseline_recorder as perf

if TYPE_CHECKING:
    pass  # Type imports for static analysis


class FastRedis:
    def __init__(self) -> None:
        self.store: Dict[str, Any] = {}

    async def get(self, key: str) -> Optional[str]:  # noqa: D401
        v = self.store.get(key)
        return None if v is None else str(v)

    async def set(
        self, key: str, value: Any, ttl: Optional[int] = None
    ) -> bool:  # noqa: D401
        self.store[key] = value
        return True

    async def incr(self, key: str, amount: int = 1) -> int:  # noqa: D401
        current = int(self.store.get(key, 0)) + amount
        self.store[key] = current
        return current

    async def ttl(self, key: str) -> int:  # noqa: D401
        return 60


@pytest.mark.asyncio
@pytest.mark.performance
async def test_capacity_staircase(monkeypatch: Any) -> None:
    mod = importlib.import_module("app.services.login_security")
    login_security = getattr(mod, "login_security")

    fast = FastRedis()

    async def _fake_get_redis_client() -> FastRedis:
        return fast

    monkeypatch.setattr(
        "app.services.login_security.get_redis_client",
        _fake_get_redis_client,
    )

    levels = [1, 5, 10, 20]
    results: Dict[int, float] = {}

    async def _one(i: int, email: str, ip: str) -> None:
        allowed, retry_after = await login_security.check_rate_limit(email, ip)
        assert allowed is True
        assert retry_after is None

    for c in levels:
        start = time.perf_counter()
        await asyncio.gather(
            *[
                asyncio.create_task(_one(i, f"cap{i}@t.com", f"172.16.0.{i%100}"))
                for i in range(c * 10)
            ]
        )
        elapsed = time.perf_counter() - start
        ops = c * 10
        results[c] = ops / elapsed if elapsed > 0 else float("inf")

    case_id = "perf:capacity:staircase"
    perf.record(
        case_id,
        levels=levels,
        throughput={str(k): round(v, 2) for k, v in results.items()},
    )
