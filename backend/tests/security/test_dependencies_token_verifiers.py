"""
依赖验证：verify_refresh_token_from_header / verify_any_token_for_logout

策略：
- 通过 patch get_token_from_request 返回我们构造的token
- 通过 patch get_token_blacklist_service 注入Fake实现
- 通过 patch get_jwt_handler 保证签发/验证一致
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.jwt_handler import JWTHandler
from app.core.dependencies import (
    verify_any_token_for_logout,
    verify_refresh_token_from_header,
)
from app.services.token_blacklist_service import TokenBlacklistService


class FakeBlacklist(TokenBlacklistService):
    def __init__(self) -> None:
        super().__init__()
        self.revoked = set()
        self.user_revoked = set()

    async def is_token_revoked(self, jti: str) -> bool:  # type: ignore[override]
        return jti in self.revoked

    async def revoke_token(self, jti: str, token_type: str, expires_delta: int, user_id: str | None = None) -> bool:  # type: ignore[override]
        self.revoked.add(jti)
        return True

    async def revoke_all_user_tokens(self, user_id: str, reason: str = "logout_all_devices") -> int:  # type: ignore[override]
        self.user_revoked.add(user_id)
        return 1

    async def is_user_globally_revoked(self, user_id: str) -> bool:  # type: ignore[override]
        return user_id in self.user_revoked


@pytest.mark.asyncio
async def test_verify_refresh_token_valid_flow():
    handler = JWTHandler()
    refresh = handler.create_refresh_token("u-1", "t-1", "u@test.com")

    with (
        patch("app.core.auth.get_token_from_request", return_value=refresh),
        patch("app.core.jwt_handler.get_jwt_handler", return_value=handler),
        patch("app.core.dependencies.get_jwt_handler", return_value=handler),
        patch("app.core.dependencies.get_token_blacklist_service", return_value=FakeBlacklist()),
    ):
        # 传入一个简单的request对象占位
        request = SimpleNamespace(headers={})
        info = await verify_refresh_token_from_header(request)
        assert info.user_id == handler.verify_refresh_token(refresh).user_id
        assert info.token_type == "refresh"


@pytest.mark.asyncio
async def test_verify_refresh_token_revoked():
    handler = JWTHandler()
    refresh = handler.create_refresh_token("u-2", "t-2", "u2@test.com")
    fake = FakeBlacklist()
    # 先撤销
    payload = handler.verify_refresh_token(refresh)
    await fake.revoke_token(payload.jti, "refresh", 600, payload.user_id)

    with (
        patch("app.core.auth.get_token_from_request", return_value=refresh),
        patch("app.core.jwt_handler.get_jwt_handler", return_value=handler),
        patch("app.core.dependencies.get_jwt_handler", return_value=handler),
        patch("app.core.dependencies.get_token_blacklist_service", return_value=fake),
    ):
        request = SimpleNamespace(headers={})
        with pytest.raises(Exception):  # AuthenticationError
            await verify_refresh_token_from_header(request)


@pytest.mark.asyncio
async def test_verify_any_token_for_logout_with_access_token():
    handler = JWTHandler()
    access = handler.create_access_token("u-3", "t-3", "u3@test.com", permissions=["read"])

    with (
        patch("app.core.auth.get_token_from_request", return_value=access),
        patch("app.core.jwt_handler.get_jwt_handler", return_value=handler),
        patch("app.core.dependencies.get_jwt_handler", return_value=handler),
    ):
        request = SimpleNamespace(headers={})
        info = await verify_any_token_for_logout(request)
        assert info.user_id == handler.verify_access_token(access).user_id
        assert info.token_type == "access"

