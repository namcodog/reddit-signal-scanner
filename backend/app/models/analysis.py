"""
分析结果数据模型

基于 Linus 原则：数据结构决定代码复杂度
- SQLAlchemy ORM模型：映射analyses表
- Pydantic Schema：API输入输出验证
- JSONB字段类型安全：防止运行时错误
- 一对一关系：每个任务对应唯一分析结果
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Union
from uuid import UUID

from sqlalchemy import Column, DateTime, Integer, Numeric, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID, JSONB
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func
from pydantic import BaseModel, Field, validator, model_validator

from .base import Base


# ===== SQLAlchemy ORM 模型 =====


class Analysis(Base):
    """分析结果ORM模型 - 映射analyses表"""

    __tablename__ = "analyses"

    # 主键和外键
    id = Column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    task_id = Column(
        PostgresUUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # JSONB存储字段
    insights = Column(JSONB, nullable=False)
    sources = Column(JSONB, nullable=False)

    # 元数据字段
    confidence_score = Column(Numeric(3, 2), nullable=False)
    analysis_version = Column(Integer, nullable=False, default=1)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # 关系映射
    task = relationship("Task", back_populates="analysis")
    reports = relationship(
        "Report", back_populates="analysis", cascade="all, delete-orphan"
    )

    # 表级约束
    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0.00 AND confidence_score <= 1.00",
            name="ck_analyses_confidence_range",
        ),
        CheckConstraint("analysis_version > 0", name="ck_analyses_version_positive"),
        CheckConstraint(
            "validate_insights_schema(insights)", name="ck_analyses_insights_schema"
        ),
        CheckConstraint(
            "validate_sources_schema(sources)", name="ck_analyses_sources_schema"
        ),
    )

    def __repr__(self) -> str:
        return f"<Analysis(id={self.id}, task_id={self.task_id}, confidence={self.confidence_score})>"

    @validates("confidence_score")
    def validate_confidence_score(self, key, confidence_score):
        """验证置信度范围"""
        del key  # 标记key参数为已使用，避免Pylance警告
        if not (0.0 <= float(confidence_score) <= 1.0):
            raise ValueError(f"置信度必须在0.00-1.00之间，得到: {confidence_score}")
        return confidence_score

    @validates("analysis_version")
    def validate_analysis_version(self, key, version):
        """验证分析版本"""
        del key  # 标记key参数为已使用，避免Pylance警告
        if version <= 0:
            raise ValueError(f"分析版本必须为正数，得到: {version}")
        return version

    @property
    def confidence_percentage(self) -> float:
        """置信度百分比显示"""
        return float(self.confidence_score) * 100

    @property
    def insights_summary(self) -> Dict[str, int]:
        """洞察摘要统计"""
        if not self.insights:
            return {"pain_points": 0, "competitors": 0, "opportunities": 0}

        return {
            "pain_points": len(self.insights.get("pain_points", [])),
            "competitors": len(self.insights.get("competitors", [])),
            "opportunities": len(self.insights.get("opportunities", [])),
        }

    @property
    def data_coverage(self) -> Dict[str, Union[int, float]]:
        """数据覆盖统计"""
        if not self.sources:
            return {"posts_analyzed": 0, "communities": 0, "cache_hit_rate": 0.0}

        return {
            "posts_analyzed": self.sources.get("posts_analyzed", 0),
            "communities": len(self.sources.get("communities", [])),
            "cache_hit_rate": self.sources.get("cache_hit_rate", 0.0),
        }


# ===== Pydantic Schema 模型 =====


class PainPoint(BaseModel):
    """痛点结构模型"""

    description: str = Field(..., min_length=1, max_length=500, description="痛点描述")
    sentiment_score: float = Field(..., ge=0.0, le=1.0, description="情感分数 0.0-1.0")
    frequency: int = Field(..., ge=1, description="出现频次")
    evidence_posts: List[str] = Field(
        default_factory=list, max_items=10, description="证据帖子ID"
    )
    categories: List[str] = Field(
        default_factory=list, max_items=5, description="痛点分类标签"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "description": "找不到靠谱的Reddit营销工具",
                "sentiment_score": 0.75,
                "frequency": 23,
                "evidence_posts": ["post_123", "post_456"],
                "categories": ["工具缺失", "营销困难"],
            }
        }


class Competitor(BaseModel):
    """竞争对手结构模型"""

    name: str = Field(..., min_length=1, max_length=100, description="竞争对手名称")
    mention_count: int = Field(..., ge=0, description="提及次数")
    sentiment_score: float = Field(..., ge=0.0, le=1.0, description="用户情感倾向")
    strengths: List[str] = Field(
        default_factory=list, max_items=10, description="优势列表"
    )
    weaknesses: List[str] = Field(
        default_factory=list, max_items=10, description="劣势列表"
    )
    price_mentions: List[str] = Field(default_factory=list, description="价格相关提及")
    market_position: str = Field(
        "unknown",
        description="市场定位",
        pattern=r"^(leader|challenger|niche|unknown)$",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Hootsuite",
                "mention_count": 45,
                "sentiment_score": 0.65,
                "strengths": ["功能全面", "界面友好"],
                "weaknesses": ["价格昂贵", "学习成本高"],
                "price_mentions": ["$99/month", "too expensive"],
                "market_position": "leader",
            }
        }


class Opportunity(BaseModel):
    """商业机会结构模型"""

    title: str = Field(..., min_length=1, max_length=200, description="机会标题")
    description: str = Field(..., min_length=1, max_length=1000, description="详细描述")
    market_size_indicator: str = Field(
        ..., description="市场规模指标", pattern=r"^(small|medium|large|huge)$"
    )
    urgency_score: float = Field(..., ge=0.0, le=1.0, description="紧迫性分数")
    feasibility_score: float = Field(..., ge=0.0, le=1.0, description="可行性分数")
    target_communities: List[str] = Field(
        default_factory=list, max_items=10, description="目标社区"
    )
    related_keywords: List[str] = Field(
        default_factory=list, max_items=20, description="相关关键词"
    )
    estimated_demand: int = Field(ge=0, description="需求量估算")

    @validator("urgency_score", "feasibility_score")
    def validate_scores(cls, v):
        if not (0.0 <= v <= 1.0):
            raise ValueError("分数必须在0.0-1.0之间")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Reddit内容自动化工具",
                "description": "自动化Reddit内容发布和互动管理工具，解决人工管理效率低下问题",
                "market_size_indicator": "large",
                "urgency_score": 0.85,
                "feasibility_score": 0.70,
                "target_communities": ["r/entrepreneur", "r/marketing"],
                "related_keywords": ["automation", "reddit bot", "content management"],
                "estimated_demand": 2500,
            }
        }


class InsightsSchema(BaseModel):
    """洞察结果Schema - 对应insights JSONB字段"""

    pain_points: List[PainPoint] = Field(
        default_factory=list, max_items=50, description="痛点列表"
    )
    competitors: List[Competitor] = Field(
        default_factory=list, max_items=30, description="竞争对手列表"
    )
    opportunities: List[Opportunity] = Field(
        default_factory=list, max_items=20, description="商业机会列表"
    )

    # 聚合统计
    analysis_summary: Dict[str, Any] = Field(
        default_factory=dict, description="分析摘要"
    )
    key_insights: List[str] = Field(
        default_factory=list, max_items=10, description="关键洞察"
    )

    @model_validator(mode="after")
    def validate_non_empty_insights(self):
        """确保至少有一种类型的洞察"""
        pain_points = self.pain_points
        competitors = self.competitors
        opportunities = self.opportunities

        if not pain_points and not competitors and not opportunities:
            raise ValueError("至少需要包含一种类型的分析洞察")

        return self

    @property
    def total_insights(self) -> int:
        """洞察总数"""
        return len(self.pain_points) + len(self.competitors) + len(self.opportunities)

    class Config:
        json_schema_extra = {
            "example": {
                "pain_points": [
                    {
                        "description": "Reddit营销工具功能不够强大",
                        "sentiment_score": 0.75,
                        "frequency": 23,
                        "evidence_posts": ["abc123"],
                        "categories": ["功能缺陷"],
                    }
                ],
                "competitors": [
                    {
                        "name": "Hootsuite",
                        "mention_count": 45,
                        "sentiment_score": 0.65,
                        "strengths": ["功能全面"],
                        "weaknesses": ["价格昂贵"],
                        "market_position": "leader",
                    }
                ],
                "opportunities": [
                    {
                        "title": "Reddit自动化工具",
                        "description": "解决手动管理效率问题",
                        "market_size_indicator": "large",
                        "urgency_score": 0.85,
                        "feasibility_score": 0.70,
                        "estimated_demand": 2500,
                    }
                ],
            }
        }


class SourcesSchema(BaseModel):
    """数据来源Schema - 对应sources JSONB字段"""

    # 数据来源信息
    communities: List[str] = Field(
        ..., min_items=1, max_items=50, description="分析的社区列表"
    )
    posts_analyzed: int = Field(..., ge=1, description="分析的帖子总数")
    comments_analyzed: int = Field(default=0, ge=0, description="分析的评论总数")
    time_range_days: int = Field(..., ge=1, le=365, description="时间范围（天数）")

    # 性能和缓存信息
    cache_hit_rate: float = Field(..., ge=0.0, le=1.0, description="缓存命中率")
    analysis_duration_seconds: float = Field(..., ge=0.0, description="分析耗时（秒）")
    reddit_api_calls: int = Field(..., ge=0, description="Reddit API调用次数")

    # 数据质量指标
    data_quality_score: float = Field(
        default=1.0, ge=0.0, le=1.0, description="数据质量分数"
    )
    filtered_spam_posts: int = Field(default=0, ge=0, description="过滤的垃圾帖子数")
    language_distribution: Dict[str, int] = Field(
        default_factory=dict, description="语言分布"
    )

    # 算法版本和配置
    algorithm_version: str = Field(..., description="使用的算法版本")
    processing_parameters: Dict[str, Any] = Field(
        default_factory=dict, description="处理参数配置"
    )

    @validator("cache_hit_rate", "data_quality_score")
    def validate_rate_scores(cls, v):
        if not (0.0 <= v <= 1.0):
            raise ValueError("比率和分数必须在0.0-1.0之间")
        return v

    @validator("communities")
    def validate_communities_format(cls, v):
        """验证社区名称格式"""
        for community in v:
            if not community.startswith("r/"):
                raise ValueError(f"社区名称必须以r/开头: {community}")
            if len(community) < 3:
                raise ValueError(f"社区名称太短: {community}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "communities": ["r/entrepreneur", "r/marketing", "r/startups"],
                "posts_analyzed": 1250,
                "comments_analyzed": 8450,
                "time_range_days": 30,
                "cache_hit_rate": 0.75,
                "analysis_duration_seconds": 45.6,
                "reddit_api_calls": 125,
                "data_quality_score": 0.92,
                "filtered_spam_posts": 23,
                "language_distribution": {"en": 1200, "es": 50},
                "algorithm_version": "v2.1.0",
                "processing_parameters": {
                    "min_score_threshold": 5,
                    "sentiment_model": "vader",
                    "clustering_method": "kmeans",
                },
            }
        }


# ===== API Schema模型 =====


class AnalysisCreateRequest(BaseModel):
    """创建分析请求模型"""

    task_id: UUID = Field(..., description="关联任务ID")
    insights: InsightsSchema = Field(..., description="分析洞察结果")
    sources: SourcesSchema = Field(..., description="数据来源信息")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="置信度分数")
    analysis_version: int = Field(default=1, ge=1, description="分析版本号")


class AnalysisResponse(BaseModel):
    """分析结果响应模型"""

    id: UUID = Field(..., description="分析结果ID")
    task_id: UUID = Field(..., description="关联任务ID")
    insights: InsightsSchema = Field(..., description="分析洞察结果")
    sources: SourcesSchema = Field(..., description="数据来源信息")
    confidence_score: float = Field(..., description="置信度分数")
    confidence_percentage: float = Field(..., description="置信度百分比")
    analysis_version: int = Field(..., description="分析版本号")
    created_at: datetime = Field(..., description="创建时间")

    # 统计信息
    insights_summary: Dict[str, int] = Field(..., description="洞察摘要统计")
    data_coverage: Dict[str, Union[int, float]] = Field(..., description="数据覆盖统计")

    class Config:
        from_attributes = True
        json_encoders = {UUID: str, datetime: lambda v: v.isoformat(), Decimal: float}


class AnalysisListResponse(BaseModel):
    """分析结果列表响应模型"""

    analyses: List[AnalysisResponse] = Field(..., description="分析结果列表")
    total: int = Field(..., description="总数量")
    page: int = Field(default=1, ge=1, description="当前页码")
    size: int = Field(default=20, ge=1, le=100, description="每页数量")

    @property
    def has_next(self) -> bool:
        """是否有下一页"""
        return self.page * self.size < self.total

    @property
    def has_prev(self) -> bool:
        """是否有上一页"""
        return self.page > 1


class AnalysisStatsResponse(BaseModel):
    """分析统计响应模型"""

    total_analyses: int = Field(..., description="分析总数")
    avg_confidence: float = Field(..., description="平均置信度")
    confidence_distribution: Dict[str, int] = Field(..., description="置信度分布")
    top_communities: List[Dict[str, Union[str, int]]] = Field(
        ..., description="热门社区"
    )
    recent_analyses: int = Field(..., description="最近7天分析数")

    class Config:
        json_schema_extra = {
            "example": {
                "total_analyses": 1250,
                "avg_confidence": 0.78,
                "confidence_distribution": {
                    "高 (0.8-1.0)": 450,
                    "中 (0.5-0.8)": 650,
                    "低 (0.0-0.5)": 150,
                },
                "top_communities": [
                    {"community": "r/entrepreneur", "count": 125},
                    {"community": "r/marketing", "count": 98},
                ],
                "recent_analyses": 47,
            }
        }


# ===== 工具函数 =====


def create_analysis_from_dict(data: Dict[str, Any]) -> Analysis:
    """从字典创建分析对象"""
    return Analysis(
        task_id=data["task_id"],
        insights=data["insights"],
        sources=data["sources"],
        confidence_score=data["confidence_score"],
        analysis_version=data.get("analysis_version", 1),
    )


def validate_analysis_data(insights: Dict[str, Any], sources: Dict[str, Any]) -> bool:
    """验证分析数据有效性"""
    try:
        InsightsSchema(**insights)
        SourcesSchema(**sources)
        return True
    except Exception:
        return False


def calculate_insights_quality_score(insights: InsightsSchema) -> float:
    """计算洞察质量分数"""
    # 基于洞察数量和多样性计算质量分数
    pain_points_count = len(insights.pain_points)
    competitors_count = len(insights.competitors)
    opportunities_count = len(insights.opportunities)

    # 多样性权重
    diversity_score = (
        min(
            1.0,
            (pain_points_count > 0)
            + (competitors_count > 0)
            + (opportunities_count > 0),
        )
        / 3
    )

    # 数量权重（有上限，避免数量膨胀）
    quantity_score = min(
        1.0, (pain_points_count + competitors_count + opportunities_count) / 30
    )

    # 综合评分
    return diversity_score * 0.6 + quantity_score * 0.4
