"""
反馈事件记录服务

当前实现：
- 首选写入 Redis 列表键（rss:feedback:events）
- Redis 不可用时，降级写入本地 JSONL 文件 backend/data/feedback_events.jsonl

后续PRD-07：
- 将实现真正的 feedback_events 表与仓储层，替换持久化实现即可
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Tuple

from ..core.redis_client import get_redis_client
from ..core.database import get_session_factory
from .feedback_event_store import create_event as db_create_event
from ..core.types import JsonValue
from ..schemas.feedback import FeedbackEventRequest


EVENT_LIST_KEY = "rss:feedback:events"
FALLBACK_FILE = Path("backend/data/feedback_events.jsonl")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


async def record_event(
    req: FeedbackEventRequest, request_id: str | None
) -> Tuple[bool, str, str]:
    """生成 event_id 并记录事件。

    返回 (stored, backend)：backend in {redis, file}
    """
    event_id = str(uuid.uuid4())
    envelope: Dict[str, JsonValue] = {
        "event_id": event_id,
        "timestamp": _now_iso(),
        "request_id": request_id or "",
        "source": req.source.value,
        "event_type": req.event_type.value,
        "task_id": req.task_id,
        "analysis_id": req.analysis_id,
        "user_id": req.user_id,
        # payload（保持扁平，便于后续入库映射）
        "rating": req.rating.value if req.rating is not None else None,
        "reason": req.reason,
        "comment": req.comment,
        "insight_id": req.insight_id,
        "flag": req.flag.value if req.flag is not None else None,
        "tags": req.tags or [],
        "metric_name": req.metric_name,
        "metric_value": req.metric_value,
        "metric_unit": req.metric_unit,
        "context": req.context or {},
    }

    # 1) 优先写入数据库
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            ev_id = await db_create_event(session, req, request_id)
            await session.commit()
            return True, "db", ev_id
    except Exception:
        pass

    # 2) 其次写入Redis
    try:
        client = await get_redis_client()
        await client.lpush(EVENT_LIST_KEY, envelope)
        return True, "redis", event_id
    except Exception:
        # 2) 降级写入本地JSONL
        try:
            _ensure_parent_dir(FALLBACK_FILE)
            line = json.dumps(envelope, ensure_ascii=False)
            # 避免阻塞事件循环
            await asyncio.to_thread(_append_line, FALLBACK_FILE, line)
            return True, "file", event_id
        except Exception:
            return False, "none", event_id


def _append_line(path: Path, line: str) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(line)
        f.write("\n")
