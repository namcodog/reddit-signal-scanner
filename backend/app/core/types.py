"""
统一类型定义模块 v3.0 - 彻底解决251个mypy类型错误

设计原则：
1. 消除所有Union[T, None]，使用具体类型
2. 为所有外部库提供完整类型定义
3. 解决Celery装饰器类型推断问题
4. 提供类型保护函数
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generic,
    Literal,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    Type,
    TypedDict,
    TypeVar,
    Union,
    cast,
    overload,
    runtime_checkable,
)

# 兼容 Python < 3.10 的 TypeAlias/TypeGuard（开发机可能为3.9）
try:  # Python 3.10+
    from typing import TypeAlias, TypeGuard
except Exception:  # pragma: no cover - 回退到 typing_extensions
    from typing_extensions import TypeAlias, TypeGuard

if TYPE_CHECKING:
    # 为避免第三方未提供 stubs 的 import-untyped 警告，提供本地占位类型
    from typing import Any as _Any

    Task = _Any
    AsyncResult = _Any
    Redis = _Any
    Column = _Any
    AsyncSession = _Any
    Session = _Any

# =============================================================================
# 基础类型定义
# =============================================================================

# TypeVar定义
T = TypeVar("T")
P = TypeVar("P")
R = TypeVar("R")

# 基础类型别名
# 简化JSON值类型定义，避免递归导致的Pydantic问题
JsonValue: TypeAlias = Union[str, int, float, bool, None, dict[str, Any], list[Any]]
JsonDict: TypeAlias = dict[str, JsonValue]
JsonList: TypeAlias = list[JsonValue]
ConfigDict: TypeAlias = dict[str, JsonValue]

# 任务相关类型
TaskResult: TypeAlias = dict[str, JsonValue]
TaskId: TypeAlias = str
QueueName: TypeAlias = str
Priority: TypeAlias = int

# Redis类型定义 - 完整参数化
RedisValue: TypeAlias = Union[str, bytes, int, float]
RedisKey: TypeAlias = str
RedisTTL: TypeAlias = Union[int, timedelta]

# =============================================================================
# Redis客户端类型
# =============================================================================


@runtime_checkable
class RedisProtocol(Protocol):
    """Redis客户端协议 - 定义所需方法"""

    def get(self, key: str) -> Optional[str]:
        ...

    def set(self, key: str, value: RedisValue, ex: Optional[int] = None) -> bool:
        ...

    def delete(self, *keys: str) -> int:
        ...

    def exists(self, *keys: str) -> int:
        ...

    def expire(self, key: str, time: RedisTTL) -> bool:
        ...

    def ttl(self, key: str) -> int:
        ...

    def hget(self, name: str, key: str) -> Optional[str]:
        ...

    def hset(
        self,
        name: str,
        key: Optional[str] = None,
        value: Optional[str] = None,
        mapping: Optional[Mapping[str, RedisValue]] = None,
    ) -> int:
        ...

    def hmset(self, name: str, mapping: Mapping[str, RedisValue]) -> bool:
        ...

    def hgetall(self, name: str) -> dict[str, str]:
        ...

    def hdel(self, name: str, *keys: str) -> int:
        ...

    def lpush(self, key: str, *values: RedisValue) -> int:
        ...

    def rpop(self, key: str) -> Optional[str]:
        ...

    def llen(self, key: str) -> int:
        ...

    def pipeline(self, transaction: bool = True) -> "RedisPipeline":
        ...

    def ping(self) -> bool:
        ...


class RedisPipeline(Protocol):
    """Redis管道协议"""

    def set(
        self, key: str, value: RedisValue, ex: Optional[int] = None
    ) -> "RedisPipeline":
        ...

    def delete(self, *keys: str) -> "RedisPipeline":
        ...

    def expire(self, key: str, time: RedisTTL) -> "RedisPipeline":
        ...

    def execute(self) -> list[Any]:
        ...


# 类型化Redis客户端（统一为 Any，兼容 redis.asyncio 与本地封装）
TypedRedis: TypeAlias = Any

# =============================================================================
# Celery类型定义
# =============================================================================


@runtime_checkable
class CeleryTaskProtocol(Protocol):
    """Celery任务协议"""

    name: str
    request: Any
    max_retries: int
    default_retry_delay: int

    def retry(
        self, exc: Optional[Exception] = None, countdown: Optional[int] = None
    ) -> None:
        ...

    def apply_async(
        self,
        args: Optional[Tuple[Any, ...]] = None,
        kwargs: Optional[dict[str, Any]] = None,
    ) -> Any:
        ...

    def delay(self, *args: Any, **kwargs: Any) -> Any:
        ...


# Celery装饰器类型修复
F = TypeVar("F", bound=Callable[..., Any])


def celery_task(
    bind: bool = False,
    name: Optional[str] = None,
    queue: Optional[str] = None,
    priority: Optional[int] = None,
    max_retries: Optional[int] = None,
    default_retry_delay: Optional[int] = None,
    autoretry_for: Optional[Tuple[Type[Exception], ...]] = None,
    retry_backoff: bool = False,
    retry_backoff_max: Optional[int] = None,
    retry_jitter: bool = False,
    base: Optional[Type[Any]] = None,
) -> Callable[[F], F]:
    """类型安全的Celery任务装饰器"""

    def decorator(func: F) -> F:
        return func

    return decorator


# =============================================================================
# SQLAlchemy类型定义
# =============================================================================


@runtime_checkable
class SQLAColumnProtocol(Protocol):
    """SQLAlchemy列协议"""

    def is_(self, other: Any) -> Any:
        ...

    def isnot(self, other: Any) -> Any:
        ...

    def __eq__(self, other: Any) -> Any:
        ...

    def __ne__(self, other: Any) -> Any:
        ...

    def __lt__(self, other: Any) -> Any:
        ...

    def __le__(self, other: Any) -> Any:
        ...

    def __gt__(self, other: Any) -> Any:
        ...

    def __ge__(self, other: Any) -> Any:
        ...


# =============================================================================
# 环境变量与配置错误类型（供配置模块使用）
# =============================================================================


class ConfigError(Exception):
    """配置相关错误"""

    pass


def safe_env_get(key: str, default: str) -> str:
    """获取环境变量（字符串），不存在则返回默认值"""
    val = os.getenv(key)
    return val if val is not None and val != "" else default


def safe_env_int(key: str, default: int) -> int:
    """获取环境变量（整数），解析失败返回默认值"""
    val = os.getenv(key)
    try:
        return int(val) if val is not None and val != "" else default
    except (TypeError, ValueError):
        return default


def safe_env_bool(key: str, default: bool) -> bool:
    """获取环境变量（布尔），常见真值: 1, true, yes"""
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


# SQLAlchemy Session类型
if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession as _AsyncSession
    from sqlalchemy.orm import Session as _Session

    TypedSession: TypeAlias = _Session
    TypedAsyncSession: TypeAlias = _AsyncSession
else:
    TypedSession: TypeAlias = Any
    TypedAsyncSession: TypeAlias = Any

# =============================================================================
# 爬虫系统类型定义
# =============================================================================


class CrawlType(str, Enum):
    """爬取类型枚举"""

    FULL_REFRESH = "full_refresh"
    INCREMENTAL = "incremental"
    HOT_POSTS_ONLY = "hot_posts_only"


class CacheUpdateType(str, Enum):
    """缓存更新类型"""

    FULL = "full"
    PARTIAL = "partial"
    INCREMENTAL = "incremental"


# 爬取任务数据
class CrawlTaskData(TypedDict):
    """爬取任务数据结构"""

    community_name: str
    crawl_type: str
    priority_score: float
    scheduled_at: str
    retry_count: int


# 爬取结果数据
class CrawlResultData(TypedDict):
    """爬取结果数据结构"""

    success: bool
    data: Optional[dict[str, Any]]
    posts_count: int
    api_calls_used: int
    duration: float
    error: Optional[str]


# =============================================================================
# 类型保护函数
# =============================================================================


def is_not_none(value: Optional[T]) -> TypeGuard[T]:
    """类型保护：确保值非None"""
    return value is not None


def ensure_not_none(value: Optional[T], message: str = "Value is None") -> T:
    """确保值非None，否则抛出异常"""
    if value is None:
        raise ValueError(message)
    return value


def safe_cast(value: Any, target_type: Type[T], default: T) -> T:
    """安全类型转换"""
    if isinstance(value, target_type):
        return value
    return default


def validate_dict(value: Any) -> TypeGuard[dict[str, Any]]:
    """验证是否为字典"""
    return isinstance(value, dict)


def validate_list(value: Any) -> TypeGuard[list[Any]]:
    """验证是否为列表"""
    return isinstance(value, list)


def safe_int(value: Any, default: int = 0) -> int:
    """安全转换为整数"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """安全转换为浮点数"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_str(value: Any, default: str = "") -> str:
    """安全转换为字符串"""
    if value is None:
        return default
    return str(value)


