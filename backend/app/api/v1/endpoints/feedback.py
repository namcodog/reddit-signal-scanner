"""
反馈与埋点端点

用途：前台“赞/踩 + 洞察标注 + 轻量指标”统一入口
路径：POST /api/v1/feedback/events
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Request

from ....schemas.common.responses import ResponseStatus
from ....schemas.feedback import (
    FeedbackEventRequest,
    FeedbackEventResponse,
    FeedbackEventSaved,
)
from ....services.feedback_event_service import record_event


router = APIRouter(prefix="/feedback", tags=["用户反馈"])


@router.post("/events", response_model=FeedbackEventResponse, summary="记录用户反馈事件")
async def post_feedback_event(
    request: Request, payload: FeedbackEventRequest
) -> FeedbackEventResponse:
    """接收前台埋点事件。

    认证策略：匿名可用；若JWT存在，将自动注入 user_id。
    存储策略：优先Redis，失败降级到本地JSONL；PRD-07落地数据库后替换。
    """
    # 尝试注入 user_id（如果中间件已认证）
    if getattr(request.state, "user_id", None) and payload.user_id is None:
        payload.user_id = str(request.state.user_id)

    stored, backend, event_id = await record_event(
        payload, getattr(request.state, "request_id", None)
    )

    return FeedbackEventResponse(
        status=ResponseStatus.SUCCESS if stored else ResponseStatus.ERROR,
        message="记录成功" if stored else "记录失败",
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        request_id=getattr(request.state, "request_id", None),
        data=FeedbackEventSaved(
            event_id=event_id,
            stored=stored,
            stored_backend=backend,
            timestamp=datetime.now(timezone.utc),
        ),
    )
