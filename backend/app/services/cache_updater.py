"""
精简版缓存更新服务 - PRD03-06 平衡实现

Linus原则：缓存即数据，统一处理
- 统一更新逻辑：存在则更新，不存在则创建
- 保留TTL管理和基本统计
- 严格遵循rss:前缀规范
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Mapping, Optional

import redis
from redis.exceptions import RedisError

from ..core.config import get_settings
from ..core.redis_client import CacheKeys

logger = logging.getLogger(__name__)


class SimpleCacheUpdater:
    """精简缓存更新服务 - 80行核心逻辑"""

    def __init__(self) -> None:
        """初始化缓存更新器"""
        settings = get_settings()
        # 使用redis_url而不是分离的host/port
        redis_from_url: Any = redis.from_url
        self.redis_client = redis_from_url(
            settings.redis_url,
            decode_responses=True,
            socket_timeout=5,
            retry_on_timeout=True,
        )

        # 缓存键前缀 - 遵循现有规范
        self.key_prefix = f"{CacheKeys.PROJECT}:crawler"

        # TTL设置（秒）
        self.posts_ttl = 3600  # 1小时
        self.meta_ttl = 86400  # 24小时

    def update_community_posts(
        self, community_name: str, posts_data: Mapping[str, Any]
    ) -> bool:
        """更新社区帖子缓存 - 统一逻辑

        Args:
            community_name: 社区名称
            posts_data: 帖子数据

        Returns:
            是否成功
        """
        try:
            # 缓存键
            cache_key = f"{self.key_prefix}:community:{community_name}:posts"
            meta_key = f"{self.key_prefix}:community:{community_name}:meta"

            # 获取现有数据（用于增量合并）
            existing = self.redis_client.get(cache_key)

            if existing:
                # 合并新旧数据（去重）
                existing_data = json.loads(existing)
                existing_posts = existing_data.get("posts", [])
                new_posts = (
                    list(posts_data.get("posts", []))
                    if isinstance(posts_data.get("posts", []), list)
                    else []
                )

                # 用字典去重（基于post id）
                posts_dict = {p.get("id"): p for p in existing_posts if p.get("id")}
                for post in new_posts:
                    if post.get("id"):
                        posts_dict[post["id"]] = post

                # 限制总数为最新500个
                all_posts = list(posts_dict.values())
                all_posts.sort(key=lambda x: x.get("id", ""), reverse=True)
                # 构建新的可变字典以写回
                new_payload = dict(posts_data)
                new_payload["posts"] = all_posts[:500]
            else:
                new_payload = dict(posts_data)

            # 保存数据
            json_data = json.dumps(new_payload, default=str)
            self.redis_client.set(cache_key, json_data, ex=self.posts_ttl)

            # 更新元数据
            metadata = {
                "last_update": datetime.utcnow().isoformat(),
                "posts_count": len(posts_data.get("posts", [])),
                "community": community_name,
            }
            self.redis_client.set(meta_key, json.dumps(metadata), ex=self.meta_ttl)

            logger.debug(f"更新缓存成功: {community_name}")
            return True

        except (RedisError, json.JSONDecodeError, TypeError, ValueError) as e:
            logger.error(
                "更新缓存失败 %s: %s", community_name, e,
            )
            return False

    def get_community_posts(self, community_name: str) -> Optional[Mapping[str, Any]]:
        """获取社区帖子缓存"""
        try:
            cache_key = f"{self.key_prefix}:community:{community_name}:posts"
            data = self.redis_client.get(cache_key)
            if data:
                from typing import cast

                return cast(Mapping[str, Any], json.loads(data))
            return None
        except (RedisError, json.JSONDecodeError, TypeError, ValueError) as e:
            logger.error("获取缓存失败 %s: %s", community_name, e)
            return None

    def get_cache_stats(self) -> Mapping[str, Any]:
        """获取简单的缓存统计"""
        try:
            pattern = f"{self.key_prefix}:community:*:posts"
            keys = self.redis_client.keys(pattern)

            return {
                "communities_cached": len(keys),
                "key_prefix": self.key_prefix,
                "posts_ttl": self.posts_ttl,
                "meta_ttl": self.meta_ttl,
            }
        except RedisError as e:
            logger.error("获取统计失败: %s", e)
            return {}


# 工厂函数
def get_cache_updater() -> SimpleCacheUpdater:
    """获取缓存更新器实例"""
    return SimpleCacheUpdater()
