"""
细粒度清理锁管理器 - Reddit Signal Scanner
实现不同清理类型的独立并发控制，避免全局锁阻塞

基于Linus设计原则：
- 最小锁粒度，最大并发度
- 简单的锁机制，复杂的协调逻辑
- 避免死锁，确保释放
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import Dict, Optional, Any, ContextManager
from dataclasses import dataclass
from enum import Enum
import redis
from sqlalchemy.orm import Session

from ..core.config import settings
from ..services.data_cleanup_service_v2 import CleanupCategory

logger = logging.getLogger(__name__)


class LockStatus(Enum):
    """锁状态枚举"""

    AVAILABLE = "available"
    ACQUIRED = "acquired"
    EXPIRED = "expired"
    FAILED = "failed"


@dataclass
class LockInfo:
    """锁信息数据结构"""

    category: str
    lock_key: str
    owner_id: str
    acquired_at: datetime
    expires_at: datetime
    metadata: Dict[str, Any]


class CleanupLockError(Exception):
    """清理锁异常"""

    pass


class CategoryLock:
    """单个清理类别的锁实现 - Linus原则：简单而强大"""

    def __init__(
        self,
        category: CleanupCategory,
        redis_client: redis.Redis,
        ttl_seconds: int = 3600,
    ):
        self.category = category
        self.redis_client = redis_client
        self.ttl_seconds = ttl_seconds
        self.lock_key = f"cleanup_lock:{category.value}"
        self._local_acquired = False
        self._owner_id = None

    def acquire(self, timeout: int = 10, task_info: Optional[Dict] = None) -> bool:
        """
        获取锁 - 非阻塞实现，遵循Linus 3层嵌套原则

        Args:
            timeout: 获取锁的超时时间（秒）
            task_info: 任务信息

        Returns:
            bool: 是否成功获取锁
        """
        owner_id = f"{threading.current_thread().ident}_{int(time.time())}"
        metadata = self._build_lock_metadata(owner_id, task_info)

        start_time = time.time()

        while (time.time() - start_time) < timeout:
            if self._try_acquire_lock(owner_id, metadata):
                return True
            time.sleep(0.1)  # 短暂等待后重试

        logger.warning(f"获取清理锁 {self.category.value} 超时")
        return False

    def _build_lock_metadata(
        self, owner_id: str, task_info: Optional[Dict]
    ) -> Dict[str, Any]:
        """构建锁元数据 - 提取方法减少嵌套"""
        return {
            "acquired_at": datetime.utcnow().isoformat(),
            "expires_at": (
                datetime.utcnow() + timedelta(seconds=self.ttl_seconds)
            ).isoformat(),
            "task_info": task_info or {},
            "thread_id": threading.current_thread().ident,
        }

    def _try_acquire_lock(self, owner_id: str, metadata: Dict[str, Any]) -> bool:
        """尝试获取锁 - 提取方法减少嵌套"""
        # 使用Redis SET NX EX 原子操作
        acquired = self.redis_client.set(
            self.lock_key, owner_id, nx=True, ex=self.ttl_seconds
        )

        if acquired:
            # 存储锁的元数据
            self.redis_client.hset(f"{self.lock_key}:meta", mapping=metadata)
            self.redis_client.expire(f"{self.lock_key}:meta", self.ttl_seconds)

            self._owner_id = owner_id
            self._local_acquired = True
            logger.info(f"成功获取清理锁 {self.category.value} [owner: {owner_id}]")
            return True

        return False

    def release(self) -> bool:
        """
        释放锁

        Returns:
            bool: 是否成功释放锁
        """
        if not self._local_acquired or not self._owner_id:
            logger.warning(f"尝试释放未持有的锁 {self.category.value}")
            return False

        # 使用Lua脚本确保原子性释放
        lua_script = """
        local lock_key = KEYS[1]
        local meta_key = KEYS[2]
        local owner_id = ARGV[1]
        
        if redis.call('GET', lock_key) == owner_id then
            redis.call('DEL', lock_key)
            redis.call('DEL', meta_key)
            return 1
        else
            return 0
        end
        """

        result = self.redis_client.eval(
            lua_script, 2, self.lock_key, f"{self.lock_key}:meta", self._owner_id
        )

        if result == 1:
            self._local_acquired = False
            self._owner_id = None
            logger.info(f"成功释放清理锁 {self.category.value}")
            return True
        else:
            logger.error(f"释放清理锁 {self.category.value} 失败：锁已被其他进程持有")
            return False

    def is_locked(self) -> bool:
        """检查锁是否被持有"""
        return self.redis_client.exists(self.lock_key)

    def get_lock_info(self) -> Optional[LockInfo]:
        """获取锁信息"""
        owner_id = self.redis_client.get(self.lock_key)
        if not owner_id:
            return None

        metadata = self.redis_client.hgetall(f"{self.lock_key}:meta")
        if not metadata:
            return None

        return LockInfo(
            category=self.category.value,
            lock_key=self.lock_key,
            owner_id=owner_id.decode(),
            acquired_at=datetime.fromisoformat(
                metadata.get(b"acquired_at", b"").decode()
            ),
            expires_at=datetime.fromisoformat(
                metadata.get(b"expires_at", b"").decode()
            ),
            metadata={k.decode(): v.decode() for k, v in metadata.items()},
        )

    @contextmanager
    def acquire_context(self, timeout: int = 10, task_info: Optional[Dict] = None):
        """
        上下文管理器方式获取锁

        Args:
            timeout: 获取锁的超时时间
            task_info: 任务信息

        Yields:
            bool: 锁状态

        Raises:
            CleanupLockError: 获取锁失败
        """
        acquired = self.acquire(timeout=timeout, task_info=task_info)

        if not acquired:
            raise CleanupLockError(f"无法获取清理锁 {self.category.value}")

        try:
            yield True
        finally:
            self.release()


class CleanupLockManager:
    """
    清理锁管理器 - Linus架构合规版

    设计原则：
    1. 细粒度锁 - 每个清理类别独立锁
    2. 高并发支持 - 不同类别可同时执行
    3. 自动过期 - 避免死锁
    4. 故障恢复 - 锁会自动释放
    """

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_client = redis.Redis.from_url(redis_url or settings.REDIS_URL)
        self.category_locks: Dict[CleanupCategory, CategoryLock] = {}
        self._init_category_locks()

    def _init_category_locks(self):
        """初始化各类别锁"""
        lock_configs = {
            CleanupCategory.COMPLETED_TASKS: 1800,  # 30分钟 - 数据量大
            CleanupCategory.FAILED_TASKS: 900,  # 15分钟 - 数据量中等
            CleanupCategory.ORPHAN_ANALYSES: 300,  # 5分钟 - 数据量小
            CleanupCategory.EXPIRED_CACHE: 600,  # 10分钟 - IO密集
            CleanupCategory.INACTIVE_USERS: 3600,  # 1小时 - 复杂查询
        }

        for category, ttl in lock_configs.items():
            self.category_locks[category] = CategoryLock(
                category=category, redis_client=self.redis_client, ttl_seconds=ttl
            )

    def get_lock(self, category: CleanupCategory) -> CategoryLock:
        """
        获取指定类别的锁

        Args:
            category: 清理类别

        Returns:
            CategoryLock: 类别锁实例
        """
        lock = self.category_locks.get(category)
        if not lock:
            raise CleanupLockError(f"不支持的清理类别: {category}")

        return lock

    def acquire_multiple(
        self,
        categories: list[CleanupCategory],
        timeout: int = 10,
        task_info: Optional[Dict] = None,
    ) -> Dict[CleanupCategory, bool]:
        """
        批量获取多个类别的锁 - 避免死锁的顺序获取

        Args:
            categories: 清理类别列表
            timeout: 超时时间
            task_info: 任务信息

        Returns:
            Dict: 各类别锁的获取结果
        """
        # 按类别名排序，避免死锁
        sorted_categories = sorted(categories, key=lambda x: x.value)
        acquired_locks = {}
        failed_categories = []

        try:
            for category in sorted_categories:
                lock = self.get_lock(category)
                success = lock.acquire(timeout=timeout, task_info=task_info)
                acquired_locks[category] = success

                if not success:
                    failed_categories.append(category)
                    break

            # 如果有失败的，释放已获取的锁
            if failed_categories:
                for category in acquired_locks:
                    if acquired_locks[category]:
                        self.get_lock(category).release()

                logger.error(f"批量获取锁失败，失败的类别: {failed_categories}")

            return acquired_locks

        except Exception as e:
            # 发生异常时释放所有已获取的锁
            for category in acquired_locks:
                if acquired_locks[category]:
                    try:
                        self.get_lock(category).release()
                    except Exception:
                        pass

            raise CleanupLockError(f"批量获取锁异常: {e}")

    def release_multiple(
        self, categories: list[CleanupCategory]
    ) -> Dict[CleanupCategory, bool]:
        """
        批量释放多个类别的锁

        Args:
            categories: 清理类别列表

        Returns:
            Dict: 各类别锁的释放结果
        """
        results = {}

        for category in categories:
            try:
                lock = self.get_lock(category)
                results[category] = lock.release()
            except Exception as e:
                logger.error(f"释放锁 {category.value} 失败: {e}")
                results[category] = False

        return results

    def get_all_lock_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有锁的状态"""
        status = {}

        for category, lock in self.category_locks.items():
            lock_info = lock.get_lock_info()

            if lock_info:
                status[category.value] = {
                    "status": LockStatus.ACQUIRED.value,
                    "owner_id": lock_info.owner_id,
                    "acquired_at": lock_info.acquired_at.isoformat(),
                    "expires_at": lock_info.expires_at.isoformat(),
                    "metadata": lock_info.metadata,
                }
            else:
                status[category.value] = {
                    "status": LockStatus.AVAILABLE.value,
                    "owner_id": None,
                    "acquired_at": None,
                    "expires_at": None,
                    "metadata": {},
                }

        return status

    def cleanup_expired_locks(self) -> Dict[str, bool]:
        """清理过期锁（Redis会自动处理，此方法用于监控）"""
        results = {}
        current_time = datetime.utcnow()

        for category, lock in self.category_locks.items():
            try:
                lock_info = lock.get_lock_info()

                if lock_info and lock_info.expires_at < current_time:
                    # 锁已过期但Redis还未清理（理论上不应该发生）
                    logger.warning(f"发现过期锁 {category.value}，强制清理")
                    results[category.value] = lock.release()
                else:
                    results[category.value] = True

            except Exception as e:
                logger.error(f"检查锁 {category.value} 状态失败: {e}")
                results[category.value] = False

        return results

    @contextmanager
    def acquire_category_lock(
        self,
        category: CleanupCategory,
        timeout: int = 10,
        task_info: Optional[Dict] = None,
    ):
        """
        上下文管理器方式获取单个类别锁

        Args:
            category: 清理类别
            timeout: 超时时间
            task_info: 任务信息

        Yields:
            CategoryLock: 锁实例

        Raises:
            CleanupLockError: 获取锁失败
        """
        lock = self.get_lock(category)

        with lock.acquire_context(timeout=timeout, task_info=task_info):
            yield lock


# 全局锁管理器实例
_lock_manager = None


def get_cleanup_lock_manager() -> CleanupLockManager:
    """获取全局清理锁管理器"""
    global _lock_manager

    if _lock_manager is None:
        _lock_manager = CleanupLockManager()

    return _lock_manager


# 便捷函数
def acquire_cleanup_lock(
    category: CleanupCategory, timeout: int = 10, task_info: Optional[Dict] = None
) -> ContextManager[CategoryLock]:
    """获取清理锁的便捷函数"""
    manager = get_cleanup_lock_manager()
    return manager.acquire_category_lock(category, timeout, task_info)


def get_cleanup_lock_status() -> Dict[str, Dict[str, Any]]:
    """获取所有清理锁状态的便捷函数"""
    manager = get_cleanup_lock_manager()
    return manager.get_all_lock_status()


# 导出接口
__all__ = [
    "CleanupLockManager",
    "CategoryLock",
    "CleanupLockError",
    "LockInfo",
    "LockStatus",
    "get_cleanup_lock_manager",
    "acquire_cleanup_lock",
    "get_cleanup_lock_status",
]