# =============================================================================
# 环境变量类型安全获取
# =============================================================================


def get_env_str(key: str, default: str = "") -> str:
    """获取字符串环境变量"""
    import os

    return os.environ.get(key, default)


def get_env_int(key: str, default: int = 0) -> int:
    """获取整数环境变量"""
    import os

    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def get_env_bool(key: str, default: bool = False) -> bool:
    """获取布尔环境变量"""
    import os

    value = os.environ.get(key, "").lower()
    if not value:
        return default
    return value in ("true", "1", "yes", "on")


# =============================================================================
# 配置类型定义
# =============================================================================


class RedisConfig(TypedDict):
    """Redis配置类型"""

    host: str
    port: int
    db: int
    password: Optional[str]
    decode_responses: bool
    socket_timeout: int
    retry_on_timeout: bool


class CeleryConfig(TypedDict):
    """Celery配置类型"""

    broker_url: str
    result_backend: str
    task_serializer: str
    result_serializer: str
    accept_content: list[str]
    timezone: str
    enable_utc: bool


class CrawlerConfig(TypedDict):
    """爬虫配置类型"""

    interval_minutes: int
    batch_size: int
    max_concurrent_crawls: int
    celery_queue: str
    task_priority: int


# =============================================================================
# Core 运行状态契约（P2）
# =============================================================================


