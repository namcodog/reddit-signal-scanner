"""Typed pytest coverage for the simplified SSE broadcaster implementation."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List

import pytest

from backend.app.services.simple_sse_broadcaster import ProductionSSEBroadcaster, SimpleTaskBroadcaster


class MockResponse:
    """Tiny stand-in for FastAPI Response streaming behaviour."""

    def __init__(self) -> None:
        self.messages: List[str] = []
        self.is_connected = True

    async def send_text(self, text: str) -> None:
        if not self.is_connected:
            raise RuntimeError("Connection closed")
        self.messages.append(text)


@pytest.mark.asyncio
async def test_simple_broadcast_sends_to_each_connection() -> None:
    broadcaster = SimpleTaskBroadcaster()
    responses = [MockResponse() for _ in range(3)]
    task_id = "test-task-001"

    connections = [await broadcaster.add_connection(f"{task_id}-{i}", response) for i, response in enumerate(responses)]
    assert len(connections) == 3

    await broadcaster.broadcast_task_update(
        task_id="test-task-001-0",
        status="processing",
        progress=50,
        message="测试消息",
    )

    msg = responses[0].messages[0]
    assert "test-task-001-0" in msg
    assert "processing" in msg
    assert "50" in msg

    responses[1].is_connected = False
    await broadcaster.broadcast_task_update(
        task_id="test-task-001-1",
        status="failed",
        progress=0,
        message="连接失败测试",
    )
    assert broadcaster.get_connection_count() == 2


@pytest.mark.asyncio
async def test_cleanup_removes_expired_connections() -> None:
    broadcaster = SimpleTaskBroadcaster()
    for index in range(100):
        await broadcaster.add_connection(f"temp-task-{index}", MockResponse())
    assert broadcaster.get_connection_count() == 100

    current = time.time()
    for connection in list(broadcaster.connections):
        connection.created_at = current - 400
        connection.last_ping = current - 400

    await broadcaster.cleanup_expired_connections()
    assert broadcaster.get_connection_count() == 0
    assert broadcaster.get_task_count() == 0


@pytest.mark.asyncio
async def test_production_broadcaster_enforces_limits() -> None:
    broadcaster = ProductionSSEBroadcaster(max_connections=50)
    responses: List[MockResponse] = []
    for index in range(60):
        response = MockResponse()
        try:
            await broadcaster.add_connection(f"task-{index}", response)
            responses.append(response)
        except RuntimeError:
            break
    assert broadcaster.get_connection_count() <= 50
    metrics: Dict[str, Any] = broadcaster.get_metrics()
    assert "connection_count" in metrics


@pytest.mark.asyncio
async def test_connections_support_parallel_updates() -> None:
    broadcaster = SimpleTaskBroadcaster()

    async def open_connection(index: int) -> None:
        response = MockResponse()
        await broadcaster.add_connection(f"co-task-{index}", response)
        await broadcaster.broadcast_task_update(
            task_id=f"co-task-{index}",
            status="done",
            progress=100,
            message="parallel",
        )
        assert response.messages

    await asyncio.gather(*(open_connection(index) for index in range(10)))
    assert broadcaster.get_connection_count() == 10
