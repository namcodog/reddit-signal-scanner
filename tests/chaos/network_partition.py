"""Chaos: 网络分区/高延迟/抖动 场景

策略：
- 通过 monkeypatch get_redis_client 注入 FakeRedis，前 N 次抛错/延迟
- 验证服务在 Redis 异常时的“保守处理”与不中断
"""

import asyncio
from typing import Any, Optional

import pytest
from tests.performance import baseline_recorder as perf


class FlakyRedis:
    """模拟网络抖动与高延迟的 Redis 客户端"""

    def __init__(self, fail_times: int = 2, delay_ms: int = 0) -> None:
        self._fail_remain = fail_times
        self._delay = delay_ms / 1000.0
        self._store: dict[str, str] = {}

    async def _maybe_delay(self) -> None:
        if self._delay > 0:
            await asyncio.sleep(self._delay)

    async def _maybe_fail(self) -> None:
        if self._fail_remain > 0:
            self._fail_remain -= 1
            raise ConnectionError("simulated network partition")

    async def exists(self, key: str) -> bool:
        await self._maybe_delay()
        await self._maybe_fail()
        return key in self._store

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        await self._maybe_delay()
        await self._maybe_fail()
        self._store[key] = str(value)
        return True

    # 兼容少量调用
    async def get(self, key: str):
        await self._maybe_delay()
        await self._maybe_fail()
        return self._store.get(key)


@pytest.mark.asyncio
@pytest.mark.chaos
async def test_token_blacklist_behaves_conservatively_under_partition(monkeypatch):
    """
    Redis 连接异常时，黑名单检查应保守返回未撤销（不中断主流程）。
    """
    from app.services.token_blacklist_service import get_token_blacklist_service

    flaky = FlakyRedis(fail_times=2, delay_ms=0)

    async def _fake_get_redis_client():  # type: ignore
        return flaky

    monkeypatch.setattr(
        "app.services.token_blacklist_service.get_redis_client", _fake_get_redis_client
    )

    svc = get_token_blacklist_service()
    case_id = "chaos:redis_partition:blacklist_exists"
    with perf.time_block(case_id):
        # 前两次 exists 将抛错，服务应捕获并保守返回 False（未撤销）
        assert await svc.is_token_revoked("jti-1") is False
        assert await svc.is_token_revoked("jti-1") is False
        # 第三次开始恢复正常（未写入过，仍返回 False）
        assert await svc.is_token_revoked("jti-1") is False
    # 记录失败至成功的错误次数（初始fail_times=2）
    perf.record(case_id, failures_until_success=2)


@pytest.mark.asyncio
@pytest.mark.chaos
async def test_login_rate_limit_allows_when_redis_unavailable(monkeypatch):
    """登录频率限制在 Redis 异常时不阻断登录（日志记录）。"""
    from app.services.login_security import login_security

    flaky = FlakyRedis(fail_times=3, delay_ms=0)

    async def _fake_get_redis_client():  # type: ignore
        return flaky

    monkeypatch.setattr("app.services.login_security.get_redis_client", _fake_get_redis_client)

    case_id = "chaos:redis_partition:login_rate_limit"
    with perf.time_block(case_id):
        allowed, retry_after = await login_security.check_rate_limit("u@test.com", "1.2.3.4")
        # Redis 异常时，策略为允许继续（避免外部依赖阻断登录）
        assert allowed is True
        assert retry_after is None
    perf.record(case_id, failures_until_success=3)


@pytest.mark.asyncio
@pytest.mark.chaos
async def test_high_latency_does_not_break_blacklist(monkeypatch):
    """高延迟但最终可达时，黑名单检查仍能返回结果。"""
    from app.services.token_blacklist_service import get_token_blacklist_service

    # 仅增加轻微延迟，避免拖慢测试
    slow = FlakyRedis(fail_times=0, delay_ms=10)

    async def _fake_get_redis_client():  # type: ignore
        return slow

    monkeypatch.setattr(
        "app.services.token_blacklist_service.get_redis_client", _fake_get_redis_client
    )

    svc = get_token_blacklist_service()
    case_id = "chaos:redis_latency:blacklist_exists"
    with perf.time_block(case_id):
        assert await svc.is_token_revoked("any") is False
    perf.record(case_id, latency_ms=10)
