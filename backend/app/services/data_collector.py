"""
Reddit Signal Scanner - 缓存优先数据采集系统

PRD-03 Step 2: 缓存优先数据采集系统的核心实现
基于Linus设计原则：数据结构优先 + 消除特殊情况 + 简洁实用

核心理念：
- 90% 数据来自Redis缓存（预爬取）
- 10% 数据通过精准API调用补充
- 统一的数据源接口，消除缓存/API的特殊情况处理
- 异步并发处理，确保5分钟内完成采集
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from decimal import Decimal
import logging

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from ..core.database import get_async_db
from ..core.redis_client import get_redis_client
from ..core.config import get_settings
from ..core.config_manager import get_data_collection_config, get_cache_config
from ..core.input_validator import validate_community_list
from ..models.community_cache import CommunityCache
from ..schemas.reddit_data import RedditPost, DataCollectionResult
from .reddit_client import RedditAPIClient

logger = logging.getLogger(__name__)


@dataclass
class DataSourceResult:
    """数据源结果统一模型 - 消除缓存/API差异"""

    posts: List[RedditPost]
    source_type: str  # "cache" or "api"
    communities_covered: List[str]
    coverage_rate: float  # 0.0-1.0
    fetch_time_seconds: float
    error_message: Optional[str] = None
    cache_hit_rate: Optional[float] = None


@dataclass
class CollectionConfig:
    """数据采集配置 - 统一参数管理"""

    target_communities: List[str]
    max_posts_per_community: int = 100
    max_api_calls: int = 15  # 限制API调用数量
    cache_freshness_threshold: float = 0.7  # 缓存新鲜度阈值
    concurrent_limit: int = 10  # 并发限制
    timeout_seconds: int = 120  # 超时时间


class DataCollectionService:
    """缓存优先数据采集系统主服务

    架构设计原则：
    1. 数据结构优先：统一的 CollectionConfig 输入，DataCollectionResult 输出
    2. 消除特殊情况：缓存和API使用相同的处理流程
    3. 简洁实用：单一职责，只负责数据采集，不处理业务逻辑
    """

    def __init__(self):
        self.settings = get_settings()
        self.config = get_data_collection_config()
        self.cache_config = get_cache_config()
        self.redis_client: Optional[redis.Redis] = None
        self.reddit_client: Optional[RedditAPIClient] = None
        self.db_session: Optional[AsyncSession] = None

    async def __aenter__(self):
        """异步上下文管理器 - 初始化连接"""
        self.redis_client = await get_redis_client()
        self.reddit_client = RedditAPIClient()
        # 注意：在实际使用中，db_session应该通过依赖注入获得
        # 这里用于演示，生产环境应使用 Depends(get_async_db)
        db_generator = get_async_db()
        self.db_session = await db_generator.__anext__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器 - 清理连接"""
        if self.redis_client:
            await self.redis_client.close()
        if self.reddit_client:
            await self.reddit_client.close()
        if self.db_session:
            await self.db_session.close()

    async def collect_community_data(
        self, config: CollectionConfig
    ) -> DataCollectionResult:
        """主数据采集接口

        基于PRD-03缓存优先策略：
        1. 检查缓存覆盖率，确定数据获取策略
        2. 90%数据优先从Redis缓存获取
        3. 10%数据通过精准API调用补充
        4. 所有数据统一清洗和格式化

        Args:
            config: 数据采集配置

        Returns:
            DataCollectionResult: 统一的采集结果
        """
        start_time = time.time()

        # 输入验证
        validated_communities = validate_community_list(config.target_communities)
        config.target_communities = validated_communities

        logger.info(f"开始采集 {len(config.target_communities)} 个社区数据")

        try:
            # Step 1: 分析缓存状态，制定数据获取策略
            cache_analysis = await self._analyze_cache_coverage(
                config.target_communities
            )
            collection_strategy = self._determine_collection_strategy(
                cache_analysis, config
            )

            logger.info(
                f"缓存命中率: {cache_analysis['hit_rate']:.1%}, 策略: {collection_strategy['name']}"
            )

            # Step 2: 并行执行数据采集任务
            collection_tasks = self._create_collection_tasks(
                collection_strategy, config
            )
            results = await asyncio.gather(*collection_tasks, return_exceptions=True)

            # Step 3: 合并和清洗数据
            merged_data = await self._merge_and_clean_results(
                results, config.target_communities
            )

            # Step 4: 更新缓存统计
            await self._update_cache_statistics(cache_analysis, merged_data)

            execution_time = time.time() - start_time
            logger.info(
                f"数据采集完成，耗时 {execution_time:.2f}秒，获取 {len(merged_data.posts)} 个帖子"
            )

            return merged_data

        except Exception as e:
            logger.error(f"数据采集失败: {str(e)}", exc_info=True)
            return DataCollectionResult(
                posts=[],
                total_communities=len(config.target_communities),
                successful_communities=0,
                cache_hit_rate=0.0,
                api_calls_made=0,
                execution_time_seconds=time.time() - start_time,
                error_message=str(e),
            )

    async def _analyze_cache_coverage(self, communities: List[str]) -> Dict:
        """分析缓存覆盖率和质量

        Returns:
            Dict: 包含缓存命中率、质量分布、过期状态等信息
        """
        cache_query = select(CommunityCache).where(
            CommunityCache.community_name.in_(communities)
        )

        cache_records = await self.db_session.execute(cache_query)
        cached_communities = {
            record.community_name: record for record in cache_records.scalars()
        }

        # 分析缓存状态
        fresh_cache_count = 0
        stale_cache_count = 0
        total_cached_posts = 0
        quality_scores = []

        for community in communities:
            if community in cached_communities:
                cache_record = cached_communities[community]
                if not cache_record.is_expired():
                    fresh_cache_count += 1
                    total_cached_posts += cache_record.posts_cached
                    quality_scores.append(float(cache_record.quality_score))
                else:
                    stale_cache_count += 1

        hit_rate = fresh_cache_count / len(communities) if communities else 0.0
        avg_quality = (
            sum(quality_scores) / len(quality_scores) if quality_scores else 0.5
        )

        return {
            "hit_rate": hit_rate,
            "fresh_communities": fresh_cache_count,
            "stale_communities": stale_cache_count,
            "missing_communities": len(communities) - len(cached_communities),
            "total_cached_posts": total_cached_posts,
            "average_quality": avg_quality,
            "cached_records": cached_communities,
        }

    def _determine_collection_strategy(
        self, cache_analysis: Dict, config: CollectionConfig
    ) -> Dict:
        """确定数据采集策略

        基于PRD-03的缓存优先原则和Linus的简洁设计：
        策略统一为"缓存优先+API精准补充"，只调整参数不改变逻辑结构
        """
        hit_rate = cache_analysis["hit_rate"]

        if hit_rate >= 0.8:
            # 高缓存命中率：主要使用缓存，少量API补充
            strategy = {
                "name": "cache_dominant",
                "max_api_calls": min(config.max_api_calls, 5),
                "cache_preference": 0.95,
                "api_supplement_ratio": 0.05,
            }
        elif hit_rate >= 0.6:
            # 中等缓存命中率：缓存+API混合
            strategy = {
                "name": "hybrid",
                "max_api_calls": min(config.max_api_calls, 10),
                "cache_preference": 0.8,
                "api_supplement_ratio": 0.2,
            }
        else:
            # 低缓存命中率：更多依赖API调用
            strategy = {
                "name": "api_heavy",
                "max_api_calls": config.max_api_calls,
                "cache_preference": 0.6,
                "api_supplement_ratio": 0.4,
            }

        return strategy

    def _create_collection_tasks(
        self, strategy: Dict, config: CollectionConfig
    ) -> List:
        """创建并发采集任务列表

        统一任务类型：每个任务都返回 DataSourceResult
        消除缓存/API的特殊处理逻辑
        """
        tasks = []
        api_calls_scheduled = 0

        for community in config.target_communities:
            # 统一任务创建逻辑：所有社区都尝试缓存优先
            task = self._collect_single_community(
                community=community,
                max_posts=config.max_posts_per_community,
                allow_api_fallback=(api_calls_scheduled < strategy["max_api_calls"]),
                freshness_threshold=config.cache_freshness_threshold,
            )
            tasks.append(task)

            # API调用计数（用于限流）
            if api_calls_scheduled < strategy["max_api_calls"]:
                api_calls_scheduled += 1

        return tasks

    async def _collect_single_community(
        self,
        community: str,
        max_posts: int,
        allow_api_fallback: bool,
        freshness_threshold: float,
    ) -> DataSourceResult:
        """采集单个社区数据 - 缓存优先策略

        统一处理逻辑：
        1. 优先尝试缓存读取
        2. 缓存失效且允许API调用时，使用API补充
        3. 其他情况返回空结果（优雅降级）
        """
        start_time = time.time()

        try:
            # Step 1: 尝试从缓存读取
            cache_result = await self._load_from_cache(community, freshness_threshold)

            if cache_result.posts and len(cache_result.posts) >= max_posts * 0.7:
                # 缓存数据充足，直接使用
                cache_result.fetch_time_seconds = time.time() - start_time
                return cache_result

            # Step 2: 缓存不足，尝试API补充
            if allow_api_fallback:
                api_result = await self._fetch_from_api(community, max_posts)

                if api_result.posts:
                    # 更新缓存
                    await self._update_community_cache(community, api_result.posts)
                    api_result.fetch_time_seconds = time.time() - start_time
                    return api_result

            # Step 3: 优雅降级 - 返回可用的缓存数据（即使过期）
            fallback_result = await self._load_from_cache(
                community, freshness_threshold=0.0
            )
            fallback_result.fetch_time_seconds = time.time() - start_time
            fallback_result.error_message = "使用过期缓存数据，API调用受限"

            return fallback_result

        except Exception as e:
            logger.error(f"采集社区 {community} 数据失败: {str(e)}")
            return DataSourceResult(
                posts=[],
                source_type="error",
                communities_covered=[],
                coverage_rate=0.0,
                fetch_time_seconds=time.time() - start_time,
                error_message=str(e),
            )

    async def _load_from_cache(
        self, community: str, freshness_threshold: float
    ) -> DataSourceResult:
        """从Redis缓存加载社区数据"""
        cache_key = f"community:posts:{community}"

        try:
            cached_data = await self.redis_client.get(cache_key)
            if not cached_data:
                return DataSourceResult(
                    posts=[],
                    source_type="cache_miss",
                    communities_covered=[],
                    coverage_rate=0.0,
                    fetch_time_seconds=0.0,
                )

            posts_data = json.loads(cached_data)
            posts = [
                RedditPost(**post_data) for post_data in posts_data.get("posts", [])
            ]

            # 检查数据新鲜度
            cache_timestamp = posts_data.get("cached_at", 0)
            age_hours = (time.time() - cache_timestamp) / 3600
            freshness = max(0.0, 1.0 - (age_hours / 24))  # 24小时内线性衰减

            return DataSourceResult(
                posts=posts,
                source_type="cache",
                communities_covered=[community] if posts else [],
                coverage_rate=1.0 if freshness >= freshness_threshold else freshness,
                fetch_time_seconds=0.0,
                cache_hit_rate=1.0 if posts else 0.0,
            )

        except Exception as e:
            logger.warning(f"缓存读取失败 {community}: {str(e)}")
            return DataSourceResult(
                posts=[],
                source_type="cache_error",
                communities_covered=[],
                coverage_rate=0.0,
                fetch_time_seconds=0.0,
                error_message=str(e),
            )

    async def _fetch_from_api(self, community: str, max_posts: int) -> DataSourceResult:
        """从Reddit API获取社区数据"""
        try:
            posts = await self.reddit_client.get_community_posts(
                subreddit=community, limit=max_posts, time_filter="day", sort="hot"
            )

            return DataSourceResult(
                posts=posts,
                source_type="api",
                communities_covered=[community] if posts else [],
                coverage_rate=1.0 if posts else 0.0,
                fetch_time_seconds=0.0,  # 将在上级函数设置
                cache_hit_rate=0.0,
            )

        except Exception as e:
            logger.error(f"API调用失败 {community}: {str(e)}")
            return DataSourceResult(
                posts=[],
                source_type="api_error",
                communities_covered=[],
                coverage_rate=0.0,
                fetch_time_seconds=0.0,
                error_message=str(e),
            )

    async def _update_community_cache(self, community: str, posts: List[RedditPost]):
        """更新社区缓存数据"""
        try:
            # 更新Redis缓存
            cache_key = f"community:posts:{community}"
            cache_data = {
                "posts": [asdict(post) for post in posts],
                "cached_at": time.time(),
                "community": community,
                "total_posts": len(posts),
            }

            await self.redis_client.setex(
                cache_key, 3600, json.dumps(cache_data)  # 1小时TTL
            )

            # 更新数据库元数据
            update_stmt = (
                update(CommunityCache)
                .where(CommunityCache.community_name == community)
                .values(
                    posts_cached=len(posts),
                    last_crawled_at=datetime.utcnow(),
                    quality_score=Decimal("0.8"),  # API数据质量较高
                )
            )

            await self.db_session.execute(update_stmt)
            await self.db_session.commit()

        except Exception as e:
            logger.error(f"更新缓存失败 {community}: {str(e)}")

    async def _merge_and_clean_results(
        self,
        results: List[Union[DataSourceResult, Exception]],
        target_communities: List[str],
    ) -> DataCollectionResult:
        """合并和清洗采集结果"""
        all_posts = []
        successful_communities = []
        total_api_calls = 0
        cache_hits = 0
        errors = []

        for result in results:
            if isinstance(result, Exception):
                errors.append(str(result))
                continue

            if isinstance(result, DataSourceResult):
                all_posts.extend(result.posts)
                successful_communities.extend(result.communities_covered)

                if result.source_type == "api":
                    total_api_calls += 1
                elif result.source_type == "cache" and result.cache_hit_rate > 0:
                    cache_hits += 1

                if result.error_message:
                    errors.append(result.error_message)

        # 数据去重（基于帖子ID）
        seen_post_ids = set()
        unique_posts = []
        for post in all_posts:
            if post.id not in seen_post_ids:
                unique_posts.append(post)
                seen_post_ids.add(post.id)

        # 数据质量过滤
        clean_posts = self._filter_low_quality_posts(unique_posts)

        cache_hit_rate = (
            cache_hits / len(target_communities) if target_communities else 0.0
        )

        return DataCollectionResult(
            posts=clean_posts,
            total_communities=len(target_communities),
            successful_communities=len(set(successful_communities)),
            cache_hit_rate=cache_hit_rate,
            api_calls_made=total_api_calls,
            execution_time_seconds=0.0,  # 在调用方设置
            errors=errors if errors else None,
        )

    def _filter_low_quality_posts(self, posts: List[RedditPost]) -> List[RedditPost]:
        """过滤低质量帖子

        PRD-03要求：过滤删除、被封等低质量内容
        """
        clean_posts = []

        for post in posts:
            # 基础过滤条件
            if (
                post.is_deleted
                or post.is_removed
                or not post.title
                or len(post.title) < 10
                or post.score < 1
            ):
                continue

            # 内容长度检查
            content_length = len(post.content or "") + len(post.title or "")
            if content_length < 50:
                continue

            clean_posts.append(post)

        return clean_posts

    async def _update_cache_statistics(
        self, cache_analysis: Dict, result: DataCollectionResult
    ):
        """更新缓存统计信息"""
        try:
            # 更新缓存命中统计
            for community_name, cache_record in cache_analysis[
                "cached_records"
            ].items():
                cache_record.increment_hit_count()

            await self.db_session.commit()
            logger.debug(
                f"已更新 {len(cache_analysis['cached_records'])} 个社区的缓存统计"
            )

        except Exception as e:
            logger.error(f"更新缓存统计失败: {str(e)}")


# 工厂函数：简化服务使用
async def collect_posts_data(
    communities: List[str], max_posts: int = 100
) -> DataCollectionResult:
    """便捷的数据采集接口

    Args:
        communities: 目标社区列表
        max_posts: 每个社区最大帖子数

    Returns:
        DataCollectionResult: 采集结果
    """
    config = CollectionConfig(
        target_communities=communities, max_posts_per_community=max_posts
    )

    async with DataCollectionService() as collector:
        return await collector.collect_community_data(config)
