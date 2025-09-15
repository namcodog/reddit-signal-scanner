"""
多维度社区评分和排序系统 - 智能社区发现核心组件
基于相似度、活跃度、质量的综合评分算法，保证推荐结果的准确性和多样性
"""

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union, cast, overload

import numpy as np

from ..core.types import JsonValue

# Pydantic integration for type-safe responses
try:
    from ..schemas.algorithms.community_ranking import (
        AlgorithmMetadataResponse,
        CommunityMetadataPydantic,
        PerformanceStatsResponse,
        RankingConfigPydantic,
        RankingResultPydantic,
        ScoreExplanationResponse,
        community_metadata_from_dataclass,
        ranking_result_from_dataclass,
    )

    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class CommunityMetadata:
    """社区元数据结构"""

    id: str
    name: str  # r/ObsidianMD
    display_name: str  # "Obsidian MD Community"
    description: str  # 社区描述
    category: str  # 大分类: tech/business/lifestyle
    tags: List[str] = field(default_factory=list)  # 细粒度标签
    keywords: List[str] = field(default_factory=list)  # 关键词集合

    # 质量指标 (核心竞争优势)
    member_count: int = 0
    daily_posts_avg: float = 0.0  # 日均帖子数
    comment_quality_score: float = 0.0  # 评论质量评分 0-1
    content_depth_score: float = 0.0  # 内容深度评分 0-1
    business_relevance: float = 0.0  # 商业相关性 0-1

    # 算法优化
    description_vector: Optional[List[float]] = None  # 预计算的描述向量

    # 扩展性
    custom_metadata: dict[str, JsonValue] = field(default_factory=dict)  # 支持未来扩展

    def to_dict(self) -> dict[str, JsonValue]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category,
            "tags": cast(List[JsonValue], list(self.tags)),
            "keywords": cast(List[JsonValue], list(self.keywords)),
            "member_count": self.member_count,
            "daily_posts_avg": self.daily_posts_avg,
            "comment_quality_score": self.comment_quality_score,
            "content_depth_score": self.content_depth_score,
            "business_relevance": self.business_relevance,
            "custom_metadata": self.custom_metadata,
        }


@dataclass
class RankingConfig:
    """评分配置"""

    # 权重配置 (总和应为1.0)
    similarity_weight: float = 0.4  # 相似度权重 40%
    activity_weight: float = 0.3  # 活跃度权重 30%
    quality_weight: float = 0.3  # 质量权重 30%

    # 活跃度评分参数
    max_daily_posts_for_scale: float = 50.0  # 用于对数缩放的基准值

    # 质量评分子权重
    comment_quality_weight: float = 0.4  # 评论质量子权重
    content_depth_weight: float = 0.3  # 内容深度子权重
    business_relevance_weight: float = 0.3  # 商业相关性子权重

    # 多样性控制
    max_per_category: int = 5  # 每个类别最多推荐数量
    category_bonus: float = 0.1  # 类别多样性奖励

    # 分数阈值
    min_relevance_threshold: float = 0.1  # 最低相关性阈值
    quality_bonus_threshold: float = 0.8  # 高质量社区额外加分阈值

    def validate(self) -> bool:
        """验证配置有效性"""
        total_weight = (
            self.similarity_weight + self.activity_weight + self.quality_weight
        )

        if abs(total_weight - 1.0) > 0.01:
            logger.warning(f"权重总和不为1.0: {total_weight}")
            return False

        total_quality_weight = (
            self.comment_quality_weight
            + self.content_depth_weight
            + self.business_relevance_weight
        )

        if abs(total_quality_weight - 1.0) > 0.01:
            logger.warning(f"质量评分子权重总和不为1.0: {total_quality_weight}")
            return False

        return True


@dataclass
class RankingResult:
    """评分结果"""

    community: CommunityMetadata
    similarity_score: float  # 原始相似度分数
    activity_score: float  # 活跃度分数
    quality_score: float  # 质量分数
    final_score: float  # 最终综合分数
    diversity_bonus: float = 0.0  # 多样性奖励分数

    def get_score_breakdown(self) -> Dict[str, float]:
        """获取分数详细构成"""
        return {
            "similarity": self.similarity_score,
            "activity": self.activity_score,
            "quality": self.quality_score,
            "diversity_bonus": self.diversity_bonus,
            "final": self.final_score,
        }


