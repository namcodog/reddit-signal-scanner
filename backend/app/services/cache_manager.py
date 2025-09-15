"""
Reddit Signal Scanner - 缓存管理器

PRD-03 缓存优先架构的核心组件
基于Linus设计原则：简洁、高性能、可预测

核心职责：
- 统一的Redis缓存操作接口
- 缓存生命周期管理（TTL、LRU、优先级）
- 与数据库元数据的同步
- 缓存预热和清理策略
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple, cast

import redis.asyncio as redis
from redis.exceptions import RedisError
from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError

from ..core.config import get_settings
from ..core.database import get_db
from ..core.redis_client import get_redis_client
from ..core.sqlalchemy_typing import as_bool_clause
from ..models.community_cache import CommunityCache
from ..schemas.reddit_data import CacheStatus, RedditPost
from ..core.types import TypedRedis

logger = logging.getLogger(__name__)


class CacheManager:
    """Redis缓存管理器

    基于PRD-03缓存优先架构设计：
    - 缓存即数据源：90%的数据来源于缓存
    - 统一接口：屏蔽Redis操作复杂性
    - 生命周期管理：TTL + LRU + Priority三重策略
    - 元数据同步：Redis数据与PostgreSQL元数据一致性
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.redis_client: Optional[TypedRedis] = None
        self.db_session: Optional[AsyncSession] = None

        # 缓存配置
        self.default_ttl = 3600  # 1小时
        self.max_cache_size_mb = 512  # 最大缓存大小
        self.cleanup_batch_size = 100

        # 缓存键模板
        self.key_templates = {
            "community_posts": "community:posts:{community}",
            "community_info": "community:info:{community}",
            "collection_stats": "stats:collection:{date}",
            "rate_limit": "ratelimit:api:{client_id}",
        }

    async def __aenter__(self) -> "CacheManager":
        """异步上下文管理器入口"""
        # 获取包装器并使用其底层原生 AsyncRedis 客户端
        rc_wrapper = await get_redis_client()
        self.redis_client = rc_wrapper.client
        self.db_session = await anext(get_db())
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> None:
        """异步上下文管理器出口"""
        # 不在此处关闭全局 Redis 连接（共享连接池由应用生命周期管理）
        if self.db_session:
            await self.db_session.close()

    # 运行期保障：确保资源已初始化
    def _require_redis(self) -> TypedRedis:
        if self.redis_client is None:
            raise RuntimeError(
                "Redis client is not initialized. Use 'async with CacheManager()' or call create_cache_manager()."
            )
        # 在 __aenter__ 中已将 self.redis_client 设为底层原生 AsyncRedis 客户端
        return cast(TypedRedis, self.redis_client)

    def _require_db(self) -> AsyncSession:
        if self.db_session is None:
            raise RuntimeError(
                "DB session is not initialized. Use 'async with CacheManager()' or call create_cache_manager()."
            )
        return self.db_session

    async def get_community_posts(
        self, community: str, freshness_threshold: float = 0.7
    ) -> Tuple[List[RedditPost], CacheStatus]:
        """获取社区帖子缓存数据

        Args:
            community: 社区名称（支持r/prefix或不含前缀）
            freshness_threshold: 新鲜度阈值（0-1）

        Returns:
            Tuple[List[RedditPost], CacheStatus]: 帖子列表和缓存状态
        """
        clean_community = self._clean_community_name(community)
        cache_key = self.key_templates["community_posts"].format(
            community=clean_community
        )

        try:
            rc = self._require_redis()
            # 获取缓存数据
            cached_data = await rc.get(cache_key)

            # 获取缓存元数据
            cache_status = await self._get_cache_metadata(clean_community)

            if not cached_data:
                logger.debug(f"缓存未命中: {clean_community}")
                return [], cache_status

            # 解析缓存数据
            try:
                cache_content = json.loads(cached_data)
            except json.JSONDecodeError as jde:
                logger.warning(
                    "缓存JSON解析失败: %s (%s)", clean_community, jde
                )
                return [], cache_status
            posts_data = cache_content.get("posts", [])
            cached_at = cache_content.get("cached_at", 0)

            # 检查新鲜度
            cache_age_hours = (time.time() - cached_at) / 3600
            freshness_score = max(0.0, 1.0 - (cache_age_hours / 24))

            if freshness_score < freshness_threshold:
                logger.debug(f"缓存过期: {clean_community}, 新鲜度: {freshness_score:.2f}")
                cache_status.is_fresh = False

            # 转换为RedditPost对象
            posts = []
            for post_data in posts_data:
                try:
                    post = RedditPost(**post_data)
                    posts.append(post)
                except (ValidationError, TypeError, ValueError) as e:
                    logger.warning("解析帖子数据失败: %s (%s)", post_data, e)
                    continue

            # 更新缓存命中统计
            await self._update_hit_statistics(clean_community)

            logger.debug(f"缓存命中: {clean_community}, 帖子数: {len(posts)}")
            return posts, cache_status

        except (RedisError, SQLAlchemyError) as e:
            logger.error("获取缓存数据失败 %s: %s", clean_community, e)
            return [], CacheStatus(community=clean_community)

    async def set_community_posts(
        self, community: str, posts: List[RedditPost], ttl: Optional[int] = None
    ) -> bool:
        """设置社区帖子缓存

        Args:
            community: 社区名称
            posts: 帖子列表
            ttl: 生存时间（秒），None使用默认值

        Returns:
            bool: 设置是否成功
        """
        if not posts:
            logger.warning(f"尝试缓存空帖子列表: {community}")
            return False

        clean_community = self._clean_community_name(community)
        cache_key = self.key_templates["community_posts"].format(
            community=clean_community
        )

        try:
            # 准备缓存数据
            cache_data = {
                "posts": [post.dict() for post in posts],
                "cached_at": time.time(),
                "community": clean_community,
                "total_posts": len(posts),
                "cache_version": "v1.0",
            }

            # 设置Redis缓存
            try:
                cache_json = json.dumps(
                    cache_data, ensure_ascii=False, separators=(",", ":")
                )
            except (TypeError, ValueError) as se:
                logger.error("缓存数据序列化失败 %s: %s", clean_community, se)
                return False
            ttl_value = ttl or self.default_ttl

            rc = self._require_redis()
            await rc.setex(cache_key, ttl_value, cache_json)

            # 更新数据库元数据
            await self._update_cache_metadata(clean_community, len(posts))

            logger.info(f"缓存更新成功: {clean_community}, 帖子数: {len(posts)}")
            return True

        except (RedisError, SQLAlchemyError) as e:
            logger.error("设置缓存失败 %s: %s", clean_community, e)
            return False

    async def get_multiple_communities(
        self, communities: List[str], freshness_threshold: float = 0.7
    ) -> Dict[str, Tuple[List[RedditPost], CacheStatus]]:
        """批量获取多个社区的缓存数据

        Args:
            communities: 社区列表
            freshness_threshold: 新鲜度阈值

        Returns:
            Dict: 社区名 -> (帖子列表, 缓存状态) 映射
        """
        if not communities:
            return {}

        # 并行获取所有社区数据
        tasks = [
            self.get_community_posts(community, freshness_threshold)
            for community in communities
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 组织结果
        community_data: Dict[str, Tuple[List[RedditPost], CacheStatus]] = {}
        for i, result in enumerate(results):
            community = communities[i]
            clean_community = self._clean_community_name(community)

            if isinstance(result, Exception):
                logger.error(f"获取社区数据失败 {community}: {result}")
                community_data[clean_community] = (
                    [],
                    CacheStatus(community=clean_community),
                )
            else:
                posts, cache_status = cast(Tuple[List[RedditPost], CacheStatus], result)
                community_data[clean_community] = (posts, cache_status)

        return community_data

    async def invalidate_community_cache(self, community: str) -> bool:
        """失效社区缓存

        Args:
            community: 社区名称

        Returns:
            bool: 操作是否成功
        """
        clean_community = self._clean_community_name(community)
        cache_key = self.key_templates["community_posts"].format(
            community=clean_community
        )

        try:
            rc = self._require_redis()
            db = self._require_db()
            # 删除Redis缓存
            deleted = await rc.delete(cache_key)

            # 更新数据库元数据
            update_stmt = (
                update(CommunityCache)
                .where(
                    self._as_clause(CommunityCache.community_name == clean_community)
                )
                .values(posts_cached=0, last_crawled_at=None)
            )

            await db.execute(update_stmt)
            await db.commit()

            logger.info(f"缓存失效: {clean_community}")
            return bool(deleted)

        except (RedisError, SQLAlchemyError) as e:
            logger.error("缓存失效失败 %s: %s", clean_community, e)
            return False

    async def cleanup_expired_cache(self, max_items: int = 100) -> int:
        """清理过期缓存

        Args:
            max_items: 最大清理项目数

        Returns:
            int: 清理的项目数量
        """
        try:
            # 获取所有过期缓存记录
            expired_query = (
                select(CommunityCache)
                .where(
                    and_(
                        self._as_clause(
                            cast(Any, CommunityCache.last_crawled_at).isnot(None)
                        ),
                        self._as_clause(
                            (cast(Any, CommunityCache.last_crawled_at))
                            < (
                                datetime.utcnow()
                                - timedelta(
                                    seconds=cast(Any, CommunityCache.ttl_seconds)
                                )
                            )
                        ),
                    )
                )
                .limit(max_items)
            )

            db = self._require_db()
            rc = self._require_redis()
            expired_records = await db.execute(expired_query)
            expired_communities = expired_records.scalars().all()

            if not expired_communities:
                return 0

            # 批量删除Redis缓存
            cache_keys = [
                self.key_templates["community_posts"].format(
                    community=record.community_name
                )
                for record in expired_communities
            ]

            deleted_raw = (await rc.delete(*cache_keys)) if cache_keys else 0
            deleted_count: int = int(deleted_raw)

            # 更新数据库记录
            community_names = [record.community_name for record in expired_communities]
            update_stmt = (
                update(CommunityCache)
                .where(
                    self._as_clause(
                        cast(Any, CommunityCache.community_name).in_(community_names)
                    )
                )
                .values(posts_cached=0, last_crawled_at=None)
            )

            await db.execute(update_stmt)
            await db.commit()

            logger.info(f"清理过期缓存: {deleted_count} 个项目")
            return deleted_count

        except (SQLAlchemyError, RedisError, TypeError, ValueError) as e:
            logger.error(f"清理过期缓存失败: {e}")
            return 0

    async def get_cache_statistics(self) -> dict[str, Any]:
        """获取缓存统计信息

        Returns:
            Dict: 缓存统计数据
        """
        try:
            # 数据库统计
            db = self._require_db()
            rc = self._require_redis()
            total_communities_stmt = select(CommunityCache)
            total_result = await db.execute(total_communities_stmt)
            total_communities = len(total_result.scalars().all())

            cached_communities_stmt = select(CommunityCache).where(
                self._as_clause(CommunityCache.posts_cached > 0)
            )
            cached_result = await db.execute(cached_communities_stmt)
            cached_communities = cached_result.scalars().all()

            # Redis统计
            redis_info = await rc.info("memory")
            memory_used_mb = redis_info.get("used_memory", 0) / (1024 * 1024)

            # 计算统计信息
            total_cached_posts = sum(
                record.posts_cached for record in cached_communities
            )
            total_hits = sum(record.hit_count for record in cached_communities)
            avg_quality = (
                sum(float(record.quality_score) for record in cached_communities)
                / len(cached_communities)
                if cached_communities
                else 0.0
            )

            return {
                "total_communities": total_communities,
                "cached_communities": len(cached_communities),
                "cache_coverage_rate": len(cached_communities)
                / max(1, total_communities),
                "total_cached_posts": total_cached_posts,
                "average_posts_per_community": total_cached_posts
                / max(1, len(cached_communities)),
                "total_cache_hits": total_hits,
                "average_quality_score": avg_quality,
                "redis_memory_used_mb": memory_used_mb,
                "redis_memory_limit_mb": self.max_cache_size_mb,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except (SQLAlchemyError, RedisError) as e:
            logger.error("获取缓存统计失败: %s", e)
            return {"error": str(e)}

    # 私有辅助方法

    def _clean_community_name(self, community: str) -> str:
        """清理社区名称格式"""
        clean_name = community.strip().lower()
        if not clean_name.startswith("r/"):
            clean_name = f"r/{clean_name}"
        return clean_name

    @staticmethod
    def _as_clause(expr: Any) -> ColumnElement[bool]:
        """将任意表达式视为 SQLAlchemy 布尔子句以满足类型检查。"""
        return cast(ColumnElement[bool], expr)

    async def _get_cache_metadata(self, community: str) -> CacheStatus:
        """获取社区缓存元数据"""
        try:
            query = select(CommunityCache).where(
                as_bool_clause(CommunityCache.community_name == community)
            )

            db = self._require_db()
            result = await db.execute(query)
            cache_record = result.scalars().first()

            if not cache_record:
                return CacheStatus(community=community)

            return CacheStatus(
                community=community,
                is_cached=cache_record.posts_cached > 0,
                is_fresh=not cache_record.is_expired(),
                posts_count=cache_record.posts_cached,
                last_updated=cache_record.last_crawled_at,
                quality_score=float(cache_record.quality_score),
                hit_count=cache_record.hit_count,
            )

        except SQLAlchemyError as e:
            logger.error("获取缓存元数据失败 %s: %s", community, e)
            return CacheStatus(community=community)

    async def _update_cache_metadata(self, community: str, posts_count: int) -> None:
        """更新缓存元数据"""
        try:
            # 检查是否存在记录
            query = select(CommunityCache).where(
                self._as_clause(CommunityCache.community_name == community)
            )
            db = self._require_db()
            result = await db.execute(query)
            existing_record = result.scalars().first()

            if existing_record:
                # 更新现有记录
                existing_record.update_cache_stats(posts_count, quality=0.8)
            else:
                # 创建新记录
                new_record = CommunityCache(
                    community_name=community,
                    posts_cached=posts_count,
                    last_crawled_at=datetime.utcnow(),
                    quality_score=Decimal("0.8"),
                )
                db.add(new_record)

            await db.commit()

        except SQLAlchemyError as e:
            logger.error("更新缓存元数据失败 %s: %s", community, e)
            db = self._require_db()
            await db.rollback()

    async def _update_hit_statistics(self, community: str) -> None:
        """更新缓存命中统计"""
        try:
            update_stmt = (
                update(CommunityCache)
                .where(as_bool_clause(CommunityCache.community_name == community))
                .values(
                    hit_count=CommunityCache.hit_count + 1,
                    last_hit_at=datetime.utcnow(),
                )
            )

            db = self._require_db()
            await db.execute(update_stmt)
            await db.commit()

        except SQLAlchemyError as e:
            logger.error("更新命中统计失败 %s: %s", community, e)


# 工厂函数
async def create_cache_manager() -> CacheManager:
    """创建缓存管理器的工厂函数"""
    manager = CacheManager()
    await manager.__aenter__()
    return manager
