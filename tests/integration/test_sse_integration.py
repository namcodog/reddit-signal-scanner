"""Typed pytest coverage for SSE task broadcaster integration."""

from __future__ import annotations

import asyncio
from typing import List

import pytest

from backend.app.models.task import TaskStatus, TaskUpdate
from backend.app.services.sse_service import TaskSSEService, get_sse_service


class _Collector:
    """Helper to record SSE messages emitted for a given task id."""

    def __init__(self, service: TaskSSEService, task_id: str) -> None:
        self.service = service
        self.task_id = task_id
        self.messages: List[str] = []

    async def consume(self, expected: int) -> None:
        async for raw in self.service.stream_updates(self.task_id):
            self.messages.append(raw)
            if len(self.messages) >= expected:
                break


@pytest.mark.asyncio
async def test_task_update_serialisation_matches_contract() -> None:
    updates = [
        TaskUpdate.create_started("task-001", "任务开始"),
        TaskUpdate.create_progress("task-001", 33, "正在处理数据"),
        TaskUpdate.create_progress("task-001", 66, "分析中..."),
        TaskUpdate.create_completed("task-001", "分析完成"),
        TaskUpdate.create_failed("task-001", "网络连接失败"),
    ]
    for update in updates:
        payload = update.to_json()
        assert "\"task_id\"" in payload
        assert "\"status\"" in payload
        assert "\"progress\"" in payload
        assert "\"message\"" in payload
        sse_format = update.to_sse_format()
        assert sse_format.startswith("data: ")
        assert sse_format.endswith("\n\n")


@pytest.mark.asyncio
async def test_sse_service_notifies_single_consumer() -> None:
    service = get_sse_service()
    task_id = "test-task-001"
    collector = _Collector(service, task_id)
    consumer = asyncio.create_task(collector.consume(expected=3))
    await asyncio.sleep(0.05)
    assert service.get_connection_count() == 1

    service.notify_update(task_id, TaskStatus.PROCESSING, 10, "开始测试")
    service.notify_update(task_id, TaskStatus.PROCESSING, 50, "测试进行中")
    service.notify_update(task_id, TaskStatus.COMPLETED, 100, "测试完成")

    await consumer
    assert service.get_connection_count() == 0
    assert len(collector.messages) == 3


@pytest.mark.asyncio
async def test_sse_service_handles_concurrent_tasks() -> None:
    service = get_sse_service()
    collectors = [_Collector(service, f"concurrent-task-{index}") for index in range(3)]
    consumers = [asyncio.create_task(collector.consume(expected=2)) for collector in collectors]
    await asyncio.sleep(0.05)
    assert service.get_connection_count() == 3

    for index, collector in enumerate(collectors):
        service.notify_update(collector.task_id, TaskStatus.PROCESSING, 50, f"任务{index}进行中")
        service.notify_update(collector.task_id, TaskStatus.COMPLETED, 100, f"任务{index}完成")

    await asyncio.gather(*consumers)
    assert service.get_connection_count() == 0
    for collector in collectors:
        assert len(collector.messages) == 2
