"""任务实时事件总线 - 提供Redis发布订阅与本地回退。"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Final, Literal, cast

from redis.asyncio.client import PubSub
from redis.exceptions import RedisError

from ..core.redis_client import get_redis
from ..core.sse import get_sse_service
from ..core.types import JsonValue

logger = logging.getLogger(__name__)

CHANNEL_NAME = "tasks.realtime"

TaskEventType = Literal["connected", "progress", "completed", "error", "close"]
_TASK_EVENT_TYPES: Final[tuple[TaskEventType, ...]] = (
    "connected",
    "progress",
    "completed",
    "error",
    "close",
)
_TASK_EVENT_TYPES_SET: Final[frozenset[str]] = frozenset(_TASK_EVENT_TYPES)


@dataclass(slots=True)
class TaskRealtimeEvent:
    """Redis发布的实时事件消息。"""

    event_type: TaskEventType
    task_id: str
    payload: Dict[str, JsonValue]
    timestamp: str

    def to_json(self) -> str:
        message = {
            "type": self.event_type,
            "task_id": self.task_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }
        return json.dumps(message, ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> "TaskRealtimeEvent":
        data = json.loads(raw)
        event_type = cls._coerce_event_type(data.get("type"))
        task_id = str(data.get("task_id"))
        payload = data.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        timestamp = str(data.get("timestamp", datetime.now(timezone.utc).isoformat()))
        # 确保payload中的值都是JSON兼容类型
        converted_payload: Dict[str, JsonValue] = {}
        for key, value in payload.items():
            converted_payload[key] = cls._coerce_json_value(value)
        return cls(
            event_type=event_type,
            task_id=task_id,
            payload=converted_payload,
            timestamp=timestamp,
        )

    @staticmethod
    def _coerce_event_type(value: Any) -> TaskEventType:
        if isinstance(value, str):
            lowered = value.lower()
            if lowered in _TASK_EVENT_TYPES_SET:
                return cast(TaskEventType, lowered)
        return "progress"

    @staticmethod
    def _coerce_json_value(value: Any) -> JsonValue:
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, list):
            return [TaskRealtimeEvent._coerce_json_value(item) for item in value]
        if isinstance(value, dict):
            return {
                str(k): TaskRealtimeEvent._coerce_json_value(v) for k, v in value.items()
            }
        # 将其他类型转换为字符串，避免序列化问题
        return str(value)


_listener_task: Optional[asyncio.Task[None]] = None
_pubsub: Optional[PubSub] = None
_listener_lock = asyncio.Lock()


async def emit_task_event(
    event_type: TaskEventType,
    task_id: str,
    payload: Dict[str, JsonValue],
) -> None:
    """向Redis发布实时事件，若发布失败则直接推送至本地SSE服务。"""
    event = TaskRealtimeEvent(
        event_type=event_type,
        task_id=task_id,
        payload=payload,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    try:
        redis = await get_redis()
        await redis.publish(CHANNEL_NAME, event.to_json())
    except (RedisError, RuntimeError) as exc:
        logger.warning("Redis publish failed, fallback to local push: %s", exc)
        sse_service = get_sse_service()
        await sse_service.push_event(event.event_type, event.task_id, payload=event.payload)


async def start_task_event_listener() -> None:
    """启动Redis订阅监听，将消息转发到SSE/WebSocket服务。"""
    global _listener_task, _pubsub
    async with _listener_lock:
        if _listener_task is not None and not _listener_task.done():
            return
        redis = await get_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe(CHANNEL_NAME)
        _pubsub = pubsub
        _listener_task = asyncio.create_task(_run_event_listener(pubsub))
        logger.info("Task realtime event listener started (channel=%s)", CHANNEL_NAME)


async def stop_task_event_listener() -> None:
    """停止Redis订阅监听。"""
    global _listener_task, _pubsub
    async with _listener_lock:
        if _listener_task is not None:
            _listener_task.cancel()
            try:
                await _listener_task
            except asyncio.CancelledError:
                pass
            _listener_task = None
        if _pubsub is not None:
            try:
                await _pubsub.unsubscribe(CHANNEL_NAME)
                await _pubsub.close()
            except (RedisError, RuntimeError) as exc:
                logger.warning("Failed to close Redis pubsub cleanly: %s", exc)
            _pubsub = None
        logger.info("Task realtime event listener stopped")


async def _run_event_listener(pubsub: PubSub) -> None:
    try:
        while True:
            try:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
            except (RedisError, RuntimeError) as exc:
                logger.warning("Redis pubsub get_message error: %s", exc)
                await asyncio.sleep(1.0)
                continue

            if message is None:
                await asyncio.sleep(0.1)
                continue

            data = message.get("data")
            if not isinstance(data, str):
                continue

            try:
                event = TaskRealtimeEvent.from_json(data)
            except (ValueError, json.JSONDecodeError) as exc:
                logger.warning("Invalid realtime event payload: %s", exc)
                continue

            sse_service = get_sse_service()
            await sse_service.push_event(event.event_type, event.task_id, payload=event.payload)
    except asyncio.CancelledError:
        logger.debug("Realtime event listener cancelled")
        raise
    except Exception as exc:  # pragma: no cover - 捕获意外异常保证后台稳定
        logger.exception("Realtime event listener crashed: %s", exc)
    finally:
        try:
            await pubsub.close()
        except Exception:
            pass
