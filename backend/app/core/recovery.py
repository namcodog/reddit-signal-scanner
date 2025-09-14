"""
Reddit Signal Scanner - 错误恢复策略

PRD02-07要求：支持自动恢复和优雅降级
- Reddit API限制 → 缓存模式
- 数据库连接失败 → 重试机制
- SSE连接断开 → 轮询模式

Linus设计哲学：
- "实用主义"：解决生产环境的真实问题
- "简洁胜过聪明"：3个直接函数，避免复杂的恢复框架
- "数据结构优先"：统一的恢复结果格式
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Dict, Optional

from .redis_client import CacheKeys, redis_get
from .types import JsonValue
from .config import get_settings

logger = logging.getLogger(__name__)


class RecoveryResult:
    """
    统一的恢复结果数据结构 - 消除恢复策略的格式差异

    所有恢复策略都返回相同格式的结果，便于：
    - 客户端统一处理
    - 日志记录和监控
    - 后续扩展新的恢复策略
    """

    def __init__(
        self,
        success: bool,
        strategy: str,
        message: str,
        data: Optional[dict[str, JsonValue]] = None,
        retry_after: Optional[int] = None,
    ):
        self.success = success
        self.strategy = strategy
        self.message = message
        self.data = data or {}
        self.retry_after = retry_after
        self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> dict[str, JsonValue]:
        """转换为字典格式，用于API响应"""
        result: dict[str, JsonValue] = {
            "success": self.success,
            "strategy": self.strategy,
            "message": self.message,
            "timestamp": self.timestamp,
        }

        if self.data:
            result["data"] = self.data

        if self.retry_after:
            result["retry_after"] = self.retry_after

        return result


async def cache_fallback_strategy(
    task_id: str, error_context: Optional[dict[str, JsonValue]] = None
) -> RecoveryResult:
    """
    缓存回退策略 - Reddit API限制时启用

    恢复流程：
    1. 尝试从Redis缓存获取数据
    2. 如果有缓存，返回缓存数据
    3. 如果无缓存，启用降级模式

    预期场景：Reddit API 429限流、503服务不可用
    """
    try:
        logger.info(f"Activating cache fallback for task {task_id}")

        # 尝试从Redis缓存获取任务数据
        cache_key = CacheKeys.reddit_task_data(task_id)
        cached_data = await redis_get(cache_key)

        if cached_data:
            # 找到缓存数据，返回成功恢复结果
            logger.info(f"Cache hit for task {task_id}")
            return RecoveryResult(
                success=True,
                strategy="cache_fallback",
                message="已启用缓存模式，使用最近缓存的Reddit数据",
                data={
                    "cache_mode": True,
                    "data_source": "redis_cache",
                    "cache_data": cached_data,
                    "cache_key": cache_key,
                    "degraded_features": ["real_time_updates"],
                },
                retry_after=1800,  # 30分钟后重试Reddit API
            )
        else:
            # 无缓存数据，启用降级模式
            logger.warning(f"Cache miss for task {task_id}, entering degraded mode")
            return RecoveryResult(
                success=True,  # 仍然算作成功，只是功能降级
                strategy="cache_fallback",
                message="缓存无数据，已启用降级模式，部分功能受限",
                data={
                    "cache_mode": True,
                    "data_source": "degraded",
                    "cache_key": cache_key,
                    "degraded_features": ["real_time_updates", "recent_data"],
                },
                retry_after=900,  # 15分钟后重试（无缓存时更快重试）
            )

    except Exception as e:
        logger.error(f"Cache fallback strategy failed: {e}")
        return RecoveryResult(
            success=False,
            strategy="cache_fallback",
            message="缓存系统暂时不可用",
            retry_after=300,  # 5分钟后重试
        )


async def retry_with_backoff_strategy(
    operation: Optional[Callable[[], Awaitable[Any]]],
    max_retries: int = 3,
    base_delay: float = 1.0,
    error_context: Optional[dict[str, JsonValue]] = None,
) -> RecoveryResult:
    """
    指数退避重试策略 - 数据库连接失败时使用

    重试算法：
    1. 第1次重试：延迟1秒
    2. 第2次重试：延迟2秒
    3. 第3次重试：延迟4秒

    预期场景：数据库连接超时、临时网络故障、事务锁冲突
    """
    operation_name = (
        error_context.get("operation", "database_operation")
        if error_context
        else "unknown"
    )

    # 如果没有具体操作，返回重试配置信息
    if operation is None:
        return RecoveryResult(
            success=True,
            strategy="retry_with_backoff",
            message="重试机制已激活，等待外部重试操作",
            data={
                "max_retries": max_retries,
                "base_delay": base_delay,
                "operation": operation_name,
                "note": "需要在业务逻辑层重新调用失败的操作",
            },
        )

    for attempt in range(max_retries):
        try:
            logger.info(
                f"Retry attempt {attempt + 1}/{max_retries} for {operation_name}"
            )

            # 执行重试操作
            if attempt > 0:
                delay = base_delay * (2 ** (attempt - 1))
                await asyncio.sleep(delay)

            # 执行实际操作
            result = await operation()
            logger.info(
                f"Retry successful for {operation_name} after {attempt + 1} attempts"
            )

            return RecoveryResult(
                success=True,
                strategy="retry_with_backoff",
                message=f"重试成功，共尝试 {attempt + 1} 次",
                data={
                    "attempts": attempt + 1,
                    "operation": operation_name,
                    "result": result if isinstance(result, dict) else str(result),
                },
            )

        except Exception as e:
            logger.warning(
                f"Retry attempt {attempt + 1} failed for {operation_name}: {e}"
            )

            if attempt == max_retries - 1:
                # 所有重试都失败
                logger.error(f"All retry attempts failed for {operation_name}")
                return RecoveryResult(
                    success=False,
                    strategy="retry_with_backoff",
                    message=f"重试失败，已尝试 {max_retries} 次",
                    data={
                        "attempts": max_retries,
                        "operation": operation_name,
                        "last_error": str(e),
                    },
                    retry_after=300,  # 5分钟后可以重新尝试
                )

    # 理论上不会到达这里
    return RecoveryResult(
        success=False, strategy="retry_with_backoff", message="重试策略执行异常"
    )


async def polling_fallback_strategy(
    task_id: str, error_context: Optional[dict[str, JsonValue]] = None
) -> RecoveryResult:
    """
    轮询回退策略 - SSE连接断开时使用

    切换流程：
    1. 断开SSE连接
    2. 提供轮询端点信息
    3. 设置合适的轮询间隔

    预期场景：客户端网络不稳定、代理服务器限制、长连接超时
    """
    try:
        logger.info(f"Activating polling fallback for task {task_id}")

        # 计算轮询相关参数
        polling_interval = 2000  # 2秒轮询间隔
        settings = get_settings()
        polling_url = f"{settings.api_prefix}/status/{task_id}"

        return RecoveryResult(
            success=True,
            strategy="polling_fallback",
            message="已切换到轮询模式，确保数据同步",
            data={
                "polling_enabled": True,
                "polling_url": polling_url,
                "polling_interval": polling_interval,
                "task_id": task_id,
                "fallback_reason": (
                    error_context.get("reason", "sse_connection_lost")
                    if error_context
                    else "sse_connection_lost"
                ),
                "instructions": "客户端请定时调用polling_url获取最新状态",
            },
        )

    except Exception as e:
        logger.error(f"Polling fallback strategy failed: {e}")
        return RecoveryResult(
            success=False,
            strategy="polling_fallback",
            message="轮询回退机制初始化失败",
            data={
                "error": str(e),
                "fallback_url": f"{get_settings().api_prefix}/status/{task_id}",
            },
            retry_after=60,  # 1分钟后重试
        )


# 恢复策略注册表 - 简单的映射关系，避免复杂的策略工厂
from typing import Awaitable as _Awaitable

RECOVERY_STRATEGIES: Dict[str, Callable[..., _Awaitable[RecoveryResult]]] = {
    "cache_fallback": cache_fallback_strategy,
    "retry_with_backoff": retry_with_backoff_strategy,
    "polling_fallback": polling_fallback_strategy,
}


async def execute_recovery_strategy(
    strategy_name: str, **kwargs: Any
) -> Optional[RecoveryResult]:
    """
    执行恢复策略 - 统一的策略调用接口

    Args:
        strategy_name: 策略名称 (cache_fallback|retry_with_backoff|polling_fallback)
        **kwargs: 策略执行参数

    Returns:
        RecoveryResult: 恢复结果，失败时返回None
    """
    strategy = RECOVERY_STRATEGIES.get(strategy_name)

    if not strategy:
        logger.error(f"Unknown recovery strategy: {strategy_name}")
        return None

    try:
        return await strategy(**kwargs)
    except Exception as e:
        logger.error(f"Recovery strategy {strategy_name} execution failed: {e}")
        return RecoveryResult(
            success=False, strategy=strategy_name, message=f"恢复策略执行失败: {str(e)}"
        )
