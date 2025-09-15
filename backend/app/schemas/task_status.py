"""
Reddit Signal Scanner - 任务状态快照数据结构

基于 Pydantic 的类型安全模型定义，用于：
1. Redis缓存数据结构
2. API响应模型
3. 监控指标收集
4. 告警信息结构

设计原则：
- 100%类型覆盖，禁用Any类型
- 数据结构优先，驱动缓存性能
- 支持JSON序列化和高效查询
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union, cast
from uuid import UUID

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

from ..core.task_status import UnifiedTaskStatus
from ..core.types import JsonValue
from .contracts.task_contract import TaskProcessedData, TaskRetryInfo, TaskStatus


class TaskStatusSnapshot(BaseModel):
    """
    任务状态快照 - Redis缓存核心数据结构

    设计目标：
    1. 快速查询，避免频繁数据库访问
    2. 包含所有监控和展示所需信息
    3. 支持高效的批量操作和筛选
    """

    # 基本标识
    task_id: UUID = Field(..., description="任务唯一标识")
    user_id: UUID = Field(..., description="任务所属用户")
    status: UnifiedTaskStatus = Field(..., description="当前统一状态")
    progress: int = Field(0, ge=0, le=100, description="进度百分比")

    # 时间戳信息
    created_at: datetime = Field(..., description="任务创建时间")
    updated_at: datetime = Field(..., description="最后更新时间")
    started_at: Optional[datetime] = Field(None, description="开始处理时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")

    # 执行信息
    worker_id: Optional[str] = Field(None, description="处理的Worker ID")
    queue_name: Optional[str] = Field(None, description="所属队列名称")
    retry_count: int = Field(0, ge=0, description="重试次数")

    # 错误信息
    error_message: Optional[str] = Field(None, description="错误描述信息")
    error_type: Optional[str] = Field(None, description="错误类型分类")
    error_code: Optional[str] = Field(None, description="错误代码")

    # 业务信息预览
    product_description: Optional[str] = Field(
        None, max_length=200, description="产品描述预览"
    )
    keywords: Optional[List[str]] = Field(None, description="关键词列表")

    # 性能指标
    processing_duration: Optional[float] = Field(None, ge=0, description="处理耗时(秒)")
    queue_wait_duration: Optional[float] = Field(None, ge=0, description="队列等待时间(秒)")

    class Config:
        # 支持UUID和datetime的JSON序列化
        json_encoders = {UUID: str, datetime: lambda v: v.isoformat() if v else None}
        # 允许使用枚举值
        use_enum_values = True

    @field_validator("progress", mode="after")
    @classmethod
    def validate_progress_by_status(cls, v: int, info: ValidationInfo) -> int:
        """根据状态验证进度值的合理性"""
        data = getattr(info, "data", {}) or {}
        status = data.get("status")
        if status == UnifiedTaskStatus.COMPLETED and v != 100:
            return 100
        elif status == UnifiedTaskStatus.FAILED and v != 0:
            return 0
        return v

    @field_validator("completed_at", mode="after")
    @classmethod
    def validate_completed_at(
        cls, v: Optional[datetime], info: ValidationInfo
    ) -> Optional[datetime]:
        """验证完成时间的合理性"""
        data = getattr(info, "data", {}) or {}
        status = data.get("status")
        if status == UnifiedTaskStatus.COMPLETED and not v:
            return datetime.now(timezone.utc)
        elif status != UnifiedTaskStatus.COMPLETED:
            return None
        return v

    def to_redis_dict(self) -> Dict[str, str]:
        """转换为Redis Hash存储格式"""
        data = self.dict()
        redis_dict = {}

        for key, value in data.items():
            if value is None:
                continue
            elif isinstance(value, (list, dict)):
                redis_dict[key] = json.dumps(value)
            elif isinstance(value, (UUID, datetime)):
                redis_dict[key] = str(value)
            else:
                redis_dict[key] = str(value)

        return redis_dict

    @classmethod
    def from_redis_dict(cls, redis_data: Dict[str, str]) -> "TaskStatusSnapshot":
        """从Redis Hash数据重建对象"""
        processed_data: dict[str, object] = {}

        for key, value in redis_data.items():
            if key in ["task_id", "user_id"]:
                processed_data[key] = UUID(value)
            elif key.endswith("_at"):
                processed_data[key] = (
                    datetime.fromisoformat(value) if value != "None" else None
                )
            elif key in ["progress", "retry_count"]:
                processed_data[key] = int(value)
            elif key in ["processing_duration", "queue_wait_duration"]:
                processed_data[key] = float(value) if value != "None" else None
            elif key == "keywords":
                processed_data[key] = json.loads(value) if value != "None" else None
            elif key == "status":
                processed_data[key] = UnifiedTaskStatus(value)
            else:
                processed_data[key] = value

        return cls(**cast(dict[str, Any], processed_data))

    def to_processed_contract(self) -> TaskProcessedData:
        """导出契约化的任务处理数据，服务于重试/监控等上层逻辑。"""
        retry_info: Optional[TaskRetryInfo] = None
        if self.retry_count and self.retry_count > 0:
            retry_info = TaskRetryInfo(attempt_count=self.retry_count)

        status_map = {
            "pending": TaskStatus.PENDING,
            "processing": TaskStatus.RUNNING,
            "completed": TaskStatus.SUCCESS,
            "failed": TaskStatus.FAILED,
        }
        mapped = status_map.get(self.status.value, TaskStatus.PENDING)

        return TaskProcessedData(
            status=mapped,
            progress_percentage=self.progress,
            retry_info=retry_info,
            result_data=None,
            processing_time_seconds=self.processing_duration,
        )


class TaskMetrics(BaseModel):
    """任务执行指标统计"""

    # 基本计数
    total_tasks: int = Field(0, ge=0, description="总任务数")
    pending_tasks: int = Field(0, ge=0, description="待处理任务数")
    processing_tasks: int = Field(0, ge=0, description="处理中任务数")
    completed_tasks: int = Field(0, ge=0, description="已完成任务数")
    failed_tasks: int = Field(0, ge=0, description="失败任务数")

    # 性能指标
    avg_processing_time: float = Field(0.0, ge=0, description="平均处理时间(秒)")
    avg_queue_wait_time: float = Field(0.0, ge=0, description="平均队列等待时间(秒)")
    success_rate: float = Field(0.0, ge=0, le=1, description="成功率")
    throughput_per_hour: float = Field(0.0, ge=0, description="每小时吞吐量")

    # 队列状态
    queue_lengths: Dict[str, int] = Field(default_factory=dict, description="各队列长度")
    active_workers: int = Field(0, ge=0, description="活跃Worker数量")

    # 统计时间范围
    metrics_window_start: datetime = Field(..., description="统计窗口开始时间")
    metrics_window_end: datetime = Field(..., description="统计窗口结束时间")

    @model_validator(mode="after")
    def compute_success_rate(self) -> "TaskMetrics":
        """根据 completed/total 计算成功率"""
        try:
            completed = int(self.completed_tasks)
            total = int(self.total_tasks)
        except Exception:
            completed, total = 0, 0
        self.success_rate = completed / total if total > 0 else 0.0
        return self


class TaskQuery(BaseModel):
    """任务查询参数模型"""

    # 过滤条件
    user_id: Optional[UUID] = Field(None, description="用户ID过滤")
    status: Optional[UnifiedTaskStatus] = Field(None, description="状态过滤")
    worker_id: Optional[str] = Field(None, description="Worker ID过滤")
    queue_name: Optional[str] = Field(None, description="队列名称过滤")

    # 分页参数
    limit: int = Field(10, ge=1, le=100, description="返回数量限制")
    offset: int = Field(0, ge=0, description="分页偏移量")

    # 时间范围过滤
    created_after: Optional[datetime] = Field(None, description="创建时间起始")
    created_before: Optional[datetime] = Field(None, description="创建时间截止")
    updated_after: Optional[datetime] = Field(None, description="更新时间起始")
    updated_before: Optional[datetime] = Field(None, description="更新时间截止")

    # 排序参数
    sort_by: str = Field("updated_at", description="排序字段")
    sort_order: str = Field("desc", pattern="^(asc|desc)$", description="排序方向")

    @field_validator("created_before", mode="after")
    @classmethod
    def validate_time_range(
        cls, v: Optional[datetime], info: ValidationInfo
    ) -> Optional[datetime]:
        """验证时间范围的合理性"""
        data = getattr(info, "data", {}) or {}
        created_after = data.get("created_after")
        if (
            v
            and created_after
            and isinstance(created_after, datetime)
            and v <= created_after
        ):
            raise ValueError("结束时间必须晚于开始时间")
        return v

    def to_cache_key(self) -> str:
        """生成查询缓存键"""
        key_parts = []
        if self.user_id:
            key_parts.append(f"user:{self.user_id}")
        if self.status:
            key_parts.append(f"status:{self.status.value}")
        if self.worker_id:
            key_parts.append(f"worker:{self.worker_id}")

        key_suffix = f"limit:{self.limit}:offset:{self.offset}"
        return f"task_query:{'_'.join(key_parts)}:{key_suffix}"


class TaskAlert(BaseModel):
    """任务告警信息模型"""

    # 告警基本信息
    alert_id: str = Field(..., description="告警唯一ID")
    alert_type: str = Field(..., description="告警类型")
    severity: str = Field(
        ..., pattern="^(info|warning|error|critical)$", description="严重级别"
    )

    # 关联对象
    task_id: Optional[UUID] = Field(None, description="相关任务ID")
    user_id: Optional[UUID] = Field(None, description="相关用户ID")
    worker_id: Optional[str] = Field(None, description="相关Worker ID")
    queue_name: Optional[str] = Field(None, description="相关队列名称")

    # 告警内容
    title: str = Field(..., max_length=100, description="告警标题")
    message: str = Field(..., max_length=500, description="告警详细信息")

    # 时间信息
    created_at: datetime = Field(..., description="告警产生时间")
    updated_at: Optional[datetime] = Field(None, description="告警更新时间")
    resolved_at: Optional[datetime] = Field(None, description="告警解决时间")

    # 状态标识
    is_resolved: bool = Field(False, description="是否已解决")
    is_acknowledged: bool = Field(False, description="是否已确认")

    # 告警上下文数据
    context: Dict[str, str] = Field(default_factory=dict, description="告警上下文数据")

    class Config:
        json_encoders = {UUID: str, datetime: lambda v: v.isoformat() if v else None}


class WorkerHealth(BaseModel):
    """Worker健康状态模型"""

    # Worker基本信息
    worker_id: str = Field(..., description="Worker唯一ID")
    hostname: str = Field(..., description="主机名称")
    status: str = Field(
        ..., pattern="^(online|offline|busy|idle)$", description="Worker状态"
    )

    # 负载统计
    active_tasks: int = Field(0, ge=0, description="当前处理任务数")
    processed_tasks: int = Field(0, ge=0, description="累计处理任务数")
    failed_tasks: int = Field(0, ge=0, description="累计失败任务数")

    # 资源使用情况
    cpu_usage: float = Field(0.0, ge=0, le=1, description="CPU使用率(0-1)")
    memory_usage_mb: float = Field(0.0, ge=0, description="内存使用量(MB)")
    disk_usage_percent: float = Field(0.0, ge=0, le=100, description="磁盘使用率(%)")

    # 时间信息
    last_heartbeat: datetime = Field(..., description="最后心跳时间")
    started_at: datetime = Field(..., description="Worker启动时间")
    uptime_seconds: int = Field(0, ge=0, description="运行时长(秒)")

    # 队列信息
    assigned_queues: List[str] = Field(default_factory=list, description="分配的队列列表")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}

    @field_validator("uptime_seconds", mode="before")
    @classmethod
    def calculate_uptime(cls, v: int, info: ValidationInfo) -> int:
        """计算Worker运行时长"""
        data = getattr(info, "data", {}) or {}
        started_at = data.get("started_at")
        if started_at and isinstance(started_at, datetime):
            return int((datetime.now(timezone.utc) - started_at).total_seconds())
        return v

    def is_healthy(self, heartbeat_timeout: int = 300) -> bool:
        """判断Worker是否健康"""
        if self.status == "offline":
            return False

        # 检查心跳超时
        last_heartbeat_age = (
            datetime.now(timezone.utc) - self.last_heartbeat
        ).total_seconds()
        if last_heartbeat_age > heartbeat_timeout:
            return False

        # 检查资源使用率
        if self.cpu_usage > 0.95 or self.memory_usage_mb > 1024 * 8:  # 8GB限制
            return False

        return True


class TaskStatusBatchUpdate(BaseModel):
    """批量更新任务状态的请求模型"""

    updates: List[Dict[str, Union[str, int, float]]] = Field(..., description="批量更新项列表")

    @field_validator("updates")
    @classmethod
    def validate_updates(
        cls, v: List[Dict[str, Union[str, int, float]]]
    ) -> List[Dict[str, Union[str, int, float]]]:
        """验证批量更新数据格式"""
        for update in v:
            if "task_id" not in update:
                raise ValueError("每个更新项必须包含task_id")
            if "status" not in update:
                raise ValueError("每个更新项必须包含status")
        return v


class TaskStatusResponse(BaseModel):
    """API响应模型"""

    success: bool = Field(..., description="请求是否成功")
    data: Optional[
        Union[TaskStatusSnapshot, List[TaskStatusSnapshot], TaskMetrics]
    ] = Field(None, description="响应数据")
    message: Optional[str] = Field(None, description="响应消息")
    total_count: Optional[int] = Field(None, description="总数据量(用于分页)")

    class Config:
        json_encoders = {UUID: str, datetime: lambda v: v.isoformat() if v else None}
