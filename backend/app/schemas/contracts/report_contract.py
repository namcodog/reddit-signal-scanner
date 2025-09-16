from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

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


class ReportData(BaseModel):
    """标准化报告数据结构（与现有SignalReport兼容的超集）。"""

    # 基本元数据
    task_id: str
    query: str
    total_posts: int = Field(ge=0)
    total_comments: int = Field(ge=0)
    analysis_duration: float = Field(ge=0)

    # 核心洞察
    key_insights: List[InsightItem] = Field(default_factory=list)
    sentiment_summary: Dict[str, float] = Field(default_factory=dict)
    trending_topics: List[str] = Field(default_factory=list)
    user_personas: List[Dict[str, JsonValue]] = Field(default_factory=list)

    # 其他
    generated_at: str
    data_freshness: str

    # 允许存在而不强制的字段（为兼容服务侧临时字段）
    html_content: Optional[str] = None

    class Config:
        # 兼容服务端额外字段（如 data_coverage 等），避免解析失败
        extra = "ignore"
