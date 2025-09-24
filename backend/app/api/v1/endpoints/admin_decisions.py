from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException

from ....api.deps.admin_guard import ensure_admin_write_access
from ....core.database import get_session_factory
from ....schemas.admin.decisions import (
    AdminCommunityDecisionRequest,
    AdminDecisionResponse,
    AdminDecisionSaved,
)
from ....schemas.feedback import FeedbackEventRequest, FeedbackEventType, FeedbackSource
from ....services.feedback_event_store import create_event as db_create_event


router = APIRouter(prefix="/admin/decisions", tags=["Admin-决策"])


@router.post("/community", response_model=AdminDecisionResponse)
async def post_decision_community(
    request: Request, payload: AdminCommunityDecisionRequest
) -> AdminDecisionResponse:
    ensure_admin_write_access(request)

    session_factory = get_session_factory()
    async with session_factory() as session:
        ev_id = await db_create_event(
            session,
            FeedbackEventRequest(
                source=FeedbackSource.admin,
                event_type=FeedbackEventType.community_decision,
                task_id="",
                user_id=getattr(request.state, "user_id", None),
                context={
                    "community": payload.community,
                    "action": payload.action,
                    "labels": payload.labels,
                    "reason": payload.reason,
                },
            ),
            request_id=getattr(request.state, "request_id", None),
        )
        await session.commit()

        return AdminDecisionResponse(
            code=0,
            data=AdminDecisionSaved(event_id=ev_id),
            trace_id=getattr(request.state, "request_id", None),
        )
