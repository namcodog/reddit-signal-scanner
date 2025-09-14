"""
任务监控系统数据模型 - 基于Linus原则的清晰设计

核心设计原则：
1. 数据结构决定一切 - 清晰的模型定义
2. 消除特殊情况 - 统一的事件流
3. 类型安全 - 100%类型覆盖
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator

from app.core.task_status import UnifiedTaskStatus

from ..core.types import JsonValue

# ==================== 核心枚举类型 ====================


class AlertSeverity(str, Enum):
    """告警严重级别"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertConditionType(str, Enum):
    """告警条件类型"""

    LONG_RUNNING = "long_running"  # 长时间运行
    WORKER_DOWN = "worker_down"  # Worker宕机
    QUEUE_BACKLOG = "queue_backlog"  # 队列积压
    HIGH_FAILURE_RATE = "high_failure_rate"  # 高失败率
    MEMORY_HIGH = "memory_high"  # 内存占用高
    CPU_HIGH = "cpu_high"  # CPU占用高


class MetricType(str, Enum):
    """监控指标类型"""

    TASK_COUNT = "task_count"
    TASK_DURATION = "task_duration"
    SUCCESS_RATE = "success_rate"
    QUEUE_SIZE = "queue_size"
    WORKER_COUNT = "worker_count"
    SYSTEM_RESOURCE = "system_resource"


# ==================== 核心数据模型 ====================


class TaskEvent(BaseModel):
    """
    统一任务事件模型 - 所有状态变更都是事件
    消除特殊情况：不区分创建、更新、完成，统一为事件
    """

    task_id: str = Field(..., description="任务ID")
    event_type: str = Field(..., description="事件类型")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    old_status: Optional[UnifiedTaskStatus] = None
    new_status: UnifiedTaskStatus
    user_id: Optional[str] = None
    worker_id: Optional[str] = None
    queue_name: str = Field(default="default")
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    error_message: Optional[str] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class TaskSnapshot(BaseModel):
    """
    任务快照 - 某一时刻的任务状态
    用于Redis缓存和快速查询
    """

    task_id: str
    status: UnifiedTaskStatus
    progress: int = Field(ge=0, le=100, default=0)
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    user_id: Optional[str] = None
    worker_id: Optional[str] = None
    queue_name: str = "default"
    retry_count: int = 0
    result_summary: Optional[dict[str, JsonValue]] = None

    @validator("progress")
    def validate_progress(cls, v: int, values: dict[str, JsonValue]) -> int:
        """根据状态自动计算进度"""
        if "status" in values:
            status = values["status"]
            if status == UnifiedTaskStatus.PENDING:
                return 0
            elif status == UnifiedTaskStatus.COMPLETED:
                return 100
            elif status == UnifiedTaskStatus.FAILED:
                return v  # 保留失败时的进度
        return v

    def to_cache_dict(self) -> Dict[str, str]:
        """转换为Redis存储格式"""
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "progress": str(self.progress),
            "updated_at": self.updated_at.isoformat(),
            "user_id": self.user_id or "",
            "worker_id": self.worker_id or "",
            "queue_name": self.queue_name,
        }

    @classmethod
    def from_cache_dict(cls, data: Dict[str, str]) -> "TaskSnapshot":
        """从Redis数据恢复"""
        return cls(
            task_id=data["task_id"],
            status=UnifiedTaskStatus(data["status"]),
            progress=int(data.get("progress", 0)),
            created_at=datetime.fromisoformat(
                data.get("created_at", datetime.now(timezone.utc).isoformat())
            ),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            user_id=data.get("user_id") or None,
            worker_id=data.get("worker_id") or None,
            queue_name=data.get("queue_name", "default"),
        )


class WorkerStatus(BaseModel):
    """Worker健康状态 - 简化设计，只保留必要字段"""

    worker_id: str
    hostname: str
    is_alive: bool
    last_heartbeat: datetime
    active_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    cpu_percent: float = Field(ge=0, le=100, default=0)
    memory_percent: float = Field(ge=0, le=100, default=0)
    started_at: datetime

    @property
    def uptime_seconds(self) -> int:
        """计算运行时间（秒）"""
        now = datetime.now(timezone.utc)
        started = (
            self.started_at
            if self.started_at.tzinfo is not None
            else self.started_at.replace(tzinfo=timezone.utc)
        )
        return int((now - started).total_seconds())

    @property
    def is_healthy(self) -> bool:
        """判断Worker是否健康（3分钟内有心跳）"""
        now = datetime.now(timezone.utc)
        last = (
            self.last_heartbeat
            if self.last_heartbeat.tzinfo is not None
            else self.last_heartbeat.replace(tzinfo=timezone.utc)
        )
        time_since_heartbeat = (now - last).total_seconds()
        return self.is_alive and time_since_heartbeat < 180


