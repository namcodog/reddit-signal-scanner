"""
Admin 社区指标 Schemas（严格类型）

用于 PRD‑07 社区验收页：
- Must Gates 计算
- C‑Score 计算与状态灯
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


StatusColor = Literal["green", "yellow", "red"]


class MustGates(BaseModel):
    freshness_hours_max: float = Field(default=48.0)
    min_hits_7d: int = Field(default=30)
    max_dup_ratio: float = Field(default=0.15)
    max_spam_ratio: float = Field(default=0.10)
    min_topic_score: float = Field(default=0.60)


class MustResult(BaseModel):
    freshness_ok: bool
    hits_ok: bool
    dup_ok: bool
    spam_ok: bool
    topic_ok: bool

    def all_passed(self) -> bool:
        return (
            self.freshness_ok
            and self.hits_ok
            and self.dup_ok
            and self.spam_ok
            and self.topic_ok
        )


class CommunitySummary(BaseModel):
    community: str
    last_crawled_at: Optional[datetime] = None
    freshness_hours: float = Field(..., ge=0)
    hit_7d: int = Field(..., ge=0)
    dup_ratio: float = Field(..., ge=0.0, le=1.0)
    spam_ratio: float = Field(..., ge=0.0, le=1.0)
    topic_score: float = Field(..., ge=0.0, le=1.0)

    # 计算项
    activity_score: float = Field(..., ge=0.0, le=100.0)
    freshness_score: float = Field(..., ge=0.0, le=100.0)
    topic_percent: float = Field(..., ge=0.0, le=100.0)
    c_score: int = Field(..., ge=0, le=100)
    status_color: StatusColor

    # Must Gates 结果与样本
    must: MustResult
    evidence_samples: List[str] = Field(default_factory=list)


class CommunitiesListData(BaseModel):
    items: List[CommunitySummary]
    total: int


class CommunitiesListResponse(BaseModel):
    code: int = 0
    data: CommunitiesListData
    trace_id: str | None = None
