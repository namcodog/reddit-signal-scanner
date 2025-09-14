"""分析任务处理时长：统计接口基线验证

目标：
- 通过 /api/v1/monitoring/tasks/stats 验证平均/最大处理时长
- 基线：max_processing_time 与 avg_processing_time < 300s
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, List

import pytest
from httpx import ASGITransport, AsyncClient

from tests.performance import baseline_recorder as perf


@pytest.fixture
async def api_client() -> AsyncIterator[AsyncClient]:
    from backend.app.main import app
    from backend.app.middleware.jwt_middleware import JWTMiddleware

    JWTMiddleware.SKIP_AUTH_PATHS.update({
        "/api/v1/monitoring/tasks/stats",
    })

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client


@pytest.mark.asyncio
@pytest.mark.performance
async def test_task_stats_processing_time(api_client: AsyncClient, monkeypatch: Any) -> None:
    # 构造假的 TaskTracker 响应
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

    class FakeTracker:
        def query_tasks(self, request: TaskQueryRequest) -> TaskQueryResponse:
            return TaskQueryResponse(
                tasks=tasks, total=len(tasks), limit=1000, offset=0
            )

    mod = __import__(
        "backend.app.api.v1.endpoints.monitoring",
        fromlist=["dummy"],
    )
    monkeypatch.setattr(mod, "_get_task_tracker", lambda: FakeTracker())

    case_id = "api:stats:processing_time"
    payload = {"period": "day"}
    resp = await api_client.post("/api/v1/monitoring/tasks/stats", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    avg_s = float(data.get("avg_processing_time", 0))
    max_s = float(data.get("max_processing_time", 0))

    # KPI：< 300 秒（5 分钟）
    assert avg_s < 300.0
    assert max_s < 300.0
    perf.record(
        case_id,
        avg_processing_time_s=round(avg_s, 2),
        max_processing_time_s=round(max_s, 2),
    )
