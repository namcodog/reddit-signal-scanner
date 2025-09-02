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
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any
from decimal import Decimal
import logging

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_
from sqlalchemy.orm import selectinload

from ..core.database import get_async_db
from ..core.redis_client import get_redis_client
from ..core.config import get_settings
from ..models.community_cache import CommunityCache
from ..schemas.reddit_data import RedditPost, CacheStatus

logger = logging.getLogger(__name__)


class CacheManager:
    """Redis缓存管理器

    基于PRD-03缓存优先架构设计：
    - 缓存即数据源：90%的数据来源于缓存
    - 统一接口：屏蔽Redis操作复杂性
    - 生命周期管理：TTL + LRU + Priority三重策略
    - 元数据同步：Redis数据与PostgreSQL元数据一致性
    """

    def __init__(self):
        self.settings = get_settings()
        self.redis_client: Optional[redis.Redis] = None
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

    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.redis_client = await get_redis_client()
        self.db_session = await anext(get_async_db())
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.redis_client:
            await self.redis_client.close()
        if self.db_session:
            await self.db_session.close()

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
            # 获取缓存数据
            cached_data = await self.redis_client.get(cache_key)

            # 获取缓存元数据
            cache_status = await self._get_cache_metadata(clean_community)

            if not cached_data:
                logger.debug(f"缓存未命中: {clean_community}")
                return [], cache_status

            # 解析缓存数据
            cache_content = json.loads(cached_data)
            posts_data = cache_content.get("posts", [])
            cached_at = cache_content.get("cached_at", 0)

            # 检查新鲜度
            cache_age_hours = (time.time() - cached_at) / 3600
            freshness_score = max(0.0, 1.0 - (cache_age_hours / 24))

            if freshness_score < freshness_threshold:
                logger.debug(
                    f"缓存过期: {clean_community}, 新鲜度: {freshness_score:.2f}"
                )
                cache_status.is_fresh = False

            # 转换为RedditPost对象
            posts = []
            for post_data in posts_data:
                try:
                    post = RedditPost(**post_data)
                    posts.append(post)
                except Exception as e:
                    logger.warning(f"解析帖子数据失败: {e}")
                    continue

            # 更新缓存命中统计
            await self._update_hit_statistics(clean_community)

            logger.debug(f"缓存命中: {clean_community}, 帖子数: {len(posts)}")
            return posts, cache_status

        except Exception as e:
            logger.error(f"获取缓存数据失败 {clean_community}: {e}")
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
            cache_json = json.dumps(
                cache_data, ensure_ascii=False, separators=(",", ":")
            )
            ttl_value = ttl or self.default_ttl

            await self.redis_client.setex(cache_key, ttl_value, cache_json)

            # 更新数据库元数据
            await self._update_cache_metadata(clean_community, len(posts))

            logger.info(f"缓存更新成功: {clean_community}, 帖子数: {len(posts)}")
            return True

        except Exception as e:
            logger.error(f"设置缓存失败 {clean_community}: {e}")
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
        community_data = {}
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
                posts, cache_status = result
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
            # 删除Redis缓存
            deleted = await self.redis_client.delete(cache_key)

            # 更新数据库元数据
            update_stmt = (
                update(CommunityCache)
                .where(CommunityCache.community_name == clean_community)
                .values(posts_cached=0, last_crawled_at=None)
            )

            await self.db_session.execute(update_stmt)
            await self.db_session.commit()

            logger.info(f"缓存失效: {clean_community}")
            return bool(deleted)

        except Exception as e:
            logger.error(f"缓存失效失败 {clean_community}: {e}")
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
                        CommunityCache.last_crawled_at.isnot(None),
                        CommunityCache.last_crawled_at
                        < datetime.utcnow()
                        - timedelta(seconds=CommunityCache.ttl_seconds),
                    )
                )
                .limit(max_items)
            )

            expired_records = await self.db_session.execute(expired_query)
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

            deleted_count = (
                await self.redis_client.delete(*cache_keys) if cache_keys else 0
            )

            # 更新数据库记录
            community_names = [record.community_name for record in expired_communities]
            update_stmt = (
                update(CommunityCache)
                .where(CommunityCache.community_name.in_(community_names))
                .values(posts_cached=0, last_crawled_at=None)
            )

            await self.db_session.execute(update_stmt)
            await self.db_session.commit()

            logger.info(f"清理过期缓存: {deleted_count} 个项目")
            return deleted_count

        except Exception as e:
            logger.error(f"清理过期缓存失败: {e}")
            return 0

    async def get_cache_statistics(self) -> Dict[str, Any]:
        """获取缓存统计信息

        Returns:
            Dict: 缓存统计数据
        """
        try:
            # 数据库统计
            total_communities_stmt = select(CommunityCache)
            total_result = await self.db_session.execute(total_communities_stmt)
            total_communities = len(total_result.scalars().all())

            cached_communities_stmt = select(CommunityCache).where(
                CommunityCache.posts_cached > 0
            )
            cached_result = await self.db_session.execute(cached_communities_stmt)
            cached_communities = cached_result.scalars().all()

            # Redis统计
            redis_info = await self.redis_client.info("memory")
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

        except Exception as e:
            logger.error(f"获取缓存统计失败: {e}")
            return {"error": str(e)}

    # 私有辅助方法

    def _clean_community_name(self, community: str) -> str:
        """清理社区名称格式"""
        clean_name = community.strip().lower()
        if not clean_name.startswith("r/"):
            clean_name = f"r/{clean_name}"
        return clean_name

    async def _get_cache_metadata(self, community: str) -> CacheStatus:
        """获取社区缓存元数据"""
        try:
            query = select(CommunityCache).where(
                CommunityCache.community_name == community
            )

            result = await self.db_session.execute(query)
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

        except Exception as e:
            logger.error(f"获取缓存元数据失败 {community}: {e}")
            return CacheStatus(community=community)

    async def _update_cache_metadata(self, community: str, posts_count: int):
        """更新缓存元数据"""
        try:
            # 检查是否存在记录
            query = select(CommunityCache).where(
                CommunityCache.community_name == community
            )
            result = await self.db_session.execute(query)
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
                self.db_session.add(new_record)

            await self.db_session.commit()

        except Exception as e:
            logger.error(f"更新缓存元数据失败 {community}: {e}")
            await self.db_session.rollback()

    async def _update_hit_statistics(self, community: str):
        """更新缓存命中统计"""
        try:
            update_stmt = (
                update(CommunityCache)
                .where(CommunityCache.community_name == community)
                .values(
                    hit_count=CommunityCache.hit_count + 1,
                    last_hit_at=datetime.utcnow(),
                )
            )

            await self.db_session.execute(update_stmt)
            await self.db_session.commit()

        except Exception as e:
            logger.error(f"更新命中统计失败 {community}: {e}")


# 工厂函数
async def create_cache_manager() -> CacheManager:
    """创建缓存管理器的工厂函数"""
    manager = CacheManager()
    await manager.__aenter__()
    return manager
