from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class AnalysisMustGates(BaseModel):
    evidence_coverage_min: float = Field(default=0.80, ge=0.0, le=1.0)
    fresh_median_days_max: float = Field(default=7.0, ge=0.0)
    relevance_pass_rate_min: float = Field(default=0.70, ge=0.0, le=1.0)
    dup_ratio_max: float = Field(default=0.15, ge=0.0, le=1.0)
    spam_ratio_max: float = Field(default=0.10, ge=0.0, le=1.0)


class AnalysisMustResult(BaseModel):
    coverage_ok: bool
    freshness_ok: bool
    relevance_ok: bool
    dup_ok: bool
    spam_ok: bool
    safety_ok: bool

    def all_passed(self) -> bool:
        return (
            self.coverage_ok
            and self.freshness_ok
            and self.relevance_ok
            and self.dup_ok
            and self.spam_ok
            and self.safety_ok
        )


class TaskAnalysisMetrics(BaseModel):
    # 输入指标（0~1）
    coverage: float = Field(..., ge=0.0, le=1.0)
    relevance: float = Field(..., ge=0.0, le=1.0)
    evidence_per_insight_avg: float = Field(..., ge=0.0)
    median_days: float = Field(..., ge=0.0)
    dup_ratio: float = Field(..., ge=0.0, le=1.0)
    spam_ratio: float = Field(..., ge=0.0, le=1.0)
    diversity: float = Field(..., ge=0.0, le=1.0)
    safety_pass: bool = Field(default=True)


class AnalysisSummary(BaseModel):
    task_id: str
    a_score: int = Field(..., ge=0, le=100)
    must: AnalysisMustResult
    # 回显指标
    coverage: float = Field(..., ge=0.0, le=1.0)
    relevance: float = Field(..., ge=0.0, le=1.0)
    evidence_per_insight_avg: float = Field(..., ge=0.0)
    median_days: float = Field(..., ge=0.0)
    dup_ratio: float = Field(..., ge=0.0, le=1.0)
    spam_ratio: float = Field(..., ge=0.0, le=1.0)
    diversity: float = Field(..., ge=0.0, le=1.0)


class AnalysisListData(BaseModel):
    items: list[AnalysisSummary]
    total: int


class AnalysisListResponse(BaseModel):
    code: int = 0
    data: AnalysisListData
    trace_id: str | None = None
