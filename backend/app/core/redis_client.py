"""
Reddit Signal Scanner - Redis客户端管理

Linus设计哲学：
- "数据结构优先"：Redis操作就是简单的键值对操作
- "消除特殊情况"：统一的Redis操作接口
- "简洁胜过聪明"：直接使用redis-py，不搞复杂的抽象层
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional, TypeVar

from redis.asyncio import ConnectionPool
from typing import TYPE_CHECKING
from .types import TypedRedis  # kept for external references
from redis.asyncio import Redis as RuntimeRedis

from .config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def _await_maybe(value: Any) -> Any:
    """Await value if it is awaitable, otherwise return as-is.
    This relaxes mismatched redis-py asyncio stubs across versions.
    """
    try:
        # Awaitables in asyncio implement __await__
        getattr(value, "__await__")
    except Exception:
        return value
    else:
        return await value


class RedisClient:
    """
    Redis异步客户端封装 - 简单直接的Redis操作

    职责：
    - 提供异步Redis连接
    - 统一的键值操作接口
    - 自动JSON序列化/反序列化
    - 连接健康检查
    """

    def __init__(self, redis_url: Optional[str] = None) -> None:
        settings = get_settings()
        self.redis_url = redis_url or settings.redis_url
        self.client: Optional[Any] = None
        self._connected = False

    async def connect(self) -> None:
        """建立Redis连接 - 使用共享连接池"""
        try:
            # 获取共享连接池 - Context7最佳实践
            pool = await get_shared_redis_pool()

            # Context7文档精确模式: Redis(connection_pool=pool)
            self.client = RuntimeRedis(connection_pool=pool)

            # 测试连接
            assert self.client is not None
            await _await_maybe(self.client.ping())
            self._connected = True

            logger.info("Redis connected with shared pool: %s", self.redis_url)

        except Exception as e:
            self._connected = False
            logger.error("Redis connection failed: %s", e)
            raise

    async def disconnect(self) -> None:
        """关闭Redis连接"""
        if self.client:
            # Prefer graceful async close if provided, otherwise fallback
            if hasattr(self.client, "aclose"):
                await _await_maybe(self.client.aclose())
            else:
                await _await_maybe(self.client.close())
            self._connected = False
            logger.info("Redis disconnected")

    async def is_healthy(self) -> bool:
        """检查Redis连接健康状态"""
        if not self.client or not self._connected:
            return False

        try:
            await _await_maybe(self.client.ping())
            return True
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            self._connected = False
            return False

    async def get(self, key: str, default: Any = None) -> Any:
        """
        获取Redis键值

        自动处理JSON反序列化，如果值不是JSON格式则返回字符串
        """
        if not self.client:
            logger.warning("Redis client not connected, returning default value")
            return default

        try:
            value: Any = await _await_maybe(self.client.get(key))

            if value is None:
                return default

            # 尝试JSON反序列化
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                # 不是JSON格式，返回原始字符串
                return value

        except Exception as e:
            logger.error("Redis get failed for key '%s': %s", key, e)
            return default

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        设置Redis键值

        自动处理JSON序列化，支持TTL过期时间
        """
        if not self.client:
            logger.warning("Redis client not connected")
            return False

        try:
            # 自动JSON序列化
            if isinstance(value, (dict, list, tuple)):
                serialized_value = json.dumps(value, ensure_ascii=False)
            else:
                serialized_value = str(value)

            result: Any
            if ttl:
                result = await _await_maybe(
                    self.client.setex(key, ttl, serialized_value)
                )
            else:
                result = await _await_maybe(self.client.set(key, serialized_value))

            # Redis set成功时返回True，处理None情况
            return bool(result) if result is not None else True

        except Exception as e:
            logger.error("Redis set failed for key '%s': %s", key, e)
            return False

    async def delete(self, *keys: str) -> int:
        """删除Redis键，返回删除的键数量"""
        if not self.client:
            return 0

        try:
            return int(await _await_maybe(self.client.delete(*keys)))
        except Exception as e:
            logger.error("Redis delete failed for keys %s: %s", keys, e)
            return 0

    async def exists(self, key: str) -> bool:
        """检查Redis键是否存在"""
        if not self.client:
            return False

        try:
            return bool(await _await_maybe(self.client.exists(key)))
        except Exception as e:
            logger.error(f"Redis exists check failed for key '{key}': {e}")
            return False

    async def expire(self, key: str, ttl: int) -> bool:
        """设置Redis键的过期时间"""
        if not self.client:
            return False

        try:
            return bool(await _await_maybe(self.client.expire(key, ttl)))
        except Exception as e:
            logger.error(f"Redis expire failed for key '{key}': {e}")
            return False

    async def ttl(self, key: str) -> int:
        """获取Redis键的剩余过期时间"""
        if not self.client:
            return -1
        try:
            result: Any = await _await_maybe(self.client.ttl(key))
            return int(result) if result is not None else -1
        except Exception as e:
            logger.error(f"Redis TTL check failed for key '{key}': {e}")
            return -1

    async def incr(self, key: str, amount: int = 1) -> int:
        """自增计数器"""
        if not self.client:
            return 0
        try:
            return int(await _await_maybe(self.client.incr(key, amount)))
        except Exception as e:
            logger.error(f"Redis incr failed for key '{key}': {e}")
            return 0

    async def sadd(self, key: str, *members: Any) -> int:
        """向集合添加成员"""
        if not self.client:
            return 0
        try:
            smembers = [str(m) for m in members]
            return int(await _await_maybe(self.client.sadd(key, *smembers)))
        except Exception as e:
            logger.error(f"Redis sadd failed for key '{key}': {e}")
            return 0

    async def scard(self, key: str) -> int:
        """获取集合基数"""
        if not self.client:
            return 0
        try:
            return int(await _await_maybe(self.client.scard(key)))
        except Exception as e:
            logger.error(f"Redis scard failed for key '{key}': {e}")
            return 0

    async def keys(self, pattern: str = "*") -> list[str]:
        """获取匹配模式的所有键（谨慎使用）"""
        if not self.client:
            return []

        try:
            keys: Any = await _await_maybe(self.client.keys(pattern))
            return list(keys)
        except Exception as e:
            logger.error(f"Redis keys failed for pattern '{pattern}': {e}")
            return []

    async def lpush(self, key: str, *values: Any) -> int:
        """列表左侧推入元素"""
        if not self.client:
            return 0

        try:
            ser_values: list[str] = []
            for v in values:
                if isinstance(v, (dict, list, tuple)):
                    ser_values.append(json.dumps(v, ensure_ascii=False))
                else:
                    ser_values.append(str(v))
            return int(await _await_maybe(self.client.lpush(key, *ser_values)))
        except Exception as e:
            logger.error(f"Redis lpush failed for key '{key}': {e}")
            return 0

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        """获取列表区间元素"""
        if not self.client:
            return []
        try:
            items: Any = await _await_maybe(self.client.lrange(key, start, end))
            return list(items)
        except Exception as e:
            logger.error(f"Redis lrange failed for key '{key}': {e}")
            return []

    async def flush_db(self) -> bool:
        """清空当前数据库（仅开发环境使用）"""
        if not self.client:
            return False

        try:
            settings = get_settings()
            if not settings.is_development:
                logger.warning("Flush DB is only allowed in development environment")
                return False

            await _await_maybe(self.client.flushdb())
            logger.info("Redis database flushed")
            return True

        except Exception as e:
            logger.error(f"Redis flush DB failed: {e}")
            return False


