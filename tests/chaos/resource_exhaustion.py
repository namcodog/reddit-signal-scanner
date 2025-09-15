"""Chaos: 资源压力（受控）

说明：不进行真实的资源枯竭，仅做受控的小基准，验证关键路径不会异常退化/崩溃。
"""

import time
from tests.performance import baseline_recorder as perf

from app.core.security import SimpleRateLimiter
from app.services.token_blacklist_service import get_token_blacklist_service


def test_simple_rate_limiter_small_burst_ok():
    limiter = SimpleRateLimiter()
    key = "chaos:burst"
    # 小突发：3 次许可，之后拒绝
    assert limiter.is_allowed(key, max_attempts=3, window_seconds=60) is True
    assert limiter.is_allowed(key, max_attempts=3, window_seconds=60) is True
    assert limiter.is_allowed(key, max_attempts=3, window_seconds=60) is True
    assert limiter.is_allowed(key, max_attempts=3, window_seconds=60) is False


def test_token_blacklist_many_revokes_with_fake_redis(monkeypatch):
    """大量撤销操作（使用内存 Fake），验证路径稳定且快速完成。"""
    class FastRedis:
        def __init__(self) -> None:
            self.store = {}

        async def set(self, key: str, value, ttl=None):  # noqa: ANN001, D401
            self.store[key] = (value, ttl)
            return True

        async def exists(self, key: str):  # noqa: ANN001, D401
            return key in self.store

    async def _fake_get_redis_client():  # type: ignore
        return FastRedis()

    monkeypatch.setattr(
        "app.services.token_blacklist_service.get_redis_client", _fake_get_redis_client
    )

    svc = get_token_blacklist_service()

    import asyncio

    case_id = "chaos:resource:bulk_revoke_100"
    start = time.perf_counter()

    async def _revoke_all():
        for i in range(100):
            jti = f"jti-{i}"
            ok = await svc.revoke_token(jti=jti, token_type="access", expires_delta=60)
            assert ok is True

    asyncio.get_event_loop().run_until_complete(_revoke_all())
    elapsed = time.perf_counter() - start

    # 粗略时间门限：100 次操作应在 1 秒内完成（内存 Fake）
    assert elapsed < 1.0
    perf.record(case_id, duration_ms=round(elapsed * 1000.0, 3), operations=100)
