"""Integration tests for real-time task updates via WebSocket and SSE."""

from __future__ import annotations

import json
import uuid
from typing import Dict, Optional

from redis.exceptions import RedisError
from starlette.testclient import TestClient

from backend.app.main import app
from backend.app.services.task_event_bus import emit_task_event


async def _async_noop(*_: object, **__: object) -> None:
    return None


def _prepare_app(monkeypatch) -> None:
    """Patch costly startup dependencies for isolated testing."""

    monkeypatch.setattr("backend.app.main.init_database", _async_noop)
    monkeypatch.setattr("backend.app.main.close_database", _async_noop)
    monkeypatch.setattr("backend.app.main.close_redis_client", _async_noop)
    monkeypatch.setattr("backend.app.main.start_task_event_listener", _async_noop)
    monkeypatch.setattr("backend.app.main.stop_task_event_listener", _async_noop)

    async def fake_get_redis_client(*_: object, **__: object) -> None:
        raise RedisError("redis disabled for realtime integration tests")

    monkeypatch.setattr(
        "backend.app.main.get_redis_client",
        fake_get_redis_client,
    )

    async def fake_get_redis(*_: object, **__: object) -> None:
        raise RedisError("redis disabled for realtime integration tests")

    monkeypatch.setattr(
        "backend.app.services.task_event_bus.get_redis",
        fake_get_redis,
    )

    async def bypass_jwt(self, scope, receive, send) -> None:  # type: ignore[override]
        await self.app(scope, receive, send)

    monkeypatch.setattr(
        "backend.app.middleware.jwt_middleware.JWTMiddleware.__call__",
        bypass_jwt,
    )


def _read_sse_event(response) -> Dict[str, object]:
    """Read the next Server-Sent Event from a streaming response."""

    buffer = ""
    for chunk in response.iter_text():
        buffer += chunk
        while "\n\n" in buffer:
            block, buffer = buffer.split("\n\n", 1)
            data: Optional[str] = None
            for line in block.splitlines():
                if line.startswith("data: "):
                    data = line[6:]
                    break
            if data is not None:
                return json.loads(data)

    raise AssertionError("No SSE event received")


def test_websocket_realtime_updates(monkeypatch) -> None:
    """WebSocket endpoint should deliver task progress updates."""

    _prepare_app(monkeypatch)

    with TestClient(app) as client:
        task_id = str(uuid.uuid4())

        with client.websocket_connect(f"/ws/tasks/{task_id}") as websocket:
            connected = websocket.receive_json()
            assert connected["type"] == "connected"
            assert connected["task_id"] == task_id

            payload: Dict[str, object] = {
                "status": "processing",
                "progress": 58,
                "message": "Processing batch",
            }
            client.portal.call(emit_task_event, "progress", task_id, payload)

            message = websocket.receive_json()
            assert message["type"] == "progress"
            assert message["task_id"] == task_id
            assert message["status"] == "processing"
            assert message["progress"] == 58


def test_sse_realtime_updates(monkeypatch) -> None:
    """SSE endpoint should stream progress updates with Redis offline."""

    _prepare_app(monkeypatch)

    with TestClient(app) as client:
        task_id = str(uuid.uuid4())

        with client.stream("GET", f"/api/v1/events/{task_id}") as response:
            connected_event = _read_sse_event(response)
            assert connected_event["type"] == "connected"
            assert connected_event["task_id"] == task_id

            payload: Dict[str, object] = {
                "status": "processing",
                "progress": 83,
                "message": "Streaming SSE update",
            }
            client.portal.call(emit_task_event, "progress", task_id, payload)

            progress_event = _read_sse_event(response)
            assert progress_event["type"] == "progress"
            assert progress_event["task_id"] == task_id
            assert progress_event["status"] == "processing"
            assert progress_event["progress"] == 83