# ===== 全局Redis连接池和客户端实例 =====

from typing import Any

_shared_pool: Optional[Any] = None
_redis_client: Optional[RedisClient] = None


async def get_shared_redis_pool() -> Any:
    """
    获取全局共享Redis连接池 - Context7最佳实践

    基于文档验证的模式：ConnectionPool.from_url + 多客户端复用
    """
    global _shared_pool

    if _shared_pool is None:
        settings = get_settings()

        # Context7文档精确模式: ConnectionPool.from_url
        _shared_pool = ConnectionPool.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,  # 优化并发连接数
            retry_on_timeout=True,  # 自动重连
            socket_connect_timeout=5,
            socket_timeout=5,
            health_check_interval=30,  # 健康检查间隔
        )
        logger.info("Shared Redis connection pool created: %s", settings.redis_url)

    return _shared_pool


async def get_redis_client() -> RedisClient:
    """
    获取全局Redis客户端实例 - 单例模式

    确保整个应用共享同一个Redis连接池
    """
    global _redis_client

    if _redis_client is None:
        _redis_client = RedisClient()
        await _redis_client.connect()

    # 检查连接健康状态，必要时重连
    if not await _redis_client.is_healthy():
        logger.info("Redis connection unhealthy, reconnecting...")
        await _redis_client.connect()

    return _redis_client


# 兼容函数：部分测试从此模块导入 get_redis
# 返回底层原生 AsyncRedis 客户端，便于直接调用 redis-py 方法
async def get_redis() -> Any:
    client = await get_redis_client()
    assert client.client is not None
    return client.client


async def close_redis_client() -> None:
    """关闭全局Redis客户端 - 应用关闭时调用"""
    global _redis_client, _shared_pool

    if _redis_client:
        await _redis_client.disconnect()
        _redis_client = None

    # Context7最佳实践：proper cleanup of shared pool
    if _shared_pool:
        await _shared_pool.disconnect()
        _shared_pool = None
        logger.info("Shared Redis connection pool closed")


# ===== 便利函数 - 简化常见操作 =====


async def redis_get(key: str, default: Any = None) -> Any:
    """便利函数：获取Redis值"""
    client = await get_redis_client()
    return await client.get(key, default)


async def redis_set(key: str, value: Any, ttl: Optional[int] = None) -> bool:
    """便利函数：设置Redis值"""
    client = await get_redis_client()
    return await client.set(key, value, ttl)


async def redis_delete(*keys: str) -> int:
    """便利函数：删除Redis键"""
    client = await get_redis_client()
    return await client.delete(*keys)


async def redis_exists(key: str) -> bool:
    """便利函数：检查Redis键是否存在"""
    client = await get_redis_client()
    return await client.exists(key)


# ===== 缓存键生成器 - 统一命名规范 =====


class CacheKeys:
    """
    Redis缓存键生成器 - 统一命名规范

    规范：项目:模块:标识符:版本
    例如：rss:reddit:task_abc123:v1
    """

    PROJECT = "rss"  # Reddit Signal Scanner

    @classmethod
    def reddit_task_data(cls, task_id: str) -> str:
        """Reddit任务数据缓存键"""
        return f"{cls.PROJECT}:reddit:task_data:{task_id}"

    @classmethod
    def reddit_api_response(cls, endpoint: str, params_hash: str) -> str:
        """Reddit API响应缓存键"""
        return f"{cls.PROJECT}:reddit:api:{endpoint}:{params_hash}"

    @classmethod
    def analysis_result(cls, analysis_id: str) -> str:
        """分析结果缓存键"""
        return f"{cls.PROJECT}:analysis:result:{analysis_id}"

    @classmethod
    def user_session(cls, user_id: str) -> str:
        """用户会话缓存键"""
        return f"{cls.PROJECT}:session:user:{user_id}"

    @classmethod
    def api_rate_limit(cls, client_ip: str, endpoint: str) -> str:
        """API限流缓存键"""
        return f"{cls.PROJECT}:rate_limit:{client_ip}:{endpoint}"
