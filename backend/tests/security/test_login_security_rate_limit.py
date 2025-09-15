"""
登录安全服务测试（频率限制 / 账户锁定 / 可疑活动）

通过 FakeRedis 注入，避免真实依赖。
"""

import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.services.login_security import (
    ACCOUNT_LOCK_THRESHOLD,
    LOGIN_RATE_LIMIT,
    RATE_LIMIT_WINDOW,
    login_security,
)
from app.schemas.auth import LoginSession


class FakeRedis:
    def __init__(self) -> None:
        self._data: dict[str, tuple[str, float | None]] = {}
        self._sets: dict[str, set[str]] = {}

    async def get(self, key: str):
        v = self._data.get(key)
        if not v:
            return None
        value, exp = v
        if exp is not None and time.time() > exp:
            self._data.pop(key, None)
            return None
        return value

    async def set(self, key: str, value, ttl: int | None = None):
        self._data[key] = (str(value), time.time() + ttl if ttl else None)
        return True

    async def incr(self, key: str):
        v = await self.get(key)
        if v is None:
            self._data[key] = ("1", None)
            return 1
        n = int(v) + 1
        # 保持原ttl不变
        _, exp = self._data[key]
        self._data[key] = (str(n), exp)
        return n

    async def ttl(self, key: str):
        v = self._data.get(key)
        if not v:
            return -2
        _, exp = v
        if exp is None:
            return -1
        rem = int(exp - time.time())
        return rem if rem > 0 else -2

    async def delete(self, key: str):
        return 1 if self._data.pop(key, None) else 0

    async def sadd(self, key: str, member: str):
        s = self._sets.setdefault(key, set())
        before = len(s)
        s.add(member)
        return 1 if len(s) > before else 0

    async def expire(self, key: str, ttl: int):
        v = self._data.get(key)
        if not v:
            return False
        value, _ = v
        self._data[key] = (value, time.time() + ttl)
        return True

    async def scard(self, key: str):
        return len(self._sets.get(key, set()))


@pytest.mark.asyncio
async def test_login_rate_limit_window():
    fake = FakeRedis()
    with patch("app.services.login_security.get_redis_client", new=AsyncMock(return_value=fake)):
        email = "rate@test.com"
        ip = "1.2.3.4"
        # 第一次尝试，允许并设置窗口
        allowed, retry_after = await login_security.check_rate_limit(email, ip)
        assert allowed is True and retry_after is None

        # 在窗口内多次尝试至超阈值
        for _ in range(LOGIN_RATE_LIMIT - 1):
            allowed, _ = await login_security.check_rate_limit(email, ip)
            assert allowed is True

        # 超限
        allowed, retry_after = await login_security.check_rate_limit(email, ip)
        assert allowed is False
        assert isinstance(retry_after, int)
        assert 0 < retry_after <= RATE_LIMIT_WINDOW


@pytest.mark.asyncio
async def test_account_lock_after_failures():
    fake = FakeRedis()
    with patch("app.services.login_security.get_redis_client", new=AsyncMock(return_value=fake)):
        email = "lock@test.com"
        # 连续失败达到阈值
        for _ in range(ACCOUNT_LOCK_THRESHOLD):
            session = LoginSession(email=email, ip_address="5.6.7.8", success=False)
            session.failure_reason = "invalid_credentials"
            await login_security.record_failed_attempt(session)

        locked, unlock_time = await login_security.check_account_lock(email)
        assert locked is True
        assert isinstance(unlock_time, datetime)


@pytest.mark.asyncio
async def test_suspicious_activity_detection_multi_ips():
    fake = FakeRedis()
    with patch("app.services.login_security.get_redis_client", new=AsyncMock(return_value=fake)):
        email = "sus@test.com"
        # 5分钟窗口内 4 个不同IP
        ips = ["10.0.0.1", "10.0.0.2", "10.0.0.3", "10.0.0.4"]
        flagged = False
        for ip in ips:
            flagged = await login_security.detect_suspicious_activity(email, ip)
        assert flagged is True

