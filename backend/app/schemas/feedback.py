"""
用户反馈埋点 Schemas

覆盖事件：
- analysis_rating（分析完成页的赞/踩）
- insight_flag（洞察标注：有用/不准/其他）
- metric（前端上报的轻量指标）

设计约束：
- 全量类型，禁止裸 Any
- 保持与后续 feedback_events 表结构兼容
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, model_validator

from ..core.types import JsonValue
from .common.responses import BaseResponse, ResponseStatus


class FeedbackSource(str, Enum):
    user = "user"
    admin = "admin"
    system = "system"


class FeedbackEventType(str, Enum):
    analysis_rating = "analysis_rating"
    insight_flag = "insight_flag"
    metric = "metric"
    community_decision = "community_decision"
    moderation_action = "moderation_action"


class RatingValue(str, Enum):
    like = "like"
    dislike = "dislike"


class InsightFlag(str, Enum):
    useful = "useful"
    inaccurate = "inaccurate"
    spam = "spam"
    other = "other"


class FeedbackEventRequest(BaseModel):
    """前台埋点统一请求体。

    根据 event_type 携带不同字段：
    - analysis_rating: rating, reason, comment
    - insight_flag: insight_id, flag, tags, comment
    - metric: metric_name, metric_value, metric_unit, context
    """

    source: FeedbackSource = Field(default=FeedbackSource.user, description="事件来源")
    event_type: FeedbackEventType = Field(..., description="事件类型")
    task_id: str = Field(..., description="任务ID")
    analysis_id: Optional[str] = Field(default=None, description="分析ID（可选）")
    user_id: Optional[str] = Field(default=None, description="用户ID（可选，后端可从JWT注入）")

    # analysis_rating
    rating: Optional[RatingValue] = Field(default=None, description="赞/踩")
    reason: Optional[str] = Field(default=None, description="原因（可选）")
    comment: Optional[str] = Field(default=None, description="备注（可选）")

    # insight_flag
    insight_id: Optional[str] = Field(default=None, description="洞察项ID")
    flag: Optional[InsightFlag] = Field(default=None, description="标注类型")
    tags: Optional[List[str]] = Field(default=None, description="附加标签列表")

    # metric
    metric_name: Optional[str] = Field(default=None, description="指标名")
    metric_value: Optional[float] = Field(default=None, description="指标值")
    metric_unit: Optional[str] = Field(default=None, description="指标单位")
    context: Optional[Dict[str, JsonValue]] = Field(
        default=None, description="上下文字段，键值均为JSON可序列化"
    )

    @model_validator(mode="after")
    def validate_by_event_type(self) -> "FeedbackEventRequest":
        et = self.event_type
        if et == FeedbackEventType.analysis_rating:
            if self.rating is None:
                raise ValueError("analysis_rating 事件必须提供 rating 字段")
        elif et == FeedbackEventType.insight_flag:
            if self.insight_id is None or self.flag is None:
                raise ValueError("insight_flag 事件必须提供 insight_id 与 flag")
        elif et == FeedbackEventType.metric:
            if self.metric_name is None or self.metric_value is None:
                raise ValueError("metric 事件必须提供 metric_name 与 metric_value")
        return self


class FeedbackEventSaved(BaseModel):
    event_id: str
    stored: bool
    stored_backend: str
    timestamp: datetime


class FeedbackEventResponse(BaseResponse):
    status: ResponseStatus = Field(default=ResponseStatus.SUCCESS)
    data: FeedbackEventSaved
