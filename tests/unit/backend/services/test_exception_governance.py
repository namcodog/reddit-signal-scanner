import asyncio
import json
from typing import Any, Mapping, Optional

import pytest
from sqlalchemy.exc import SQLAlchemyError

from backend.app.services.cache_updater import SimpleCacheUpdater
from backend.app.services.community_discovery import CommunityDiscoveryService
from backend.app.services.data_cleanup_service import DataCleanupService, CleanupCategory
from backend.app.services.task_status_service import TaskStatusService


class _FakeRedisSync:
    def __init__(self, get_value: Optional[str] = None) -> None:
        self._get_value = get_value
        self.set_calls: list[tuple[str, str, int]] = []

    def get(self, key: str) -> Optional[str]:
        return self._get_value

    def set(self, key: str, value: str, ex: int) -> None:
        self.set_calls.append((key, value, ex))

    def keys(self, pattern: str) -> list[str]:
        return []


class _FakeRedisAsync:
    def __init__(self, get_value: Optional[str] = None) -> None:
        self._get_value = get_value

    async def get(self, key: str) -> Optional[str]:
        return self._get_value


class _DummyAsyncSession:
    async def execute(self, *_args: Any, **_kwargs: Any) -> Any:  # pragma: no cover
        raise SQLAlchemyError("db error")


def test_cache_updater_handles_invalid_json_on_merge(monkeypatch: pytest.MonkeyPatch) -> None:
    updater = SimpleCacheUpdater()
    # 现有缓存为无效 JSON，触发 JSONDecodeError
    updater.redis_client = _FakeRedisSync(get_value="{invalid-json}")  # type: ignore[assignment]
    ok = updater.update_community_posts("r/test", {"posts": []})
    assert ok is False


@pytest.mark.asyncio
async def test_discovery_get_cached_result_invalid_json() -> None:
    svc = CommunityDiscoveryService()
    # 注入异步Redis，返回坏JSON
    svc.redis_client = _FakeRedisAsync(get_value="not a json")  # type: ignore[assignment]
    res = await svc._get_cached_result("req-1")
    assert res is None


def test_data_cleanup_dry_run_unsupported_category_returns_failure() -> None:
    # 提供一个哑会话（不会被用到）
    dummy_db = object()  # type: ignore[assignment]
    service = DataCleanupService(dummy_db)  # type: ignore[arg-type]
    # 清空策略映射，制造不支持的类别
    service._strategies = {}  # type: ignore[attr-defined]
    result = service._execute_dry_run_cleanup(CleanupCategory.COMPLETED_TASKS, {})
    assert result["success"] is False
    assert "不支持" in (result["error_message"] or "")


def test_task_status_format_timestamp_handles_invalid_input() -> None:
    # 使用同步的内部方法进行健壮性测试
    # 构造一个无效的 timestamp（非 datetime 对象），应当返回当前时间字符串
    svc = TaskStatusService.__new__(TaskStatusService)  # type: ignore[call-arg]
    ts = svc._format_timestamp(12345)  # type: ignore[arg-type]
    assert isinstance(ts, str) and len(ts) >= 10