class QueueMetrics(BaseModel):
    """队列指标 - 实时队列状态"""

    queue_name: str
    pending_count: int = 0
    processing_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    avg_processing_time: float = 0  # 秒
    max_processing_time: float = 0  # 秒
    oldest_task_age: float = 0  # 秒
    measured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total_count(self) -> int:
        """总任务数"""
        return self.pending_count + self.processing_count

    @property
    def success_rate(self) -> float:
        """成功率"""
        total_finished = self.completed_count + self.failed_count
        if total_finished == 0:
            return 0.0
        return (self.completed_count / total_finished) * 100


class AlertConfig(BaseModel):
    """告警配置 - 配置驱动的告警规则"""

    rule_id: str
    rule_name: str
    condition_type: AlertConditionType
    threshold: float
    comparison: str = Field(pattern="^(gt|gte|lt|lte|eq)$")  # 比较操作符
    severity: AlertSeverity = AlertSeverity.WARNING
    check_interval: int = Field(ge=10, le=3600, default=60)  # 秒
    cooldown_period: int = Field(ge=60, le=3600, default=300)  # 冷却期（秒）
    enabled: bool = True
    notification_channels: List[str] = Field(default_factory=list)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    def check_condition(self, value: float) -> bool:
        """检查是否满足告警条件"""
        if self.comparison == "gt":
            return value > self.threshold
        elif self.comparison == "gte":
            return value >= self.threshold
        elif self.comparison == "lt":
            return value < self.threshold
        elif self.comparison == "lte":
            return value <= self.threshold
        elif self.comparison == "eq":
            return value == self.threshold
        return False


class Alert(BaseModel):
    """告警实例 - 触发的告警记录"""

    alert_id: str
    rule_id: str
    rule_name: str
    severity: AlertSeverity
    condition_type: AlertConditionType
    triggered_at: datetime
    resolved_at: Optional[datetime] = None
    current_value: float
    threshold_value: float
    message: str
    context: dict[str, JsonValue] = Field(default_factory=dict)
    is_active: bool = True

    @property
    def duration_seconds(self) -> Optional[int]:
        """告警持续时间"""
        if self.resolved_at:
            return int((self.resolved_at - self.triggered_at).total_seconds())
        return None


# ==================== 查询请求和响应模型 ====================


class TaskQueryRequest(BaseModel):
    """任务查询请求"""

    user_id: Optional[str] = None
    status: Optional[UnifiedTaskStatus] = None
    queue_name: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = Field(ge=1, le=1000, default=100)
    offset: int = Field(ge=0, default=0)


class TaskQueryResponse(BaseModel):
    """任务查询响应"""

    tasks: List[TaskSnapshot]
    total: int
    limit: int
    offset: int


class TaskStatsRequest(BaseModel):
    """任务统计请求"""

    user_id: Optional[str] = None
    queue_name: Optional[str] = None
    period: str = Field(pattern="^(hour|day|week|month)$", default="day")
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class TaskStatsResponse(BaseModel):
    """任务统计响应"""

    total_tasks: int
    pending_tasks: int
    processing_tasks: int
    completed_tasks: int
    failed_tasks: int
    success_rate: float
    avg_processing_time: float
    max_processing_time: float
    period: str
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SystemHealthResponse(BaseModel):
    """系统健康状态响应"""

    workers: List[WorkerStatus]
    queues: List[QueueMetrics]
    active_alerts: List[Alert]
    total_workers: int
    healthy_workers: int
    total_queues: int
    system_status: str  # healthy, degraded, critical
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def health_score(self) -> int:
        """计算健康分数（0-100）"""
        if self.total_workers == 0:
            return 0
        worker_score = (self.healthy_workers / self.total_workers) * 50
        alert_penalty = min(len(self.active_alerts) * 10, 50)
        return max(0, int(worker_score + 50 - alert_penalty))


# ==================== WebSocket推送模型 ====================


class MonitoringUpdate(BaseModel):
    """监控更新推送消息"""

    update_type: str  # task_status, worker_status, queue_metrics, alert
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: dict[str, JsonValue]

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
