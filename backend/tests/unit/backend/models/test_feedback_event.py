from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone

from app.schemas.feedback import (
    FeedbackEventRequest,
    FeedbackEventType,
    FeedbackSource,
    RatingValue,
)
from app.services.feedback_event_store import create_event, list_events


@pytest.mark.asyncio
async def test_create_and_list_feedback_event(db_session: "object") -> None:
    # 构造最小合法请求
    req = FeedbackEventRequest(
        source=FeedbackSource.user,
        event_type=FeedbackEventType.analysis_rating,
        task_id="tsk_unit",
        rating=RatingValue.like,
    )

    ev_id = await create_event(db_session, req, request_id="test-req")
    assert isinstance(ev_id, str) and len(ev_id) > 0

    # 查询应命中刚写入的事件
    start = datetime.now(timezone.utc) - timedelta(minutes=5)
    end = datetime.now(timezone.utc) + timedelta(minutes=5)
    rows = await list_events(db_session, start=start, end=end, limit=10)
    assert any(str(r.id) == ev_id for r in rows)
