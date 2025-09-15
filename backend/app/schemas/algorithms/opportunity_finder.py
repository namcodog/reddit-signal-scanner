"""
Opportunity Finder Pydantic Models

基于Context7最佳实践的类型安全模型，专为机会发现算法设计
使用TypeAdapter和validate_call实现完整的类型安全性
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional, Union

from pydantic import BaseModel, Field, TypeAdapter
from pydantic.dataclasses import dataclass as pydantic_dataclass

if TYPE_CHECKING:
    from ...models.signal_pattern import RedditPost, Signal


# 重新定义枚举以确保类型安全
class SignalTypePydantic(str, Enum):
    """信号类型枚举 - Pydantic版本"""

    PAIN_POINT = "pain_point"
    COMPETITOR = "competitor"
    OPPORTUNITY = "opportunity"


class SentimentTypePydantic(str, Enum):
    """情感类型枚举 - Pydantic版本"""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


@pydantic_dataclass
class SignalPatternPydantic:
    """统一信号模式数据结构 - Pydantic版本"""

    signal_type: SignalTypePydantic
    keywords: List[str] = Field(..., min_length=1, description="关键词列表，至少一个")
    sentiment_threshold: float = Field(
        ..., ge=-1.0, le=1.0, description="情感阈值 [-1.0, 1.0]"
    )
    context_rules: List[str] = Field(default_factory=list, description="上下文规则")
    confidence_weight: float = Field(default=1.0, ge=0.0, le=1.0, description="置信度权重")
    min_keyword_matches: int = Field(default=1, ge=1, description="最少关键词匹配数")


@pydantic_dataclass
class RedditPostPydantic:
    """Reddit帖子数据结构 - Pydantic版本"""

    id: str = Field(..., description="帖子ID")
    title: str = Field(..., description="帖子标题")
    content: str = Field(..., description="帖子内容")
    subreddit: str = Field(..., description="所属subreddit")
    score: int = Field(default=0, description="帖子得分")
    comment_count: int = Field(default=0, ge=0, description="评论数量")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")

    @property
    def full_text(self) -> str:
        """获取完整文本内容"""
        return f"{self.title} {self.content}".strip()

    @property
    def popularity_score(self) -> float:
        """简单的受欢迎度评分"""
        return self.score + (self.comment_count * 0.5)


@pydantic_dataclass
class SignalPydantic:
    """提取的信号数据结构 - Pydantic版本"""

    # 必需字段（无默认值）必须在前面
    signal_type: SignalTypePydantic = Field(..., description="信号类型")
    content: str = Field(..., description="原始Reddit文本内容")
    sentiment_score: float = Field(..., ge=-1.0, le=1.0, description="情感分数 [-1.0, 1.0]")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度 [0.0, 1.0]")

    # 可选字段（有默认值）必须在后面
    matched_keywords: List[str] = Field(default_factory=list, description="匹配的关键词")
    context_metadata: Dict[str, Union[str, int, float, Dict[str, float]]] = Field(
        default_factory=dict, description="上下文元数据"
    )
    extracted_at: datetime = Field(default_factory=datetime.utcnow, description="提取时间")
    source_post_id: Optional[str] = Field(default=None, description="源帖子ID")
    subreddit: Optional[str] = Field(default=None, description="所属subreddit")

    @property
    def is_high_confidence(self) -> bool:
        """是否为高置信度信号"""
        return self.confidence >= 0.7

    @property
    def sentiment_label(self) -> SentimentTypePydantic:
        """情感标签"""
        if self.sentiment_score <= -0.3:
            return SentimentTypePydantic.NEGATIVE
        elif self.sentiment_score >= 0.3:
            return SentimentTypePydantic.POSITIVE
        else:
            return SentimentTypePydantic.NEUTRAL


# 响应模型，替代Any类型返回值
class OpportunityFinderResponse(BaseModel):
    """机会发现算法响应模型"""

    opportunities: List[SignalPydantic] = Field(..., description="发现的机会信号列表")
    total_processed: int = Field(..., ge=0, description="处理的总帖子数")
    opportunities_found: int = Field(..., ge=0, description="找到的机会数量")
    processing_time_ms: float = Field(..., ge=0.0, description="处理时间(毫秒)")
    confidence_distribution: Dict[str, int] = Field(
        default_factory=dict, description="置信度分布统计"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "opportunities": [
                    {
                        "signal_type": "opportunity",
                        "content": "Looking for a better project management tool...",
                        "matched_keywords": ["project management", "tool"],
                        "sentiment_score": -0.5,
                        "confidence": 0.8,
                    }
                ],
                "total_processed": 100,
                "opportunities_found": 3,
                "processing_time_ms": 150.5,
                "confidence_distribution": {"high": 2, "medium": 1},
            }
        }
    }


class OpportunityAnalysisResponse(BaseModel):
    """机会分析响应模型"""

    opportunity: SignalPydantic = Field(..., description="机会信号详情")
    analysis: Dict[str, Union[str, float, List[str]]] = Field(
        default_factory=dict, description="详细分析结果"
    )
    market_potential: float = Field(..., ge=0.0, le=1.0, description="市场潜力评分")
    competition_level: float = Field(..., ge=0.0, le=1.0, description="竞争水平")
    urgency_score: float = Field(..., ge=0.0, le=1.0, description="紧急程度")
    recommended_actions: List[str] = Field(default_factory=list, description="推荐行动")


# TypeAdapter 用于类型安全的验证和序列化
SignalListAdapter = TypeAdapter(List[SignalPydantic])
RedditPostListAdapter = TypeAdapter(List[RedditPostPydantic])
SignalPatternListAdapter = TypeAdapter(List[SignalPatternPydantic])


# 适配器函数，用于与原始dataclass的转换
def signal_to_pydantic(original_signal: "Signal") -> SignalPydantic:
    """将原始Signal转换为Pydantic版本"""
    return SignalPydantic(
        signal_type=SignalTypePydantic(original_signal.signal_type.value),
        content=original_signal.content,
        matched_keywords=original_signal.matched_keywords,
        sentiment_score=original_signal.sentiment_score,
        confidence=original_signal.confidence,
        context_metadata=original_signal.context_metadata,
        extracted_at=original_signal.extracted_at,
        source_post_id=original_signal.source_post_id,
        subreddit=original_signal.subreddit,
    )


def signals_to_pydantic(original_signals: List["Signal"]) -> List[SignalPydantic]:
    """批量转换信号列表"""
    return [signal_to_pydantic(signal) for signal in original_signals]


def reddit_post_to_pydantic(original_post: "RedditPost") -> RedditPostPydantic:
    """将原始RedditPost转换为Pydantic版本"""
    return RedditPostPydantic(
        id=original_post.id,
        title=original_post.title,
        content=original_post.content,
        subreddit=original_post.subreddit,
        score=original_post.score,
        comment_count=original_post.comment_count,
        created_at=original_post.created_at,
    )