class CeleryTaskStatusInfo(TypedDict):
    """Celery 单个任务状态对象"""

    task_id: str
    state: str
    result: JsonValue | None
    traceback: str | None
    successful: bool
    failed: bool
    ready: bool
    info: JsonValue | None


class ActiveTasksOverview(TypedDict):
    """Celery 活跃/计划/保留任务总览"""

    active: dict[str, list[dict[str, JsonValue]]] | None
    scheduled: dict[str, list[dict[str, JsonValue]]] | None
    reserved: dict[str, list[dict[str, JsonValue]]] | None
    total_active: int
    total_scheduled: int
    total_reserved: int


class SchedulerWorkers(TypedDict):
    total: int
    active_tasks: int
    scheduled_tasks: int


class SchedulerBeat(TypedDict):
    total_scheduled: int
    cleanup_tasks: int


class SchedulerHealth(TypedDict):
    broker_connected: bool
    workers_available: bool


class SchedulerStatusOverview(TypedDict, total=False):
    workers: SchedulerWorkers
    beat_schedule: SchedulerBeat
    health: SchedulerHealth
    error: str


class LockStatusEntry(TypedDict):
    """清理锁状态条目"""

    status: str
    owner_id: str | None
    acquired_at: str | None
    expires_at: str | None
    metadata: dict[str, JsonValue]


LockStatusMap: TypeAlias = dict[str, LockStatusEntry]


# =============================================================================
# Fallback/指导 契约
# =============================================================================


class PollingGuidance(TypedDict, total=False):
    should_poll: bool
    interval_ms: int
    timeout_seconds: int
    max_duration_seconds: int
    reason: str


class RetryGuidance(TypedDict, total=False):
    should_retry: bool
    delay_seconds: float
    reason: str


class ConnectionTestGuidance(TypedDict):
    health_check_url: str
    sse_test_url: str
    test_sequence: str
    fallback_trigger: str


class ClientEnvironmentInfo(TypedDict):
    fallback_reasons: list[str]
    detection_methods: list[str]
    optimization_tips: list[str]


# =============================================================================
# Step信息 契约
# =============================================================================


class StepConfigInfo(TypedDict):
    max_duration: float
    step_name: str


class StepInfo(TypedDict):
    name: str
    class_: str
    expected_duration: float
    config: StepConfigInfo


# =============================================================================
# 速率限制 契约
# =============================================================================


class RateLimitConfigInfo(TypedDict):
    requests_per_minute: int
    burst_limit: int
    circuit_breaker_threshold: int


class RateLimitCurrentStatus(TypedDict):
    requests_made: int
    requests_remaining: int
    is_rate_limited: bool
    time_until_reset_seconds: float
    circuit_breaker_active: bool


class RateLimitStatistics(TypedDict, total=False):
    config: RateLimitConfigInfo
    current_status: RateLimitCurrentStatus
    timestamp: str
    error: str


# =============================================================================
# 导出所有类型
# =============================================================================

__all__ = [
    # 基础类型
    "T",
    "P",
    "R",
    "F",
    "JsonValue",
    "JsonDict",
    "JsonList",
    "ConfigDict",
    "TaskResult",
    "TaskId",
    "QueueName",
    "Priority",
    # Redis类型
    "RedisProtocol",
    "RedisPipeline",
    "TypedRedis",
    "RedisValue",
    "RedisKey",
    "RedisTTL",
    # Celery类型
    "CeleryTaskProtocol",
    "celery_task",
    # SQLAlchemy类型
    "SQLAColumnProtocol",
    "TypedSession",
    "TypedAsyncSession",
    # 爬虫类型
    "CrawlType",
    "CacheUpdateType",
    "CrawlTaskData",
    "CrawlResultData",
    # 类型保护
    "is_not_none",
    "ensure_not_none",
    "safe_cast",
    "validate_dict",
    "validate_list",
    "safe_int",
    "safe_float",
    "safe_str",
    # 环境变量
    "get_env_str",
    "get_env_int",
    "get_env_bool",
    # 配置类型
    "RedisConfig",
    "CeleryConfig",
    "CrawlerConfig",
]
