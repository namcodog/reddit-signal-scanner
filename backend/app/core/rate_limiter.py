"""
Reddit Signal Scanner - API速率限制器

PRD-03 缓存优先架构的API调用控制组件
基于Linus设计原则：简洁可靠、无特殊情况处理

核心职责：
- 严格限制Reddit API调用频率（<20请求/分钟）
- 平滑分布API调用，避免突发请求
- 提供熔断和降级机制
- 与缓存优先策略无缝集成
"""

import asyncio
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging

import redis.asyncio as redis
from ..core.redis_client import get_redis_client
from ..core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """速率限制配置"""

    requests_per_minute: int = 20  # PRD-03要求：远低于Reddit的60次/分钟
    burst_limit: int = 5  # 突发请求限制
    sliding_window_seconds: int = 60  # 滑动窗口大小
    circuit_breaker_threshold: int = 5  # 熔断阈值（连续失败次数）
    circuit_breaker_timeout: int = 300  # 熔断超时（5分钟）


@dataclass
class RateLimitStatus:
    """速率限制状态"""

    requests_made: int = 0
    requests_remaining: int = 0
    reset_time: float = 0.0
    is_rate_limited: bool = False
    time_until_reset: float = 0.0
    circuit_breaker_active: bool = False


class RedditRateLimiter:
    """Reddit API速率限制器

    基于PRD-03缓存优先策略设计：
    - API调用是补充手段，必须严格限制
    - 使用Redis分布式速率限制，支持多实例
    - 优雅降级：超限时返回缓存数据而非失败
    - 熔断保护：连续失败时暂停API调用
    """

    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig()
        self.redis_client: Optional[redis.Redis] = None
        self.settings = get_settings()

        # Redis键前缀
        self.key_prefix = "rate_limit:reddit_api"
        self.circuit_breaker_key = f"{self.key_prefix}:circuit_breaker"

        # 本地状态（减少Redis查询）
        self._local_status = RateLimitStatus()
        self._last_check_time = 0.0

    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.redis_client = await get_redis_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.redis_client:
            await self.redis_client.close()

    async def acquire_permit(self, timeout: float = 10.0) -> bool:
        """获取API调用许可

        Args:
            timeout: 等待许可的超时时间（秒）

        Returns:
            bool: 是否成功获取许可

        Raises:
            RateLimitExceeded: 速率限制超出且无法在超时时间内获取许可
            CircuitBreakerOpen: 熔断器开启，暂停API调用
        """
        if not self.redis_client:
            raise RuntimeError("RateLimiter未初始化")

        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # 检查熔断器状态
                if await self._is_circuit_breaker_open():
                    raise CircuitBreakerOpen("API熔断器开启，暂停调用")

                # 检查速率限制
                can_proceed = await self._check_rate_limit()

                if can_proceed:
                    # 记录请求
                    await self._record_request()
                    logger.debug("API调用许可获取成功")
                    return True

                # 计算等待时间
                status = await self.get_status()
                if status.time_until_reset > timeout - (time.time() - start_time):
                    logger.warning(f"速率限制，等待时间超过超时限制")
                    raise RateLimitExceeded("API速率限制，等待时间过长")

                # 等待后重试
                wait_time = min(3.0, status.time_until_reset)
                logger.debug(f"速率限制，等待 {wait_time:.1f}秒")
                await asyncio.sleep(wait_time)

            except (CircuitBreakerOpen, RateLimitExceeded):
                raise
            except Exception as e:
                logger.error(f"获取API许可失败: {e}")
                # 降级策略：本地间隔限制
                await asyncio.sleep(3.0)
                return True  # 优雅降级，允许请求

        raise RateLimitExceeded(f"在 {timeout}秒 内无法获取API调用许可")

    async def record_success(self):
        """记录API调用成功"""
        try:
            # 重置熔断器失败计数
            await self.redis_client.delete(f"{self.circuit_breaker_key}:failures")
            logger.debug("API调用成功，重置熔断器计数")
        except Exception as e:
            logger.error(f"记录API成功失败: {e}")

    async def record_failure(self):
        """记录API调用失败"""
        try:
            failure_key = f"{self.circuit_breaker_key}:failures"

            # 增加失败计数
            failures = await self.redis_client.incr(failure_key)
            await self.redis_client.expire(failure_key, 300)  # 5分钟过期

            logger.warning(f"API调用失败，失败计数: {failures}")

            # 检查是否需要开启熔断器
            if failures >= self.config.circuit_breaker_threshold:
                await self._open_circuit_breaker()
                logger.error(f"API连续失败 {failures} 次，开启熔断器")

        except Exception as e:
            logger.error(f"记录API失败失败: {e}")

    async def get_status(self) -> RateLimitStatus:
        """获取当前速率限制状态

        Returns:
            RateLimitStatus: 速率限制状态
        """
        try:
            current_time = time.time()

            # 获取当前窗口的请求计数
            window_key = self._get_window_key(current_time)
            requests_made = await self.redis_client.get(window_key) or 0
            requests_made = int(requests_made)

            # 计算剩余请求数
            requests_remaining = max(0, self.config.requests_per_minute - requests_made)

            # 计算重置时间
            current_minute = int(current_time // 60)
            next_minute = (current_minute + 1) * 60
            time_until_reset = next_minute - current_time

            # 检查熔断器状态
            circuit_breaker_active = await self._is_circuit_breaker_open()

            return RateLimitStatus(
                requests_made=requests_made,
                requests_remaining=requests_remaining,
                reset_time=next_minute,
                is_rate_limited=(requests_remaining == 0),
                time_until_reset=time_until_reset,
                circuit_breaker_active=circuit_breaker_active,
            )

        except Exception as e:
            logger.error(f"获取速率限制状态失败: {e}")
            # 返回保守状态
            return RateLimitStatus(
                requests_made=self.config.requests_per_minute,
                requests_remaining=0,
                is_rate_limited=True,
                time_until_reset=60.0,
            )

    async def reset_limits(self) -> bool:
        """重置速率限制（管理员功能）

        Returns:
            bool: 重置是否成功
        """
        try:
            # 删除所有相关键
            pattern = f"{self.key_prefix}:*"
            cursor = 0
            deleted_count = 0

            while True:
                cursor, keys = await self.redis_client.scan(
                    cursor, match=pattern, count=100
                )
                if keys:
                    deleted_count += await self.redis_client.delete(*keys)
                if cursor == 0:
                    break

            logger.info(f"速率限制重置，删除 {deleted_count} 个键")
            return True

        except Exception as e:
            logger.error(f"重置速率限制失败: {e}")
            return False

    # 私有方法

    async def _check_rate_limit(self) -> bool:
        """检查是否可以发起请求"""
        try:
            current_time = time.time()
            window_key = self._get_window_key(current_time)

            # 获取当前请求计数
            current_count = await self.redis_client.get(window_key)
            current_count = int(current_count) if current_count else 0

            # 检查是否超出限制
            if current_count >= self.config.requests_per_minute:
                return False

            return True

        except Exception as e:
            logger.error(f"检查速率限制失败: {e}")
            return False  # 保守策略

    async def _record_request(self):
        """记录API请求"""
        try:
            current_time = time.time()
            window_key = self._get_window_key(current_time)

            # 使用管道操作保证原子性
            pipe = self.redis_client.pipeline()
            pipe.incr(window_key)
            pipe.expire(
                window_key, self.config.sliding_window_seconds + 10
            )  # 额外10秒缓冲
            await pipe.execute()

            logger.debug(f"记录API请求: {window_key}")

        except Exception as e:
            logger.error(f"记录API请求失败: {e}")

    async def _is_circuit_breaker_open(self) -> bool:
        """检查熔断器是否开启"""
        try:
            breaker_key = f"{self.circuit_breaker_key}:open"
            is_open = await self.redis_client.get(breaker_key)
            return bool(is_open)
        except Exception as e:
            logger.error(f"检查熔断器状态失败: {e}")
            return False

    async def _open_circuit_breaker(self):
        """开启熔断器"""
        try:
            breaker_key = f"{self.circuit_breaker_key}:open"
            await self.redis_client.setex(
                breaker_key, self.config.circuit_breaker_timeout, "1"
            )
            logger.warning(f"熔断器开启，持续 {self.config.circuit_breaker_timeout}秒")
        except Exception as e:
            logger.error(f"开启熔断器失败: {e}")

    def _get_window_key(self, timestamp: float) -> str:
        """获取滑动窗口键名"""
        window_id = int(timestamp // 60)  # 以分钟为窗口
        return f"{self.key_prefix}:window:{window_id}"

    async def get_statistics(self) -> Dict[str, Any]:
        """获取速率限制统计信息"""
        try:
            status = await self.get_status()

            return {
                "config": {
                    "requests_per_minute": self.config.requests_per_minute,
                    "burst_limit": self.config.burst_limit,
                    "circuit_breaker_threshold": self.config.circuit_breaker_threshold,
                },
                "current_status": {
                    "requests_made": status.requests_made,
                    "requests_remaining": status.requests_remaining,
                    "is_rate_limited": status.is_rate_limited,
                    "time_until_reset_seconds": status.time_until_reset,
                    "circuit_breaker_active": status.circuit_breaker_active,
                },
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"获取速率限制统计失败: {e}")
            return {"error": str(e)}


# 异常类
class RateLimitExceeded(Exception):
    """速率限制超出异常"""

    pass


class CircuitBreakerOpen(Exception):
    """熔断器开启异常"""

    pass


# 工厂函数
async def create_rate_limiter(
    config: Optional[RateLimitConfig] = None,
) -> RedditRateLimiter:
    """创建速率限制器工厂函数"""
    limiter = RedditRateLimiter(config)
    await limiter.__aenter__()
    return limiter
