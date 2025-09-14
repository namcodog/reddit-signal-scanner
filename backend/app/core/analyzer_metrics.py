"""
分析引擎性能指标收集 - 基于现有监控系统的扩展

设计原则：
1. 扩展而非替代 - 基于task_monitor的类型扩展
2. 简单数据流 - 指标收集→聚合→存储
3. 零侵入性 - 通过装饰器和中间件收集
"""

import functools
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
    cast,
)

# Type variables for decorator
F = TypeVar("F", bound=Callable[..., Any])

from pydantic import BaseModel, Field, validator

from typing import Any as _Any  # 本地别名，减少全局污染

# 可选依赖 psutil 的安全导入（避免 mypy 模块/None 赋值冲突）
psutil_mod: _Any = None
try:  # pragma: no cover - 环境可能无 psutil
    import psutil as _psutil_mod
    psutil_mod = _psutil_mod
except Exception:  # pragma: no cover
    psutil_mod = None

# 复用现有监控基础类型
from app.schemas.task_monitor import (
    Alert,
    AlertConditionType,
    AlertConfig,
    AlertSeverity,
)

# ==================== 分析引擎专用类型 ====================


class AnalysisStep(str, Enum):
    """分析引擎处理步骤"""

    STEP1_COMMUNITY = "community_discovery"
    STEP2_REDDIT_DATA = "reddit_data_collection"
    STEP3_AI_EXTRACTION = "ai_extraction"
    STEP4_RANKING = "ranking_output"
    CACHE_MAINTENANCE = "cache_maintenance"


@dataclass
class StepMetrics:
    """单个步骤的性能指标"""

    step_name: AnalysisStep
    execution_time: float  # 秒
    memory_delta: float  # MB变化
    api_calls: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    items_processed: int = 0
    error_count: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def cache_hit_rate(self) -> float:
        """缓存命中率"""
        total = self.cache_hits + self.cache_misses
        return (self.cache_hits / max(total, 1)) * 100


class AnalysisPerformanceMetrics(BaseModel):
    """完整分析流程的性能指标"""

    analysis_id: str
    keyword: str
    total_execution_time: float
    step_metrics: Dict[AnalysisStep, StepMetrics]

    # Reddit API监控
    api_calls_total: int = 0
    api_calls_failed: int = 0
    rate_limit_remaining: int = 1000
    rate_limit_reset: Optional[datetime] = None

    # 缓存性能
    cache_hit_rate_overall: float = Field(ge=0, le=100)
    cache_operations_total: int = 0

    # 数据覆盖
    communities_discovered: int = 0
    posts_collected: int = 0
    insights_extracted: int = 0

    # 系统资源
    peak_memory_mb: float = 0
    avg_cpu_percent: float = Field(ge=0, le=100, default=0)

    started_at: datetime
    completed_at: Optional[datetime] = None

    @validator("cache_hit_rate_overall")
    def calculate_cache_hit_rate(cls, v: float, values: dict[str, Any]) -> float:
        """计算整体缓存命中率"""
        if "step_metrics" in values:
            from typing import Dict as _Dict

            metrics = values["step_metrics"]
            typed_metrics: _Dict[AnalysisStep, StepMetrics] = cast(
                _Dict[AnalysisStep, StepMetrics], metrics
            )
            total_hits: int = sum(m.cache_hits for m in typed_metrics.values())
            total_misses: int = sum(m.cache_misses for m in typed_metrics.values())
            total_ops = total_hits + total_misses
            if total_ops > 0:
                return (total_hits / total_ops) * 100
        return v

    @property
    def is_meeting_sla(self) -> bool:
        """是否满足5分钟SLA"""
        return self.total_execution_time <= 300

    @property
    def is_cache_healthy(self) -> bool:
        """缓存是否健康（>60%命中率）"""
        return self.cache_hit_rate_overall >= 60


class ApiEndpointMetrics(BaseModel):
    """Reddit API端点监控"""

    endpoint: str  # 如 "/r/{subreddit}/hot"
    call_count: int = 0
    success_count: int = 0
    error_count: int = 0
    total_latency: float = 0  # 累计延迟（秒）
    last_error: Optional[str] = None
    last_called: Optional[datetime] = None

    @property
    def avg_latency(self) -> float:
        """平均延迟"""
        return self.total_latency / max(self.call_count, 1)

    @property
    def success_rate(self) -> float:
        """成功率"""
        return (self.success_count / max(self.call_count, 1)) * 100


# ==================== 分析引擎专用告警规则 ====================


