"""Chaos: 数据损坏/不一致 容错。

覆盖：
- Redis 返回非 JSON/损坏 JSON 时的容错
- JWT 调试信息在非法 token 时返回错误对象而非异常
"""

from typing import Any, Optional, cast

import pytest

from backend.app.core.redis_client import RedisClient
from tests.performance import baseline_recorder as perf


class CorruptRedis:
    async def get(self, key: str, default: Optional[Any] = None) -> str:
        # 返回看起来像 JSON 但不完整的数据
        return '{"incomplete": '

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        return True


@pytest.mark.asyncio
@pytest.mark.chaos
async def test_redis_get_handles_corrupted_json(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.core.redis_client import redis_get

    async def _fake_get_redis_client() -> RedisClient:
        return cast(RedisClient, CorruptRedis())

    # 替换 token_blacklist_service 内部使用的 redis 获取函数（其依赖同一模块方法）
    monkeypatch.setattr(
        "backend.app.core.redis_client.get_redis_client", _fake_get_redis_client
    )

    # 直接调用 redis_get，预期不抛异常并返回原始字符串
    case_id = "chaos:data_corruption:redis_get_corrupted_json"
    with perf.time_block(case_id):
        val = await redis_get("some:key")
        assert isinstance(val, str)


def test_jwt_get_token_info_returns_error_on_invalid_token() -> None:
    from backend.app.core.jwt_handler import JWTHandler

    handler = JWTHandler()
    case_id = "chaos:data_corruption:jwt_invalid_token_info"
    with perf.time_block(case_id):
        info = handler.get_token_info("invalid.token.structure")
        assert isinstance(info, dict)
        assert "error" in info
        raw_token = info.get("raw_token")
        assert isinstance(raw_token, str)
        assert raw_token.startswith("invalid.tok")
