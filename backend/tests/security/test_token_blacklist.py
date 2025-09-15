"""
Token 黑名单服务测试（基于内存 FakeRedis）

覆盖点：
- revoke_token / is_token_revoked
- revoke_all_user_tokens / is_user_globally_revoked
- revoke_token_with_audit（含TTL与审计记录）
"""

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import pytest
from unittest.mock import AsyncMock, patch

from app.schemas.auth import BlacklistedToken
from app.services.token_blacklist_service import get_token_blacklist_service


class FakeRedisClient:
    def __init__(self) -> None:
        self._store: Dict[str, tuple[str, Optional[float]]] = {}
        self._sets: Dict[str, set] = {}

    async def get(self, key: str) -> Optional[str]:
        v = self._store.get(key)
        if not v:
            return None
        value, expires = v
        if expires is not None and time.time() > expires:
            self._store.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        expires = time.time() + ttl if ttl else None
        self._store[key] = (str(value), expires)
        return True

    async def delete(self, *keys: str) -> int:
        cnt = 0
        for k in keys:
            if k in self._store:
                self._store.pop(k, None)
                cnt += 1
        return cnt

    async def exists(self, key: str) -> bool:
        return (await self.get(key)) is not None

    async def ttl(self, key: str) -> int:
        v = self._store.get(key)
        if not v:
            return -2
        _, expires = v
        if expires is None:
            return -1
        remaining = int(expires - time.time())
        return remaining if remaining > 0 else -2

    # set ops (used by login_security, not strictly needed here but harmless)
    async def sadd(self, key: str, *members: Any) -> int:
        s = self._sets.setdefault(key, set())
        before = len(s)
        for m in members:
            s.add(m)
        return len(s) - before

    async def expire(self, key: str, ttl: int) -> bool:
        v = self._store.get(key)
        if not v:
            return False
        value, _ = v
        self._store[key] = (value, time.time() + ttl)
        return True

    async def scard(self, key: str) -> int:
        return len(self._sets.get(key, set()))


@pytest.mark.asyncio
async def test_revoke_and_check_token_blacklist():
    fake = FakeRedisClient()
    with patch("app.services.token_blacklist_service.get_redis_client", new=AsyncMock(return_value=fake)):
        svc = get_token_blacklist_service()

        jti = "jti-123"
        ok = await svc.revoke_token(jti=jti, token_type="access", expires_delta=120, user_id="u-1")
        assert ok is True

        revoked = await svc.is_token_revoked(jti)
        assert revoked is True


@pytest.mark.asyncio
async def test_global_user_revoke_and_check():
    fake = FakeRedisClient()
    with patch("app.services.token_blacklist_service.get_redis_client", new=AsyncMock(return_value=fake)):
        svc = get_token_blacklist_service()

        count = await svc.revoke_all_user_tokens("user-xyz")
        assert count == 1
        assert await svc.is_user_globally_revoked("user-xyz") is True


@pytest.mark.asyncio
async def test_revoke_with_audit_record():
    fake = FakeRedisClient()
    with patch("app.services.token_blacklist_service.get_redis_client", new=AsyncMock(return_value=fake)):
        svc = get_token_blacklist_service()

        now = datetime.now(timezone.utc)
        record = BlacklistedToken(
            jti="jti-audit-1",
            token_type="refresh",
            user_id=uuid_from_str("1beee4e8-2c3d-4b35-9f20-2a15a3e6a111"),
            tenant_id=uuid_from_str("1beee4e8-2c3d-4b35-9f20-2a15a3e6a222"),
            blacklisted_at=now,
            expires_at=now + timedelta(seconds=600),
            reason="token_refresh",
        )

        ok = await svc.revoke_token_with_audit(record)
        assert ok is True

        # blocklist 生效
        assert await svc.is_token_revoked("jti-audit-1") is True


def uuid_from_str(s: str):
    import uuid as _uuid

    return _uuid.UUID(s)