class AnalysisAlertConfig(AlertConfig):
    """分析引擎告警配置 - 扩展基础告警"""

    analysis_step: Optional[AnalysisStep] = None  # 特定步骤的告警

    @classmethod
    def get_default_rules(cls) -> List["AnalysisAlertConfig"]:
        """PRD要求的默认告警规则"""
        return [
            # 5分钟超时告警
            cls(
                rule_id="analysis_timeout",
                rule_name="分析超时告警",
                condition_type=AlertConditionType.LONG_RUNNING,
                threshold=300.0,  # 5分钟
                comparison="gt",
                severity=AlertSeverity.CRITICAL,
                check_interval=60,
                enabled=True,
            ),
            # 缓存命中率低告警
            cls(
                rule_id="cache_hit_low",
                rule_name="缓存命中率低",
                condition_type=AlertConditionType.HIGH_FAILURE_RATE,
                threshold=60.0,  # 60%
                comparison="lt",
                severity=AlertSeverity.WARNING,
                check_interval=120,
                enabled=True,
            ),
            # API限制预警
            cls(
                rule_id="api_limit_warning",
                rule_name="API配额即将耗尽",
                condition_type=AlertConditionType.QUEUE_BACKLOG,
                threshold=200,  # 剩余200次
                comparison="lt",
                severity=AlertSeverity.WARNING,
                check_interval=60,
                enabled=True,
            ),
        ]


# ==================== 指标收集器 ====================


class AnalysisMetricsCollector:
    """分析引擎指标收集器"""

    def __init__(self) -> None:
        self.current_analysis: Optional[AnalysisPerformanceMetrics] = None
        self.step_start_time: Optional[float] = None
        self.step_start_memory: Optional[float] = None
        self.api_metrics: Dict[str, ApiEndpointMetrics] = {}

    @contextmanager
    def measure_step(
        self, step: AnalysisStep, keyword: str = ""
    ) -> Iterator[StepMetrics]:
        """测量单个步骤的性能"""
        # 记录开始状态（惰性导入，避免缺失 stubs 阻塞 mypy）
        process = psutil_mod.Process() if psutil_mod is not None else None

        self.step_start_time = time.time()
        if process is not None:
            self.step_start_memory = process.memory_info().rss / 1024 / 1024  # MB
        else:
            self.step_start_memory = 0.0

        step_metrics = StepMetrics(step_name=step, execution_time=0, memory_delta=0)

        try:
            yield step_metrics
        finally:
            # 计算性能指标
            step_metrics.execution_time = time.time() - self.step_start_time
            if process is not None:
                current_memory = process.memory_info().rss / 1024 / 1024
                step_metrics.memory_delta = current_memory - cast(
                    float, self.step_start_memory
                )
            else:
                step_metrics.memory_delta = 0.0

            # 存储到当前分析
            if self.current_analysis:
                self.current_analysis.step_metrics[step] = step_metrics

    def record_api_call(self, endpoint: str, success: bool, latency: float) -> None:
        """记录API调用"""
        if endpoint not in self.api_metrics:
            self.api_metrics[endpoint] = ApiEndpointMetrics(endpoint=endpoint)

        metrics = self.api_metrics[endpoint]
        metrics.call_count += 1
        metrics.total_latency += latency
        metrics.last_called = datetime.utcnow()

        if success:
            metrics.success_count += 1
        else:
            metrics.error_count += 1

    def record_cache_operation(self, step: AnalysisStep, hit: bool) -> None:
        """记录缓存操作"""
        if self.current_analysis and step in self.current_analysis.step_metrics:
            metrics = self.current_analysis.step_metrics[step]
            if hit:
                metrics.cache_hits += 1
            else:
                metrics.cache_misses += 1

    def start_analysis(
        self, analysis_id: str, keyword: str
    ) -> AnalysisPerformanceMetrics:
        """开始新的分析监控"""
        self.current_analysis = AnalysisPerformanceMetrics(
            analysis_id=analysis_id,
            keyword=keyword,
            total_execution_time=0,
            step_metrics={},
            cache_hit_rate_overall=0,
            started_at=datetime.utcnow(),
        )
        return self.current_analysis

    def complete_analysis(self) -> Optional[AnalysisPerformanceMetrics]:
        """完成分析监控"""
        if self.current_analysis:
            self.current_analysis.completed_at = datetime.utcnow()
            self.current_analysis.total_execution_time = (
                self.current_analysis.completed_at - self.current_analysis.started_at
            ).total_seconds()

            # 汇总API调用
            self.current_analysis.api_calls_total = sum(
                m.call_count for m in self.api_metrics.values()
            )
            self.current_analysis.api_calls_failed = sum(
                m.error_count for m in self.api_metrics.values()
            )

            result = self.current_analysis
            self.current_analysis = None
            return result
        return None


# ==================== 装饰器工具 ====================


def monitor_analysis_step(step: AnalysisStep) -> Callable[[F], F]:
    """监控分析步骤的装饰器"""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            collector = get_metrics_collector()
            with collector.measure_step(step) as metrics:
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    metrics.error_count += 1
                    raise

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            collector = get_metrics_collector()
            with collector.measure_step(step) as metrics:
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    metrics.error_count += 1
                    raise

        # 根据函数类型返回对应的包装器
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        else:
            return cast(F, sync_wrapper)

    return decorator


# ==================== 全局实例 ====================

_collector_instance: Optional[AnalysisMetricsCollector] = None


def get_metrics_collector() -> AnalysisMetricsCollector:
    """获取全局指标收集器实例"""
    global _collector_instance
    if _collector_instance is None:
        _collector_instance = AnalysisMetricsCollector()
    return _collector_instance
