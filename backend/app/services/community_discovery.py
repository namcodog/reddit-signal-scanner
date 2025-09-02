"""
智能社区发现服务 - PRD03-02核心实现
协调关键词提取、语义相似度计算、多维度评分三大算法组件
提供高精度的社区推荐服务
"""

from typing import List, Dict, Optional, Tuple, Any, Union
import asyncio
import logging
import time
import hashlib
import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
import yaml

import redis.asyncio as redis
from ..algorithms import (
    KeywordExtractor,
    ExtractedKeywords,
    SemanticSimilarityEngine,
    SimilarityResult,
    CommunityRanking,
    CommunityMetadata,
    RankingConfig,
    RankingResult,
)

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryRequest:
    """社区发现请求"""

    product_description: str
    max_results: Optional[int] = None
    target_keywords: Optional[List[str]] = None
    filters: Optional[Dict[str, Any]] = None
    enable_cache: bool = True


@dataclass
class DiscoveryResponse:
    """社区发现响应"""

    communities: List[Dict[str, Any]]
    total_found: int
    algorithm_metadata: Dict[str, Any]
    processing_stats: Dict[str, Any]
    request_id: str


@dataclass
class DynamicDecisionResult:
    """动态决策结果"""

    target_count: int
    decision_reason: str
    cache_hit_rate: float
    strategy: str  # aggressive/balanced/conservative


