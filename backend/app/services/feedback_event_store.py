"""
反馈事件仓储（Repository）

职责：
- 将统一反馈事件写入数据库表 feedback_events
- 提供按时间范围和数量读取的基础查询

类型约束：严格使用 Pydantic/TypedDict 定义请求结构，避免 Any。
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.feedback_event import FeedbackEvent
from ..schemas.feedback import FeedbackEventRequest
from ..core.types import JsonValue


async def create_event(
    session: AsyncSession,
    request: FeedbackEventRequest,
    request_id: Optional[str] = None,
) -> str:
    """写入一条反馈事件并返回事件ID（UUID字符串）。"""
    # 统一封装 payload（保留完整上下文，便于后续扩展）
    payload: dict[str, JsonValue] = {
        "source": request.source.value,
        "event_type": request.event_type.value,
        "task_id": request.task_id,
        "analysis_id": request.analysis_id,
        "user_id": request.user_id,
        "rating": request.rating.value if request.rating is not None else None,
        "reason": request.reason,
        "comment": request.comment,
        "insight_id": request.insight_id,
        "flag": request.flag.value if request.flag is not None else None,
        "tags": request.tags or [],
        "metric_name": request.metric_name,
        "metric_value": request.metric_value,
        "metric_unit": request.metric_unit,
        "context": request.context or {},
        "request_id": request_id,
    }

    row = FeedbackEvent(
        source=request.source.value,
        event_type=request.event_type.value,
        user_id=request.user_id,
        task_id=request.task_id,
        analysis_id=request.analysis_id,
        payload=payload,
    )
    session.add(row)
    await session.flush()  # 让服务器端生成 id
    # 不在此提交，由调用方决定事务边界
    return str(row.id)


async def list_events(
    session: AsyncSession,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = 100,
) -> List[FeedbackEvent]:
    """按时间范围获取事件（倒序），最多 limit 条。"""
    stmt = select(FeedbackEvent).order_by(FeedbackEvent.created_at.desc()).limit(limit)
    if start is not None:
        stmt = stmt.where(FeedbackEvent.created_at >= start)
    if end is not None:
        stmt = stmt.where(FeedbackEvent.created_at <= end)

    result = await session.execute(stmt)
    return list(result.scalars())

