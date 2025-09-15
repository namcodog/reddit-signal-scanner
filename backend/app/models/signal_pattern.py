"""
信号模式数据结构 - Reddit商业信号提取核心模型

Linus式设计理念：
- 统一数据结构消除特殊情况
- 清晰的数据流：RedditPost → SignalPattern[] → Signal[]
- 配置驱动替代硬编码逻辑

Context7最佳实践：
- 使用Pydantic dataclass实现类型安全
- 保持原有API完全兼容
- 零破坏性变更设计
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from pydantic import Field, ValidationError

# Pydantic integration for type safety (project dependency)
from pydantic.dataclasses import dataclass as pyd_dataclass

PYDANTIC_AVAILABLE = True


class SignalType(Enum):
    """信号类型枚举"""

    PAIN_POINT = "pain_point"  # 痛点信号
    COMPETITOR = "competitor"  # 竞品信号
    OPPORTUNITY = "opportunity"  # 机会信号


class SentimentType(Enum):
    """情感类型枚举"""

    NEGATIVE = "negative"  # 负面情感（痛点）
    NEUTRAL = "neutral"  # 中性情感（竞品）
    POSITIVE = "positive"  # 正面情感（机会）


@pyd_dataclass(frozen=True)
class SignalPattern:
    """
    统一信号模式数据结构

    设计原则：
    - 通用性：适用于所有三种信号类型
    - 简洁性：最少必要字段
    - 可扩展：支持未来信号类型扩展
    """

    signal_type: SignalType
    keywords: List[str] = Field(..., min_length=1, description="关键词列表，至少包含一个关键词")
    sentiment_threshold: float = Field(
        ..., ge=-1.0, le=1.0, description="情感阈值 [-1.0, 1.0]"
    )
    context_rules: List[str] = Field(default_factory=list, description="上下文规则列表")
    confidence_weight: float = Field(
        default=1.0, ge=0.0, le=1.0, description="置信度权重 [0.0, 1.0]"
    )
    min_keyword_matches: int = Field(default=1, ge=1, description="最少关键词匹配数，至少为1")

    def __post_init__(self) -> None:
        """数据验证 - 保持向后兼容性"""
        if not PYDANTIC_AVAILABLE:
            # 如果没有Pydantic，使用原有验证逻辑
            if not -1.0 <= self.sentiment_threshold <= 1.0:
                raise ValueError(
                    f"sentiment_threshold must be in [-1.0, 1.0], got {self.sentiment_threshold}"
                )
            if not 0.0 <= self.confidence_weight <= 1.0:
                raise ValueError(
                    f"confidence_weight must be in [0.0, 1.0], got {self.confidence_weight}"
                )
            if self.min_keyword_matches < 1:
                raise ValueError(
                    f"min_keyword_matches must be >= 1, got {self.min_keyword_matches}"
                )


@pyd_dataclass
class Signal:
    """
    提取的信号数据结构

    统一表示所有类型的信号结果
    """

    signal_type: SignalType
    content: str = Field(..., description="原始Reddit文本内容")
    sentiment_score: float = Field(..., ge=-1.0, le=1.0, description="情感分数 [-1.0, 1.0]")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度 [0.0, 1.0]")
    matched_keywords: List[str] = Field(default_factory=list, description="匹配的关键词列表")
    context_metadata: Dict[str, Union[str, int, float, Dict[str, float]]] = Field(
        default_factory=dict, description="上下文元数据"
    )
    extracted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="信号提取时间"
    )
    source_post_id: Optional[str] = Field(default=None, description="源帖子ID")
    subreddit: Optional[str] = Field(default=None, description="所属subreddit")

    @property
    def is_high_confidence(self) -> bool:
        """是否为高置信度信号"""
        return self.confidence >= 0.7

    @property
    def sentiment_label(self) -> SentimentType:
        """情感标签"""
        if self.sentiment_score <= -0.3:
            return SentimentType.NEGATIVE
        elif self.sentiment_score >= 0.3:
            return SentimentType.POSITIVE
        else:
            return SentimentType.NEUTRAL


@pyd_dataclass
class RedditPost:
    """
    Reddit帖子数据结构（用于信号检测输入）

    最小必要字段，专注信号提取需求
    """

    id: str = Field(..., description="帖子唯一标识符")
    title: str = Field(..., description="帖子标题")
    content: str = Field(..., description="帖子内容文本")
    subreddit: str = Field(..., description="所属subreddit名称")
    score: int = Field(default=0, description="帖子得分/点赞数")
    comment_count: int = Field(default=0, ge=0, description="评论数量，非负整数")
    created_at: Optional[datetime] = Field(default=None, description="帖子创建时间")

    @property
    def full_text(self) -> str:
        """获取完整文本内容"""
        return f"{self.title} {self.content}".strip()

    @property
    def popularity_score(self) -> float:
        """简单的受欢迎度评分"""
        # 简化的评分算法：点赞数 + 评论数权重
        return self.score + (self.comment_count * 0.5)


# 预定义的信号模式（将从配置文件加载）
DEFAULT_SIGNAL_PATTERNS: List[SignalPattern] = [
    # 痛点信号模式
    SignalPattern(
        signal_type=SignalType.PAIN_POINT,
        keywords=["sucks", "terrible", "frustrating", "hate", "broken", "awful"],
        sentiment_threshold=-0.6,
        context_rules=["complaint", "negative_experience"],
        confidence_weight=0.9,
    ),
    # 竞品信号模式
    SignalPattern(
        signal_type=SignalType.COMPETITOR,
        keywords=["vs", "better than", "compared to", "alternative to", "similar to"],
        sentiment_threshold=0.0,  # 中性
        context_rules=["brand_mention", "comparison"],
        confidence_weight=0.8,
    ),
    # 机会信号模式
    SignalPattern(
        signal_type=SignalType.OPPORTUNITY,
        keywords=["wish there was", "if only", "missing", "need", "would pay for"],
        sentiment_threshold=0.3,
        context_rules=["unmet_need", "feature_request"],
        confidence_weight=0.85,
    ),
]
