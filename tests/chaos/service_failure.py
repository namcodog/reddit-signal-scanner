"""Chaos: 服务失效/中断→恢复 场景。

覆盖：
- Redis 客户端不健康时触发重连
- DB 执行失败的健康检查路径应返回 unhealthy 而非崩溃
"""

from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.redis_client import RedisClient
from tests.performance import baseline_recorder as perf


@pytest.mark.asyncio
@pytest.mark.chaos
async def test_redis_client_reconnects_when_unhealthy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.core import redis_client as rc

    class FakeClient:
        def __init__(self) -> None:
            self.connected = False
            self.ping_called = 0

        async def connect(self) -> None:
            self.connected = True

        async def is_healthy(self) -> bool:
            # 第一次报告不健康，触发重连；第二次健康
            self.ping_called += 1
            return self.ping_called >= 2

    fake = FakeClient()
    fake_client = cast(RedisClient, fake)
    monkeypatch.setattr(rc, "_redis_client", fake_client)

    case_id = "chaos:service_failure:redis_reconnect"
    with perf.time_block(case_id):
        client = await rc.get_redis_client()
        # 触发一次重连后应返回全局实例（即 fake 本身），且标记健康
        assert client is fake_client
        assert fake.connected is True
    perf.record(case_id, reconnect_attempts=fake.ping_called)


@pytest.mark.asyncio
@pytest.mark.chaos
async def test_auth_health_check_handles_db_failure(
    _monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DB 执行失败时，健康检查应返回 unhealthy 状态而非抛出异常。"""
    from backend.app.api.v1.endpoints.auth import auth_health_check

    class FakeBadSession:
        async def execute(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("DB down")

    # 直接调用端点函数并传入坏会话
    case_id = "chaos:service_failure:auth_health_check"
    with perf.time_block(case_id):
        resp = await auth_health_check(db=cast(AsyncSession, FakeBadSession()))
        assert resp.status == "unhealthy"
        assert "DB down" in (resp.error or "")