class CommunityDiscoveryService:
    """
    智能社区发现服务主类

    核心功能：
    1. 协调三大算法组件完成4步社区发现流程
    2. 基于缓存命中率的动态数量决策
    3. Redis缓存优化重复查询
    4. 完整的错误处理和监控
    5. 结果可解释性和算法透明度
    """

    # 默认配置
    DEFAULT_CONFIG = {
        "max_communities_scan": 500,
        "default_result_count": 20,
        "cache_ttl": 3600,  # 1小时
        "enable_precompute": True,
        "community_pool_path": "backend/data/community_pool.yaml",
    }

    # 动态决策阈值
    CACHE_THRESHOLDS = {
        "aggressive": 0.8,  # 30个社区
        "balanced": 0.6,  # 20个社区
        "conservative": 0.0,  # 10个社区
    }

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        redis_client: Optional[redis.Redis] = None,
    ):
        """
        初始化社区发现服务

        Args:
            config: 服务配置字典
            redis_client: Redis客户端实例
        """
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        self.redis_client = redis_client

        # 初始化算法组件
        self.keyword_extractor = None
        self.similarity_engine = None
        self.community_ranking = None

        # 社区池数据
        self.community_pool: List[CommunityMetadata] = []

        # 服务状态
        self.is_initialized = False

        # 性能统计
        self.stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "avg_processing_time": 0.0,
            "avg_results_count": 0.0,
        }

        logger.info("CommunityDiscoveryService实例创建完成")

    async def initialize(self):
        """异步初始化服务"""
        if self.is_initialized:
            logger.warning("服务已初始化，跳过重复初始化")
            return

        start_time = time.time()

        try:
            # 1. 初始化Redis连接（如果未提供）
            if self.redis_client is None:
                self.redis_client = redis.Redis(
                    host=os.getenv("REDIS_HOST", "localhost"),
                    port=int(os.getenv("REDIS_PORT", 6379)),
                    decode_responses=True,
                )
                await self.redis_client.ping()
                logger.info("Redis连接建立成功")

            # 2. 加载社区池数据
            await self._load_community_pool()

            # 3. 初始化算法组件
            await self._initialize_components()

            # 4. 预计算向量（如果启用）
            if self.config["enable_precompute"]:
                await self._ensure_precomputed_vectors()

            self.is_initialized = True
            init_time = time.time() - start_time

            logger.info(
                f"CommunityDiscoveryService初始化完成: "
                f"{len(self.community_pool)}个社区加载, "
                f"耗时: {init_time:.2f}秒"
            )

        except Exception as e:
            logger.error(f"服务初始化失败: {e}")
            raise

    async def discover_communities(
        self, request: Union[DiscoveryRequest, Dict[str, Any], str]
    ) -> DiscoveryResponse:
        """
        执行智能社区发现

        Args:
            request: 发现请求，可以是DiscoveryRequest对象、字典或字符串

        Returns:
            DiscoveryResponse: 发现结果
        """
        # 标准化请求格式
        if isinstance(request, str):
            request = DiscoveryRequest(product_description=request)
        elif isinstance(request, dict):
            request = DiscoveryRequest(**request)

        if not self.is_initialized:
            raise RuntimeError("服务未初始化，请先调用initialize()")

        # 生成请求ID
        request_id = self._generate_request_id(request.product_description)
        start_time = time.time()

        try:
            # 尝试从缓存获取结果
            if request.enable_cache:
                cached_result = await self._get_cached_result(request_id)
                if cached_result:
                    self._update_stats(time.time() - start_time, True)
                    return cached_result

            # 执行4步智能社区发现流程
            result = await self._execute_discovery_pipeline(request, request_id)

            # 缓存结果
            if request.enable_cache:
                await self._cache_result(request_id, result)

            # 更新统计
            processing_time = time.time() - start_time
            self._update_stats(processing_time, False)

            return result

        except Exception as e:
            logger.error(f"社区发现失败 (request_id: {request_id}): {e}")
            raise

    async def _execute_discovery_pipeline(
        self, request: DiscoveryRequest, request_id: str
    ) -> DiscoveryResponse:
        """执行4步社区发现流水线"""

        step_start_time = time.time()
        processing_stats = {
            "steps": {},
            "total_time": 0.0,
            "communities_evaluated": len(self.community_pool),
        }

        # 执行4个步骤
        extracted = await self._step_1_extract_keywords(
            request, request_id, processing_stats
        )
        similarity_result = await self._step_2_compute_similarity(
            request, extracted, request_id, processing_stats
        )
        decision_result = await self._step_3_dynamic_decision(
            request, request_id, processing_stats
        )
        final_results = await self._step_4_rank_and_select(
            similarity_result, decision_result, request_id, processing_stats
        )

        # 总处理时间
        processing_stats["total_time"] = time.time() - step_start_time

        # 构建响应
        response = DiscoveryResponse(
            communities=[self._format_community_result(r) for r in final_results],
            total_found=len(final_results),
            algorithm_metadata=self._get_algorithm_metadata(extracted, decision_result),
            processing_stats=processing_stats,
            request_id=request_id,
        )

        logger.info(
            f"[{request_id}] 社区发现完成: {len(final_results)}个社区, "
            f"耗时: {processing_stats['total_time']:.2f}秒"
        )

        return response

    async def _step_1_extract_keywords(
        self, request: DiscoveryRequest, request_id: str, stats: Dict
    ) -> ExtractedKeywords:
        """Step 1: TF-IDF关键词提取"""
        logger.debug(f"[{request_id}] Step 1: 关键词提取")
        step_time = time.time()

        extracted = self.keyword_extractor.extract_keywords(
            request.product_description, max_keywords=20
        )

        stats["steps"]["keyword_extraction"] = {
            "duration": time.time() - step_time,
            "keywords_found": len(extracted.primary_keywords),
            "product_type": extracted.product_type,
            "confidence": extracted.confidence,
        }

        return extracted

    async def _step_2_compute_similarity(
        self,
        request: DiscoveryRequest,
        extracted: ExtractedKeywords,
        request_id: str,
        stats: Dict,
    ) -> SimilarityResult:
        """Step 2: 语义相似度计算"""
        logger.debug(f"[{request_id}] Step 2: 语义相似度计算")
        step_time = time.time()

        # 构建查询文本（结合原始描述和提取的关键词）
        query_text = (
            f"{request.product_description} {' '.join(extracted.primary_keywords[:10])}"
        )

        similarity_result = await self.similarity_engine.compute_similarity_batch(
            query_text=query_text
        )

        stats["steps"]["similarity_computation"] = {
            "duration": time.time() - step_time,
            "cache_hit": similarity_result.cache_hit,
            "model_info": similarity_result.model_info,
        }

        return similarity_result

    async def _step_3_dynamic_decision(
        self, request: DiscoveryRequest, request_id: str, stats: Dict
    ) -> DynamicDecisionResult:
        """Step 3: 动态数量决策"""
        logger.debug(f"[{request_id}] Step 3: 动态数量决策")
        step_time = time.time()

        decision_result = await self._determine_target_count(
            [cm.name for cm in self.community_pool], request.max_results
        )

        stats["steps"]["dynamic_decision"] = {
            "duration": time.time() - step_time,
            "target_count": decision_result.target_count,
            "strategy": decision_result.strategy,
            "cache_hit_rate": decision_result.cache_hit_rate,
        }

        return decision_result

    async def _step_4_rank_and_select(
        self,
        similarity_result: SimilarityResult,
        decision_result: DynamicDecisionResult,
        request_id: str,
        stats: Dict,
    ) -> List[RankingResult]:
        """Step 4: 多维度评分和排序"""
        logger.debug(f"[{request_id}] Step 4: 多维度评分排序")
        step_time = time.time()

        ranking_results = self.community_ranking.rank_communities(
            communities=self.community_pool,
            similarities=similarity_result.similarities.tolist(),
            apply_diversity=True,
        )

        # 选择top-k结果
        final_results = self.community_ranking.select_top_communities(
            ranking_results, decision_result.target_count
        )

        stats["steps"]["ranking_selection"] = {
            "duration": time.time() - step_time,
            "ranked_communities": len(ranking_results),
            "final_selected": len(final_results),
            "diversity_applied": True,
        }

        return final_results

    async def _determine_target_count(
        self, communities: List[str], requested_count: Optional[int] = None
    ) -> DynamicDecisionResult:
        """动态决策社区数量"""

        # 如果用户明确指定数量，直接使用
        if requested_count:
            return DynamicDecisionResult(
                target_count=min(requested_count, len(communities)),
                decision_reason="user_specified",
                cache_hit_rate=0.0,
                strategy="manual",
            )

        # 检查缓存命中率
        cache_stats = await self._check_cache_coverage(communities[:30])  # 检查前30个
        hit_rate = cache_stats["hit_rate"]

        # 动态调整策略
        if hit_rate >= self.CACHE_THRESHOLDS["aggressive"]:
            target_count = 30
            strategy = "aggressive"
            reason = f"缓存命中率高({hit_rate:.1%})，采用积极策略深度分析"
        elif hit_rate >= self.CACHE_THRESHOLDS["balanced"]:
            target_count = 20
            strategy = "balanced"
            reason = f"缓存命中率中等({hit_rate:.1%})，采用平衡策略"
        else:
            target_count = 10
            strategy = "conservative"
            reason = f"缓存命中率低({hit_rate:.1%})，采用保守策略确保5分钟完成"

        return DynamicDecisionResult(
            target_count=target_count,
            decision_reason=reason,
            cache_hit_rate=hit_rate,
            strategy=strategy,
        )

    async def _check_cache_coverage(self, communities: List[str]) -> Dict[str, Any]:
        """检查社区缓存覆盖情况"""
        if not self.redis_client:
            return {"hit_rate": 0.0, "hits": 0, "total": len(communities)}

        cache_hits = 0
        total_checked = len(communities)

        try:
            for community in communities:
                cache_key = f"community:{community}:posts"
                exists = await self.redis_client.exists(cache_key)
                if exists:
                    cache_hits += 1

        except Exception as e:
            logger.warning(f"缓存检查失败: {e}")
            return {"hit_rate": 0.0, "hits": 0, "total": total_checked}

        hit_rate = cache_hits / total_checked if total_checked > 0 else 0.0

        return {"hit_rate": hit_rate, "hits": cache_hits, "total": total_checked}

    def _format_community_result(self, ranking_result: RankingResult) -> Dict[str, Any]:
        """格式化社区结果"""
        community_dict = ranking_result.community.to_dict()

        # 添加评分信息
        community_dict.update(
            {
                "relevance_score": {
                    "final_score": ranking_result.final_score,
                    "similarity_score": ranking_result.similarity_score,
                    "activity_score": ranking_result.activity_score,
                    "quality_score": ranking_result.quality_score,
                    "diversity_bonus": ranking_result.diversity_bonus,
                },
                "score_explanation": self.community_ranking.explain_score(
                    ranking_result
                ),
            }
        )

        return community_dict

    def _get_algorithm_metadata(
        self, extracted: ExtractedKeywords, decision: DynamicDecisionResult
    ) -> Dict[str, Any]:
        """获取算法元数据"""
        return {
            "keyword_extraction": self.keyword_extractor.get_algorithm_metadata(),
            "semantic_similarity": self.similarity_engine.get_algorithm_metadata(),
            "community_ranking": self.community_ranking.get_algorithm_metadata(),
            "dynamic_decision": {
                "strategy": decision.strategy,
                "target_count": decision.target_count,
                "cache_hit_rate": decision.cache_hit_rate,
                "reason": decision.decision_reason,
            },
            "extracted_info": {
                "product_type": extracted.product_type,
                "confidence": extracted.confidence,
                "primary_keywords": extracted.primary_keywords[:5],  # 只显示前5个
            },
        }

    async def _load_community_pool(self):
        """加载社区池数据"""
        pool_path = Path(self.config["community_pool_path"])

        if not pool_path.exists():
            logger.warning(f"社区池文件不存在: {pool_path}")
            # 创建默认的小规模社区池用于测试
            self.community_pool = self._create_default_community_pool()
            return

        try:
            with open(pool_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            # 转换为CommunityMetadata对象
            communities_data = data.get("communities", [])
            self.community_pool = [
                CommunityMetadata(**community) for community in communities_data
            ]

            logger.info(f"社区池加载成功: {len(self.community_pool)}个社区")

        except Exception as e:
            logger.error(f"社区池加载失败: {e}")
            # 使用默认社区池
            self.community_pool = self._create_default_community_pool()

    def _create_default_community_pool(self) -> List[CommunityMetadata]:
        """创建默认社区池（用于测试）"""
        default_communities = [
            CommunityMetadata(
                id="obsidianmd",
                name="r/ObsidianMD",
                display_name="Obsidian Knowledge Management",
                description="Community for Obsidian users discussing note-taking, PKM, and knowledge graphs",
                category="productivity_tools",
                tags=[
                    "note-taking",
                    "pkm",
                    "knowledge-management",
                    "obsidian",
                    "zettelkasten",
                ],
                keywords=["obsidian", "note", "markdown", "graph", "vault", "plugin"],
                member_count=45000,
                daily_posts_avg=12.5,
                comment_quality_score=0.82,
                content_depth_score=0.78,
                business_relevance=0.91,
            ),
            CommunityMetadata(
                id="pkm",
                name="r/PKM",
                display_name="Personal Knowledge Management",
                description="Discussion of personal knowledge management systems and methodologies",
                category="productivity_methods",
                tags=[
                    "pkm",
                    "knowledge-management",
                    "productivity",
                    "systems",
                    "methodology",
                ],
                keywords=[
                    "pkm",
                    "knowledge",
                    "management",
                    "system",
                    "organize",
                    "method",
                ],
                member_count=23000,
                daily_posts_avg=8.3,
                comment_quality_score=0.85,
                content_depth_score=0.91,
                business_relevance=0.88,
            ),
        ]

        logger.info(f"使用默认社区池: {len(default_communities)}个社区")
        return default_communities

    async def _initialize_components(self):
        """初始化算法组件"""
        # 初始化关键词提取器
        self.keyword_extractor = KeywordExtractor()

        # 初始化语义相似度引擎
        self.similarity_engine = SemanticSimilarityEngine(enable_cache=True)
        await self.similarity_engine.initialize()

        # 初始化社区评分系统
        ranking_config = RankingConfig(
            similarity_weight=0.4, activity_weight=0.3, quality_weight=0.3
        )
        self.community_ranking = CommunityRanking(ranking_config)

        logger.info("算法组件初始化完成")

    async def _ensure_precomputed_vectors(self):
        """确保预计算向量存在"""
        if not self.community_pool:
            logger.warning("社区池为空，跳过预计算向量")
            return

        # 检查是否已有预计算向量
        if self.similarity_engine.community_vectors is not None and len(
            self.similarity_engine.community_vectors
        ) == len(self.community_pool):
            logger.info("预计算向量已存在，跳过重新计算")
            return

        logger.info("开始预计算社区向量...")

        # 准备社区数据
        communities_for_compute = []
        for cm in self.community_pool:
            community_dict = cm.to_dict()
            # 组合描述和标签作为计算文本
            combined_text = f"{cm.description} {' '.join(cm.tags)}"
            community_dict["combined_text"] = combined_text
            communities_for_compute.append(community_dict)

        # 执行预计算
        await self.similarity_engine.precompute_community_vectors(
            communities_for_compute, text_field="combined_text"
        )

    def _generate_request_id(self, product_description: str) -> str:
        """生成请求ID"""
        content = f"{product_description}{time.time()}"
        return hashlib.md5(content.encode()).hexdigest()[:8]

    async def _get_cached_result(self, request_id: str) -> Optional[DiscoveryResponse]:
        """从缓存获取结果"""
        if not self.redis_client:
            return None

        try:
            # 使用内容hash作为缓存key而不是request_id
            cache_key = f"discovery:result:{request_id}"
            cached_data = await self.redis_client.get(cache_key)

            if cached_data:
                result_dict = json.loads(cached_data)
                return DiscoveryResponse(**result_dict)

        except Exception as e:
            logger.warning(f"缓存读取失败: {e}")

        return None

    async def _cache_result(self, request_id: str, result: DiscoveryResponse):
        """缓存结果"""
        if not self.redis_client:
            return

        try:
            cache_key = f"discovery:result:{request_id}"
            cached_data = json.dumps(asdict(result), ensure_ascii=False, default=str)

            await self.redis_client.setex(
                cache_key, self.config["cache_ttl"], cached_data
            )

        except Exception as e:
            logger.warning(f"缓存写入失败: {e}")

    def _update_stats(self, processing_time: float, cache_hit: bool):
        """更新性能统计"""
        self.stats["total_requests"] += 1

        if cache_hit:
            self.stats["cache_hits"] += 1

        # 更新平均处理时间
        total_requests = self.stats["total_requests"]
        current_avg = self.stats["avg_processing_time"]
        self.stats["avg_processing_time"] = (
            current_avg * (total_requests - 1) + processing_time
        ) / total_requests

    def get_service_stats(self) -> Dict[str, Any]:
        """获取服务统计信息"""
        cache_hit_rate = 0.0
        if self.stats["total_requests"] > 0:
            cache_hit_rate = self.stats["cache_hits"] / self.stats["total_requests"]

        return {
            "service_status": {
                "initialized": self.is_initialized,
                "community_pool_size": len(self.community_pool),
            },
            "performance_stats": {**self.stats, "cache_hit_rate": cache_hit_rate},
            "component_stats": {
                "keyword_extractor": (
                    self.keyword_extractor.get_algorithm_metadata()
                    if self.keyword_extractor
                    else None
                ),
                "similarity_engine": (
                    self.similarity_engine.get_performance_stats()
                    if self.similarity_engine
                    else None
                ),
                "community_ranking": (
                    self.community_ranking.get_performance_stats()
                    if self.community_ranking
                    else None
                ),
            },
        }

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        health_status = {
            "service_initialized": self.is_initialized,
            "community_pool_loaded": len(self.community_pool) > 0,
            "redis_connected": False,
            "components_ready": {},
        }

        # 检查Redis连接
        if self.redis_client:
            try:
                await self.redis_client.ping()
                health_status["redis_connected"] = True
            except Exception as e:
                health_status["redis_error"] = str(e)

        # 检查组件状态
        if self.is_initialized:
            if self.similarity_engine:
                health_status["components_ready"][
                    "similarity_engine"
                ] = await self.similarity_engine.health_check()

            health_status["components_ready"]["keyword_extractor"] = (
                self.keyword_extractor is not None
            )
            health_status["components_ready"]["community_ranking"] = (
                self.community_ranking is not None
            )

        return health_status
