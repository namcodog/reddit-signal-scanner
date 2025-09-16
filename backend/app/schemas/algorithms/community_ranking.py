"""
Community Ranking Algorithm Pydantic Models

基于Context7最佳实践的类型安全模型，替代Dict[str, Any]
支持向后兼容和渐进式迁移
"""

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union, cast

from pydantic import BaseModel, Field, ValidationInfo, computed_field, field_validator
from pydantic.dataclasses import dataclass as pydantic_dataclass

if TYPE_CHECKING:
    from ...algorithms.community_ranking import CommunityMetadata, RankingResult

logger = logging.getLogger(__name__)

# 定义严格的JSON值类型，替代Any
JsonValue = Union[str, int, float, bool, List[str], None]


class CommunityMetadataPydantic(BaseModel):
    """社区元数据结构 - Pydantic版本"""

    model_config = {
        "str_strip_whitespace": True,
        "validate_assignment": True,
        "extra": "forbid",  # 严格模式，不允许额外字段
    }

    # 基础标识信息
    id: str = Field(..., description="社区唯一标识符")
    name: str = Field(..., description="社区名称，如 r/ObsidianMD")
    display_name: str = Field(..., description="展示名称，如 'Obsidian MD Community'")
    description: str = Field(..., description="社区描述")

    # 分类信息
    category: str = Field(..., description="大分类: tech/business/lifestyle")
    tags: List[str] = Field(default_factory=list, description="细粒度标签")
    keywords: List[str] = Field(default_factory=list, description="关键词集合")

    # 质量指标 (核心竞争优势)
    member_count: int = Field(default=0, ge=0, description="成员数量")
    daily_posts_avg: float = Field(default=0.0, ge=0.0, description="日均帖子数")
    comment_quality_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="评论质量评分 0-1"
    )
    content_depth_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="内容深度评分 0-1"
    )
    business_relevance: float = Field(
        default=0.0, ge=0.0, le=1.0, description="商业相关性 0-1"
    )

    # 算法优化
    description_vector: Optional[List[float]] = Field(None, description="预计算的描述向量")

    # 扩展性 - 严格类型约束的自定义元数据
    custom_metadata: Dict[str, JsonValue] = Field(
        default_factory=dict, description="支持未来扩展的元数据，严格类型约束"
    )

    @field_validator("tags", "keywords")
    @classmethod
    def validate_string_lists(cls, v: List[str]) -> List[str]:
        """验证字符串列表非空且去重"""
        if not isinstance(v, list):
            raise ValueError("必须是字符串列表")
        # 去重并过滤空字符串
        return list(dict.fromkeys(tag.strip() for tag in v if tag.strip()))

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        """验证分类有效性"""
        valid_categories = {"tech", "business", "lifestyle", "other"}
        if v.lower() not in valid_categories:
            logger.warning(f"未知分类: {v}, 将设为 'other'")
            return "other"
        return v.lower()

    def to_dict(
        self,
    ) -> Dict[str, Union[str, int, float, List[str], Dict[str, JsonValue], None]]:
        """向后兼容的字典转换方法，返回具体类型"""
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category,
            "tags": self.tags,
            "keywords": self.keywords,
            "member_count": self.member_count,
            "daily_posts_avg": self.daily_posts_avg,
            "comment_quality_score": self.comment_quality_score,
            "content_depth_score": self.content_depth_score,
            "business_relevance": self.business_relevance,
            "custom_metadata": self.custom_metadata,
        }


class RankingConfigPydantic(BaseModel):
    """评分配置 - Pydantic版本"""

    model_config = {"validate_assignment": True, "extra": "forbid"}

    # 权重配置 (总和应为1.0)
    similarity_weight: float = Field(
        default=0.4, ge=0.0, le=1.0, description="相似度权重 40%"
    )
    activity_weight: float = Field(default=0.3, ge=0.0, le=1.0, description="活跃度权重 30%")
    quality_weight: float = Field(default=0.3, ge=0.0, le=1.0, description="质量权重 30%")

    # 活跃度评分参数
    max_daily_posts_for_scale: float = Field(
        default=50.0, gt=0.0, description="用于对数缩放的基准值"
    )

    # 质量评分子权重
    comment_quality_weight: float = Field(
        default=0.4, ge=0.0, le=1.0, description="评论质量子权重"
    )
    content_depth_weight: float = Field(
        default=0.3, ge=0.0, le=1.0, description="内容深度子权重"
    )
    business_relevance_weight: float = Field(
        default=0.3, ge=0.0, le=1.0, description="商业相关性子权重"
    )

    # 多样性控制
    max_per_category: int = Field(default=5, ge=1, description="每个类别最多推荐数量")
    category_bonus: float = Field(default=0.1, ge=0.0, le=0.5, description="类别多样性奖励")

    # 分数阈值
    min_relevance_threshold: float = Field(
        default=0.1, ge=0.0, le=1.0, description="最低相关性阈值"
    )
    quality_bonus_threshold: float = Field(
        default=0.8, ge=0.0, le=1.0, description="高质量社区额外加分阈值"
    )

    @field_validator("similarity_weight", "activity_weight", "quality_weight")
    @classmethod
    def validate_weights(cls, v: float, info: ValidationInfo) -> float:
        """验证权重合理性"""
        if not (0.0 <= v <= 1.0):
            raise ValueError("权重必须在0.0-1.0之间")
        return v

    def get_total_main_weight(self) -> float:
        """计算主要权重总和"""
        return self.similarity_weight + self.activity_weight + self.quality_weight

    def get_total_quality_weight(self) -> float:
        """计算质量子权重总和"""
        return (
            self.comment_quality_weight
            + self.content_depth_weight
            + self.business_relevance_weight
        )

    def is_valid(self) -> bool:
        """验证配置有效性"""
        main_weight_valid = abs(self.get_total_main_weight() - 1.0) <= 0.01
        quality_weight_valid = abs(self.get_total_quality_weight() - 1.0) <= 0.01
        return main_weight_valid and quality_weight_valid