class CategoryCounter:
    """类别计数器，用于多样性控制"""

    def __init__(self, max_per_category: int = 5) -> None:
        self.max_per_category = max_per_category
        self.category_counts: Dict[str, int] = {}

    def can_add_category(self, category: str) -> bool:
        """检查是否可以添加该类别的社区"""
        current_count = self.category_counts.get(category, 0)
        return current_count < self.max_per_category

    def add_category(self, category: str) -> None:
        """添加类别计数"""
        self.category_counts[category] = self.category_counts.get(category, 0) + 1

    def get_category_count(self, category: str) -> int:
        """获取类别当前计数"""
        return self.category_counts.get(category, 0)

    def reset(self) -> None:
        """重置计数器"""
        self.category_counts.clear()


class CommunityRanking:
    """
    多维度社区评分和排序系统

    核心功能：
    1. 相似度、活跃度、质量的多维度综合评分
    2. 活跃度对数缩放，避免大社区偏差
    3. 质量综合评分 (评论质量 + 内容深度 + 商业相关性)
    4. 结果多样性保证，避免同类社区扎堆
    5. 可配置的评分权重和阈值
    """

    def __init__(self, config: Optional[RankingConfig] = None) -> None:
        """
        初始化评分系统

        Args:
            config: 评分配置，为None时使用默认配置
        """
        self.config = config or RankingConfig()

        # 验证配置有效性
        if not self.config.validate():
            raise ValueError("评分配置无效")

        # 初始化类别计数器
        self.category_counter = CategoryCounter(self.config.max_per_category)

        # 性能统计
        self.stats = {
            "total_evaluations": 0,
            "avg_final_score": 0.0,
            "diversity_applied": 0,
        }

        logger.info(
            f"CommunityRanking初始化完成: "
            f"权重 sim={self.config.similarity_weight}, "
            f"act={self.config.activity_weight}, "
            f"qual={self.config.quality_weight}"
        )

    def rank_communities(
        self,
        communities: List[CommunityMetadata],
        similarities: List[float],
        apply_diversity: bool = True,
    ) -> List[RankingResult]:
        """
        对社区进行多维度评分和排序

        Args:
            communities: 社区元数据列表
            similarities: 对应的相似度分数列表
            apply_diversity: 是否应用多样性控制

        Returns:
            List[RankingResult]: 排序后的评分结果列表
        """
        if len(communities) != len(similarities):
            raise ValueError("社区数量和相似度分数数量不匹配")

        if not communities:
            return []

        # 重置类别计数器
        self.category_counter.reset()

        # 计算每个社区的综合评分
        ranking_results = []
        for community, similarity in zip(communities, similarities):
            # 跳过相似度过低的社区
            if similarity < self.config.min_relevance_threshold:
                continue

            result = self._calculate_community_score(community, similarity)
            ranking_results.append(result)

        # 按最终分数排序
        ranking_results.sort(key=lambda x: x.final_score, reverse=True)

        # 应用多样性控制
        if apply_diversity:
            ranking_results = self._apply_diversity_control(ranking_results)

        # 更新统计信息
        self._update_stats(ranking_results)

        logger.debug(
            f"社区排序完成: 输入{len(communities)}个社区, " f"输出{len(ranking_results)}个结果"
        )

        return ranking_results

    def _calculate_community_score(
        self, community: CommunityMetadata, similarity: float
    ) -> RankingResult:
        """计算单个社区的综合评分"""

        # 1. 相似度分数 (已经是0-1范围)
        similarity_score = max(0.0, min(1.0, similarity))

        # 2. 活跃度评分 (对数缩放避免大社区偏差)
        activity_score = self._calculate_activity_score(community.daily_posts_avg)

        # 3. 质量综合评分
        quality_score = self._calculate_quality_score(community)

        # 4. 加权综合评分
        final_score = (
            similarity_score * self.config.similarity_weight
            + activity_score * self.config.activity_weight
            + quality_score * self.config.quality_weight
        )

        # 5. 高质量社区额外加分
        if quality_score >= self.config.quality_bonus_threshold:
            final_score += 0.05  # 5%额外加分

        return RankingResult(
            community=community,
            similarity_score=similarity_score,
            activity_score=activity_score,
            quality_score=quality_score,
            final_score=final_score,
        )

    def _calculate_activity_score(self, daily_posts_avg: float) -> float:
        """
        计算活跃度评分，使用对数缩放避免大社区偏差

        Args:
            daily_posts_avg: 日均帖子数

        Returns:
            float: 活跃度评分 (0-1)
        """
        if daily_posts_avg <= 0:
            return 0.0

        # 对数缩放：log(posts + 1) / log(max_posts + 1)
        # 这样可以让活跃社区有优势，但不会让超大社区完全碾压小社区
        max_posts = self.config.max_daily_posts_for_scale

        score = math.log(daily_posts_avg + 1) / math.log(max_posts + 1)

        # 确保在0-1范围内
        return max(0.0, min(1.0, score))

    def _calculate_quality_score(self, community: CommunityMetadata) -> float:
        """
        计算质量综合评分

        Args:
            community: 社区元数据

        Returns:
            float: 质量评分 (0-1)
        """
        # 获取各项质量指标
        comment_quality = max(0.0, min(1.0, community.comment_quality_score))
        content_depth = max(0.0, min(1.0, community.content_depth_score))
        business_relevance = max(0.0, min(1.0, community.business_relevance))

        # 加权计算综合质量分数
        quality_score = (
            comment_quality * self.config.comment_quality_weight
            + content_depth * self.config.content_depth_weight
            + business_relevance * self.config.business_relevance_weight
        )

        return quality_score

    def _apply_diversity_control(
        self, ranking_results: List[RankingResult]
    ) -> List[RankingResult]:
        """
        应用多样性控制，避免同类社区扎堆

        Args:
            ranking_results: 按分数排序的结果列表

        Returns:
            List[RankingResult]: 应用多样性控制后的结果
        """
        diverse_results = []

        for result in ranking_results:
            category = result.community.category

            # 检查是否可以添加该类别的社区
            if self.category_counter.can_add_category(category):
                # 添加类别多样性奖励
                category_count = self.category_counter.get_category_count(category)
                if category_count == 0:  # 该类别的第一个社区
                    result.diversity_bonus = self.config.category_bonus
                    result.final_score += result.diversity_bonus

                diverse_results.append(result)
                self.category_counter.add_category(category)

                self.stats["diversity_applied"] += 1
            else:
                # 该类别已满，跳过
                logger.debug(f"类别 {category} 已达上限，跳过社区 {result.community.name}")
                continue

        return diverse_results

    def select_top_communities(
        self, ranking_results: List[RankingResult], top_k: int
    ) -> List[RankingResult]:
        """
        选择top-k社区

        Args:
            ranking_results: 评分结果列表
            top_k: 选择数量

        Returns:
            List[RankingResult]: Top-k结果
        """
        return ranking_results[:top_k]

    def _update_stats(self, results: List[RankingResult]) -> None:
        """更新统计信息"""
        if not results:
            return

        self.stats["total_evaluations"] += len(results)

        # 计算平均分数
        total_score = sum(r.final_score for r in results)
        self.stats["avg_final_score"] = total_score / len(results)

    def get_performance_stats(
        self, use_pydantic: bool = False
    ) -> Union[dict[str, JsonValue], "PerformanceStatsResponse"]:
        """获取性能统计信息

        Args:
            use_pydantic: 是否返回Pydantic模型，默认False保持向后兼容

        Returns:
            Dict或PerformanceStatsResponse: 性能统计数据
        """
        if use_pydantic and PYDANTIC_AVAILABLE:
            return PerformanceStatsResponse(
                total_communities_processed=int(self.stats["total_evaluations"]),
                average_score=float(self.stats["avg_final_score"]),
                processing_time_ms=0.0,  # 待实现
                diversity_applied=self.stats["diversity_applied"] > 0,
                score_distribution={},  # 待实现
            )

        # 向后兼容的字典格式
        stats: dict[str, JsonValue] = {
            "total_evaluations": self.stats["total_evaluations"],
            "avg_final_score": self.stats["avg_final_score"],
            "diversity_applications": self.stats["diversity_applied"],
            "config": {
                "similarity_weight": self.config.similarity_weight,
                "activity_weight": self.config.activity_weight,
                "quality_weight": self.config.quality_weight,
                "max_per_category": self.config.max_per_category,
            },
        }
        return stats

    def explain_score(
        self, result: RankingResult, use_pydantic: bool = False
    ) -> Union[dict[str, JsonValue], "ScoreExplanationResponse"]:
        """
        解释评分结果，提供可解释性

        Args:
            result: 评分结果
            use_pydantic: 是否返回Pydantic模型，默认False保持向后兼容

        Returns:
            Dict或ScoreExplanationResponse: 详细的评分解释
        """
        # 计算分数组件
        similarity_component = result.similarity_score * self.config.similarity_weight
        activity_component = result.activity_score * self.config.activity_weight
        quality_component = result.quality_score * self.config.quality_weight

        interpretation = self._interpret_score(result.final_score)

        if use_pydantic and PYDANTIC_AVAILABLE:
            # 生成优势和改进建议
            strengths = []
            improvement_areas = []

            if result.similarity_score > 0.7:
                strengths.append("高语义相似度匹配")
            if result.activity_score > 0.7:
                strengths.append("社区活跃度高")
            if result.quality_score > 0.7:
                strengths.append("内容质量优秀")
            if result.diversity_bonus > 0:
                strengths.append("类别多样性贡献")

            if result.similarity_score < 0.3:
                improvement_areas.append("提高内容相关性")
            if result.activity_score < 0.3:
                improvement_areas.append("增加社区活跃度")
            if result.quality_score < 0.3:
                improvement_areas.append("提升内容质量")

            return ScoreExplanationResponse(
                community_id=result.community.id,
                community_name=result.community.name,
                final_score=result.final_score,
                similarity_component=similarity_component,
                activity_component=activity_component,
                quality_component=quality_component,
                diversity_bonus=result.diversity_bonus,
                interpretation=interpretation,
                strengths=strengths,
                improvement_areas=improvement_areas,
            )

        # 向后兼容的字典格式（收敛为 JsonValue 映射）
        explanation: dict[str, JsonValue] = {
            "community": cast(
                dict[str, JsonValue],
                {
                    "name": result.community.name,
                    "category": result.community.category,
                    "member_count": result.community.member_count,
                },
            ),
            "score_breakdown": cast(dict[str, JsonValue], result.get_score_breakdown()),
            "score_calculation": cast(
                dict[str, JsonValue],
                {
                    "similarity_contribution": similarity_component,
                    "activity_contribution": activity_component,
                    "quality_contribution": quality_component,
                    "diversity_bonus": result.diversity_bonus,
                },
            ),
            "quality_details": cast(
                dict[str, JsonValue],
                {
                    "comment_quality": result.community.comment_quality_score,
                    "content_depth": result.community.content_depth_score,
                    "business_relevance": result.community.business_relevance,
                },
            ),
            "interpretation": interpretation,
        }

        return explanation

    def _interpret_score(self, score: float) -> str:
        """解释分数含义"""
        if score >= 0.8:
            return "高度相关 - 强烈推荐"
        elif score >= 0.6:
            return "相关度较高 - 推荐"
        elif score >= 0.4:
            return "中等相关 - 可考虑"
        elif score >= 0.2:
            return "相关度较低 - 不太推荐"
        else:
            return "相关度很低 - 不推荐"

    def get_algorithm_metadata(
        self, use_pydantic: bool = False
    ) -> Union[dict[str, JsonValue], "AlgorithmMetadataResponse"]:
        """获取算法元数据

        Args:
            use_pydantic: 是否返回Pydantic模型，默认False保持向后兼容

        Returns:
            Dict或AlgorithmMetadataResponse: 算法元数据
        """
        if use_pydantic and PYDANTIC_AVAILABLE:
            from ..schemas.algorithms.community_ranking import RankingConfigPydantic

            # 创建Pydantic配置
            config_pydantic = RankingConfigPydantic(
                similarity_weight=self.config.similarity_weight,
                activity_weight=self.config.activity_weight,
                quality_weight=self.config.quality_weight,
                max_daily_posts_for_scale=self.config.max_daily_posts_for_scale,
                comment_quality_weight=self.config.comment_quality_weight,
                content_depth_weight=self.config.content_depth_weight,
                business_relevance_weight=self.config.business_relevance_weight,
                max_per_category=self.config.max_per_category,
                category_bonus=self.config.category_bonus,
                min_relevance_threshold=self.config.min_relevance_threshold,
                quality_bonus_threshold=self.config.quality_bonus_threshold,
            )

            return AlgorithmMetadataResponse(
                algorithm_name="Multi-Dimensional Community Ranking",
                version="2.0.0",  # 升级版本号，支持Pydantic
                description="基于语义相似度、社区活跃度和内容质量的多维度社区排序算法",
                current_config=config_pydantic,
                supported_features=[
                    "semantic_similarity",
                    "community_activity",
                    "content_quality",
                    "diversity_control",
                    "pydantic_responses",
                ],
                performance_metrics={
                    "total_evaluations": float(self.stats["total_evaluations"]),
                    "avg_score": self.stats["avg_final_score"],
                    "diversity_rate": float(self.stats["diversity_applied"])
                    / max(self.stats["total_evaluations"], 1),
                },
                model_type="weighted_similarity",
                last_updated="2025-09-07",
            )

        # 向后兼容的字典格式
        meta: dict[str, JsonValue] = {
            "algorithm_name": "Multi-Dimensional Community Ranking",
            "version": "1.0.0",
            "scoring_components": cast(
                List[JsonValue],
                [
                    "semantic_similarity",
                    "community_activity",
                    "content_quality",
                ],
            ),
            "diversity_control": True,
            "weights": {
                "similarity": self.config.similarity_weight,
                "activity": self.config.activity_weight,
                "quality": self.config.quality_weight,
            },
            "performance_stats": cast(
                dict[str, JsonValue], self.get_performance_stats(use_pydantic=False)
            ),
        }
        return meta
