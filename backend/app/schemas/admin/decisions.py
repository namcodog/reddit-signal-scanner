from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


CommunityAction = Literal["approve", "experiment", "pause", "blacklist"]


class AdminCommunityDecisionRequest(BaseModel):
    community: str = Field(..., min_length=3)
    action: CommunityAction
    labels: List[str] = Field(default_factory=list)
    reason: Optional[str] = None


class AdminDecisionSaved(BaseModel):
    event_id: str


class AdminDecisionResponse(BaseModel):
    code: int = 0
    data: AdminDecisionSaved
    trace_id: Optional[str] = None

