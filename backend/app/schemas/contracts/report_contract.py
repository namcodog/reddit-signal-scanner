from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Literal

from pydantic import BaseModel, Field

from ...core.types import JsonValue


class ReportFormat(str, Enum):
    FULL = "full"
    SUMMARY = "summary"
    INSIGHTS = "insights"


class InsightItem(BaseModel):
    title: str
    content: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_count: int = Field(ge=0)
    tags: List[str] = Field(default_factory=list)


class ExecutiveSummary(BaseModel):
    headline: Optional[str] = Field(default=None)
    total_communities: int = Field(default=0, ge=0)
    key_insights: int = Field(default=0, ge=0)
    top_opportunity: Optional[str] = Field(default=None)
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    summary_points: List[str] = Field(default_factory=list)


class MarketMetrics(BaseModel):
    total_mentions: int = Field(default=0, ge=0)
    sentiment_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    top_communities: List[str] = Field(default_factory=list)
    trending_keywords: List[str] = Field(default_factory=list)
    engagement_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    sample_size: Optional[int] = Field(default=None, ge=0)


class PainPointExample(BaseModel):
    post_id: str
    community: Optional[str] = Field(default=None)
    permalink: Optional[str] = Field(default=None)
    content_snippet: Optional[str] = Field(default=None)
    upvotes: Optional[int] = Field(default=None, ge=0)


class PainPointInsight(BaseModel):
    description: str = Field(..., min_length=1)
    sentiment_score: float = Field(..., ge=-1.0, le=1.0)
    frequency: int = Field(..., ge=0)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    severity: Optional[Literal["low", "medium", "high"]] = Field(default=None)
    categories: List[str] = Field(default_factory=list)
    example_posts: List[PainPointExample] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class CompetitorInsight(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = Field(default=None)
    market_position: Optional[Literal["leader", "challenger", "follower", "niche"]] = Field(default=None)
    mention_count: int = Field(default=0, ge=0)
    sentiment_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    market_share_estimate: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class OpportunityInsight(BaseModel):
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    potential: Literal["low", "medium", "high"] = Field(default="medium")
    difficulty: Literal["easy", "medium", "hard"] = Field(default="medium")
    market_size: Optional[str] = Field(default=None)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    timeframe: Optional[str] = Field(default=None)
    key_insights: List[str] = Field(default_factory=list)





class ReportData(BaseModel):
    """标准化报告数据结构（与现有SignalReport兼容的超集）。"""

    # 基本元数据
    task_id: str
    query: str
    total_posts: int = Field(ge=0)
    total_comments: int = Field(ge=0)
    analysis_duration: float = Field(ge=0)
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    # 核心洞察
    key_insights: List[InsightItem] = Field(default_factory=list)
    sentiment_summary: Dict[str, float] = Field(default_factory=dict)
    trending_topics: List[str] = Field(default_factory=list)
    user_personas: List[Dict[str, JsonValue]] = Field(default_factory=list)

    # 其他
    generated_at: str
    data_freshness: str
    html_content: Optional[str] = None
    data_coverage: Optional[Dict[str, JsonValue]] = None

    # 结构化洞察
    executive_summary: ExecutiveSummary = Field(default_factory=ExecutiveSummary)
    market_metrics: MarketMetrics = Field(default_factory=MarketMetrics)
    pain_points: List[PainPointInsight] = Field(default_factory=list)
    competitors: List[CompetitorInsight] = Field(default_factory=list)
    opportunities: List[OpportunityInsight] = Field(default_factory=list)

    class Config:
        # 兼容服务端额外字段（如 data_coverage 等），避免解析失败
        extra = "ignore"