class RankingResultPydantic(BaseModel):
    """评分结果 - Pydantic版本"""

    model_config = {"validate_assignment": True, "extra": "forbid"}

    community: CommunityMetadataPydantic = Field(..., description="社区元数据")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="原始相似度分数")
    activity_score: float = Field(..., ge=0.0, le=1.0, description="活跃度分数")
    quality_score: float = Field(..., ge=0.0, le=1.0, description="质量分数")
    final_score: float = Field(..., ge=0.0, description="最终综合分数")
    diversity_bonus: float = Field(default=0.0, ge=0.0, description="多样性奖励分数")

    def get_score_breakdown(self) -> Dict[str, float]:
        """获取分数详细构成"""
        return {
            "similarity": self.similarity_score,
            "activity": self.activity_score,
            "quality": self.quality_score,
            "diversity_bonus": self.diversity_bonus,
            "final": self.final_score,
        }


# 响应模型，替代Dict[str, Any]返回值
class PerformanceStatsResponse(BaseModel):
    """性能统计响应模型"""

    total_communities_processed: int = Field(..., ge=0, description="处理的社区总数")
    average_score: float = Field(..., ge=0.0, description="平均分数")
    processing_time_ms: float = Field(..., ge=0.0, description="处理时间(毫秒)")
    diversity_applied: bool = Field(..., description="是否应用了多样性控制")
    score_distribution: Dict[str, int] = Field(
        default_factory=dict, description="分数分布统计"
    )


class ScoreExplanationResponse(BaseModel):
    """分数解释响应模型"""

    community_id: str = Field(..., description="社区ID")
    community_name: str = Field(..., description="社区名称")
    final_score: float = Field(..., ge=0.0, description="最终分数")

    # 分数组成
    similarity_component: float = Field(..., ge=0.0, description="相似度组件分数")
    activity_component: float = Field(..., ge=0.0, description="活跃度组件分数")
    quality_component: float = Field(..., ge=0.0, description="质量组件分数")
    diversity_bonus: float = Field(default=0.0, ge=0.0, description="多样性奖励")

    # 解释文本
    interpretation: str = Field(..., description="分数解释文本")
    strengths: List[str] = Field(default_factory=list, description="优势列表")
    improvement_areas: List[str] = Field(default_factory=list, description="改进建议")


class AlgorithmMetadataResponse(BaseModel):
    """算法元数据响应模型"""

    algorithm_name: str = Field(default="CommunityRanking", description="算法名称")
    version: str = Field(default="2.0", description="算法版本")
    description: str = Field(..., description="算法描述")

    # 配置信息
    current_config: RankingConfigPydantic = Field(..., description="当前配置")

    # 性能指标
    supported_features: List[str] = Field(default_factory=list, description="支持功能列表")
    performance_metrics: Dict[str, float] = Field(
        default_factory=dict, description="性能指标"
    )

    # 技术信息
    model_type: str = Field(default="weighted_similarity", description="模型类型")
    last_updated: Optional[str] = Field(None, description="最后更新时间")


# 适配器函数，用于dataclass与Pydantic之间的转换
def community_metadata_from_dataclass(
    dc_instance: "CommunityMetadata",
) -> CommunityMetadataPydantic:
    """从dataclass实例创建Pydantic实例"""
    return CommunityMetadataPydantic(
        id=dc_instance.id,
        name=dc_instance.name,
        display_name=dc_instance.display_name,
        description=dc_instance.description,
        category=dc_instance.category,
        tags=dc_instance.tags,
        keywords=dc_instance.keywords,
        member_count=dc_instance.member_count,
        daily_posts_avg=dc_instance.daily_posts_avg,
        comment_quality_score=dc_instance.comment_quality_score,
        content_depth_score=dc_instance.content_depth_score,
        business_relevance=dc_instance.business_relevance,
        description_vector=dc_instance.description_vector,
        # 类型收敛：dataclass 使用递归 JsonValue，这里收敛到 schema 的严格 JsonValue
        custom_metadata=cast(Dict[str, JsonValue], dc_instance.custom_metadata),
    )


def ranking_result_from_dataclass(
    dc_instance: "RankingResult", community_pydantic: CommunityMetadataPydantic
) -> RankingResultPydantic:
    """从dataclass实例创建RankingResult Pydantic实例"""
    return RankingResultPydantic(
        community=community_pydantic,
        similarity_score=dc_instance.similarity_score,
        activity_score=dc_instance.activity_score,
        quality_score=dc_instance.quality_score,
        final_score=dc_instance.final_score,
        diversity_bonus=dc_instance.diversity_bonus,
    )
