"""分析任务处理时长：统计接口基线验证"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, List, cast

import httpx
import pytest

from tests.performance import baseline_recorder as perf


@pytest.fixture
async def api_client() -> AsyncIterator[httpx.AsyncClient]:
    from backend.app.main import app
    from backend.app.middleware.jwt_middleware import JWTMiddleware

    JWTMiddleware.SKIP_AUTH_PATHS.update({"/api/v1/monitoring/tasks/stats"})

    transport = httpx.ASGITransport(app=cast(Any, app))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
@pytest.mark.performance
async def test_task_stats_processing_time(
    api_client: httpx.AsyncClient, monkeypatch: Any
) -> None:
    from backend.app.core.task_status import UnifiedTaskStatus
    from backend.app.schemas.task_monitor import (
        TaskQueryRequest,
        TaskQueryResponse,
        TaskSnapshot,
    )

    now = datetime.now(timezone.utc)

    def snap(task_id: str, dur_s: int) -> TaskSnapshot:
        return TaskSnapshot(
            task_id=task_id,
            status=UnifiedTaskStatus.COMPLETED,
            progress=100,
            created_at=now - timedelta(seconds=dur_s + 10),
            updated_at=now,
            started_at=now - timedelta(seconds=dur_s),
            completed_at=now,
            queue_name="default",
        )

    tasks: List[TaskSnapshot] = [snap("t1", 120), snap("t2", 240), snap("t3", 60)]

    class FakeResponse:
        def __init__(self, snapshots: List[TaskSnapshot]) -> None:
            self.tasks = snapshots
            self.total = len(snapshots)
            self.limit = len(snapshots)
            self.offset = 0

    async def fake_query(_self: Any, request: TaskQueryRequest) -> FakeResponse:
        return FakeResponse(tasks)

    mod = __import__("backend.app.api.v1.endpoints.monitoring", fromlist=["dummy"])
    monkeypatch.setattr(mod, "get_task_monitor_service", lambda: type("Svc", (), {"query_tasks": fake_query})())

    resp = await api_client.get("/api/v1/monitoring/tasks/stats")
    assert resp.status_code == 200
    data = resp.json()

    perf.record(
        "api:monitoring:tasks:stats",
        avg_processing_time=data["avg_processing_time"],
        max_processing_time=data["max_processing_time"],
        total=data["total_tasks"],
    )
