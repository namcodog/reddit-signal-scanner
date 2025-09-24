"""任务实时更新的WebSocket端点。"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from ...core.sse import SSEEvent, get_sse_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["实时通信"])

PING_INTERVAL_SECONDS = 30.0


def _serialize_event(event: SSEEvent) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "type": event.type,
        "task_id": event.task_id,
    }
    payload.update(event.data)

    timestamp = event.timestamp or datetime.now(timezone.utc).timestamp()
    payload["timestamp"] = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()

    # 如果是心跳事件（progress + heartbeat标记），统一为heartbeat类型
    if event.type == "progress" and payload.get("heartbeat"):
        payload["type"] = "heartbeat"
        payload.setdefault("message", "server heartbeat")
        payload.pop("heartbeat", None)

    return payload


@router.websocket("/tasks/{task_id}")
async def task_updates(websocket: WebSocket, task_id: str) -> None:
    """推送指定任务的实时状态更新。"""
    try:
        UUID(task_id)
    except ValueError:
        # 非法的任务ID直接拒绝连接
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    logger.info("WebSocket connection accepted for task %s", task_id)

    sse_service = get_sse_service()
    queue = await sse_service.register_connection(task_id)

    try:
        connected_payload = {
            "type": "connected",
            "task_id": task_id,
            "message": "连接已建立",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await websocket.send_json(connected_payload)

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=PING_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                heartbeat_payload = {
                    "type": "heartbeat",
                    "task_id": task_id,
                    "message": "server heartbeat",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                await websocket.send_json(heartbeat_payload)
                continue

            payload = _serialize_event(event)
            await websocket.send_json(payload)

            if payload["type"] in {"completed", "error", "close"}:
                logger.info("WebSocket connection closed automatically for task %s", task_id)
                break

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for task %s", task_id)
    except Exception as exc:  # noqa: BLE001 - 保证连接异常不会导致应用崩溃
        logger.exception("WebSocket error for task %s: %s", task_id, exc)
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
    finally:
        await sse_service.unregister_connection(task_id, queue)
        logger.debug("WebSocket queue cleaned for task %s", task_id)
