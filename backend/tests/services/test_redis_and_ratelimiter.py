import asyncio
import time
import pytest

from app.core.redis_client import redis_set, redis_get
from app.core.redis_client import get_redis_client
from app.core.rate_limiter import (
    create_rate_limiter,
    RateLimitExceeded,
    CircuitBreakerOpen,
)


@pytest.mark.asyncio
async def test_redis_kv_basic_roundtrip():
    # 确保 Redis 可用并进行一次KV往返
    key = "rss:test:kv:roundtrip"
    value = {"hello": "world", "ts": int(time.time())}

    ok = await redis_set(key, value, ttl=60)
    assert ok is True

    got = await redis_get(key)
    assert isinstance(got, dict)
    assert got.get("hello") == "world"


@pytest.mark.asyncio
async def test_rate_limiter_acquire_and_reset():
    limiter = await create_rate_limiter()
    try:
        # 清理历史状态，保证独立性
        ok = await limiter.reset_limits()
        assert ok is True

        # 应能成功获取一次许可
        allowed = await limiter.acquire_permit(timeout=1.0)
        assert allowed is True

        # 记录成功应不会抛异常
        await limiter.record_success()
    finally:
        # 退出上下文（不关闭全局连接）
        await limiter.__aexit__(None, None, None)


@pytest.mark.asyncio
async def test_rate_limiter_circuit_breaker_opens_on_failures():
    limiter = await create_rate_limiter()
    try:
        await limiter.reset_limits()

        # 连续记录失败，触发熔断
        for _ in range(limiter.config.circuit_breaker_threshold):
            await limiter.record_failure()

        with pytest.raises(CircuitBreakerOpen):
            await limiter.acquire_permit(timeout=0.5)
    finally:
        await limiter.__aexit__(None, None, None)
