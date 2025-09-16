"""
清理任务互斥锁 - Reddit Signal Scanner
防止并发执行多个数据清理任务，确保数据一致性

基于Redis实现分布式锁，支持超时和自动释放
"""

import logging
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional, cast

import redis

from .config import get_settings
from .types import JsonValue, RedisProtocol

logger = logging.getLogger(__name__)


class CleanupLockError(Exception):
    """清理锁相关异常"""

    pass


class CleanupLock:
    """
    清理任务分布式锁

    功能：
    - 确保同时只有一个清理任务执行
    - 支持锁超时自动释放
    - 提供锁状态监控
    - 优雅处理锁竞争情况
    """

    def __init__(self, redis_client: Optional[RedisProtocol] = None) -> None:
        self.redis_client = redis_client or self._get_redis_client()
        self.lock_key = "cleanup:execution_lock"
        self.lock_timeout = 3600  # 1小时超时
        self.retry_delay = 1.0  # 重试间隔
        self.max_retries = 3  # 最大重试次数

    def _get_redis_client(self) -> RedisProtocol:
        """获取Redis客户端"""
        try:
            settings = get_settings()
            redis_from_url: Any = redis.from_url
            client_any = redis_from_url(settings.redis_url, decode_responses=True)
            return cast(RedisProtocol, client_any)
        except Exception as e:
            logger.error(f"连接Redis失败: {e}")
            raise CleanupLockError(f"无法连接Redis: {e}")

    @contextmanager
    def acquire(
        self,
        timeout: Optional[int] = None,
        task_info: Optional[dict[str, JsonValue]] = None,
    ) -> Any:
        """
        获取清理锁 - 上下文管理器

        Args:
            timeout: 锁超时时间（秒），默认1小时
            task_info: 任务信息，用于调试和监控

        Raises:
            CleanupLockError: 获取锁失败

        Example:
            with cleanup_lock.acquire(timeout=1800, task_info={'task': 'daily_cleanup'}):
                # 执行清理任务
                pass
        """
        lock_timeout = timeout or self.lock_timeout
        lock_value = self._generate_lock_value(task_info)

        # 尝试获取锁
        acquired = False
        for attempt in range(self.max_retries + 1):
            try:
                acquired = self._try_acquire_lock(lock_value, lock_timeout)
                if acquired:
                    break

                if attempt < self.max_retries:
                    logger.warning(f"清理锁获取失败，第{attempt + 1}次重试...")
                    time.sleep(self.retry_delay * (2**attempt))  # 指数退避

            except Exception as e:
                logger.error(f"获取清理锁异常: {e}")
                if attempt == self.max_retries:
                    raise CleanupLockError(f"获取锁异常: {e}")

        if not acquired:
            current_lock_info = self.get_lock_info()
            raise CleanupLockError(f"清理锁获取失败，当前锁信息: {current_lock_info}")

        logger.info(f"清理锁已获取: {lock_value}")

        try:
            yield lock_value
        finally:
            # 确保锁被释放
            try:
                self._release_lock(lock_value)
                logger.info(f"清理锁已释放: {lock_value}")
            except Exception as e:
                logger.error(f"释放清理锁失败: {e}")

    def _try_acquire_lock(self, lock_value: str, timeout: int) -> bool:
        """尝试获取锁"""
        try:
            # 使用SET NX EX原子操作
            client_any: Any = self.redis_client
            result = client_any.set(
                self.lock_key,
                lock_value,
                nx=True,  # 仅当key不存在时设置
                ex=timeout,  # 设置过期时间
            )
            return bool(result)

        except redis.RedisError as e:
            logger.error(f"Redis获取锁失败: {e}")
            return False

    def _release_lock(self, lock_value: str) -> bool:
        """释放锁 - 使用Lua脚本确保原子性"""
        lua_script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """

        try:
            client_any: Any = self.redis_client
            result = client_any.eval(lua_script, 1, self.lock_key, lock_value)
            return bool(result)

        except redis.RedisError as e:
            logger.error(f"Redis释放锁失败: {e}")
            return False

    def _generate_lock_value(
        self, task_info: Optional[dict[str, JsonValue]] = None
    ) -> str:
        """生成锁值"""
        import socket
        import uuid

        lock_value = {
            "lock_id": str(uuid.uuid4())[:8],
            "hostname": socket.gethostname(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task_info": task_info or {},
        }

        return f"cleanup_lock:{lock_value['lock_id']}:{lock_value['hostname']}"

    def is_locked(self) -> bool:
        """检查是否已被锁定"""
        try:
            return bool(self.redis_client.exists(self.lock_key))
        except redis.RedisError:
            return False

    def get_lock_info(self) -> Optional[dict[str, JsonValue]]:
        """获取当前锁信息"""
        try:
            lock_value = self.redis_client.get(self.lock_key)
            if not lock_value:
                return None

            ttl = self.redis_client.ttl(self.lock_key)

            expires_at_val: Optional[str]
            if ttl > 0:
                expires_at_val = (
                    datetime.now(timezone.utc) + timedelta(seconds=ttl)
                ).isoformat()
            else:
                expires_at_val = None

            return {
                "lock_value": lock_value,
                "ttl_seconds": ttl,
                "expires_at": expires_at_val,
            }

        except redis.RedisError as e:
            logger.error(f"获取锁信息失败: {e}")
            return None

    def force_release(self) -> bool:
        """强制释放锁 - 仅用于紧急情况"""
        try:
            result = self.redis_client.delete(self.lock_key)
            logger.warning(f"强制释放清理锁: {bool(result)}")
            return bool(result)

        except redis.RedisError as e:
            logger.error(f"强制释放锁失败: {e}")
            return False

    def extend_lock(self, lock_value: str, additional_time: int) -> bool:
        """延长锁时间"""
        lua_script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("EXPIRE", KEYS[1], ARGV[2])
        else
            return 0
        end
        """

        try:
            current_ttl = self.redis_client.ttl(self.lock_key)
            if current_ttl <= 0:
                return False

            new_ttl = current_ttl + additional_time
            client_any: Any = self.redis_client
            result = client_any.eval(lua_script, 1, self.lock_key, lock_value, new_ttl)

            logger.info(f"锁时间已延长: +{additional_time}秒")
            return bool(result)

        except redis.RedisError as e:
            logger.error(f"延长锁时间失败: {e}")
            return False


# 全局锁实例
_cleanup_lock_instance: Optional[CleanupLock] = None


def get_cleanup_lock() -> CleanupLock:
    """获取全局清理锁实例"""
    global _cleanup_lock_instance
    if _cleanup_lock_instance is None:
        _cleanup_lock_instance = CleanupLock()
    return _cleanup_lock_instance


def with_cleanup_lock(timeout: Optional[int] = None) -> Callable[..., Any]:
    """清理锁装饰器"""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            cleanup_lock = get_cleanup_lock()

            from typing import Dict as _Dict

            task_info: _Dict[str, JsonValue] = {
                "function": func.__name__,
                "module": func.__module__,
                "args_count": len(args),
                "kwargs_keys": list(kwargs.keys()),
            }

            with cleanup_lock.acquire(timeout=timeout, task_info=task_info):
                return func(*args, **kwargs)

        return wrapper

    return decorator


# 便捷函数
def check_cleanup_lock_status() -> dict[str, JsonValue]:
    """检查清理锁状态"""
    cleanup_lock = get_cleanup_lock()

    return {
        "is_locked": cleanup_lock.is_locked(),
        "lock_info": cleanup_lock.get_lock_info(),
        "redis_connected": True,
    }


def emergency_release_cleanup_lock() -> bool:
    """紧急释放清理锁 - 仅用于运维"""
    cleanup_lock = get_cleanup_lock()
    return cleanup_lock.force_release()


# 导出接口
__all__ = [
    "CleanupLock",
    "CleanupLockError",
    "get_cleanup_lock",
    "with_cleanup_lock",
    "check_cleanup_lock_status",
    "emergency_release_cleanup_lock",
]
