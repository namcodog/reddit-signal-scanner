"""
Reddit Signal Scanner - 状态查询数据模式

Linus原则："数据结构决定一切"
- 完整的请求/响应类型定义
- 与API模型保持一致，避免重复定义
- 支持客户端轮询指导
- 明确的验证规则和文档
"""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from ..core.types import JsonDict, JsonValue

# ===== 状态查询请求模式 =====


class TaskStatusQueryRequest(BaseModel):
    """任务状态查询请求"""

    task_id: str = Field(..., description="任务ID，UUID格式", min_length=4, max_length=100)

    include_guidance: bool = Field(default=True, description="是否包含轮询指导信息")

    include_runtime_info: bool = Field(default=False, description="是否包含运行时详细信息")

    @field_validator("task_id")
    def validate_task_id_format(cls, v: str) -> str:
        """验证任务ID格式"""
        if not v or len(v.strip()) < 4:
            raise ValueError("任务ID不能为空且长度至少4个字符")
        return v.strip()


class BatchStatusQueryRequest(BaseModel):
    """批量状态查询请求"""

    task_ids: Annotated[
        List[str], Field(description="任务ID列表", min_length=1, max_length=50)
    ]

    limit: int = Field(default=10, description="查询限制数量", ge=1, le=50)

    include_guidance: bool = Field(default=False, description="批量查询时通常不包含指导信息")

    @field_validator("task_ids")
    def validate_task_ids(cls, v: List[str]) -> List[str]:
        """验证任务ID列表"""
        if not v:
            raise ValueError("任务ID列表不能为空")

        # 去重和清理
        cleaned_ids = []
        seen = set()
        for task_id in v:
            if task_id and task_id.strip() and task_id not in seen:
                cleaned_ids.append(task_id.strip())
                seen.add(task_id)

        if not cleaned_ids:
            raise ValueError("任务ID列表不能全部为空")

        return cleaned_ids


# ===== 轮询指导模式 =====


class PollingGuidance(BaseModel):
    """轮询指导配置"""

    should_poll: bool = Field(..., description="是否应该继续轮询")

    interval_ms: Optional[int] = Field(
        default=None, description="建议轮询间隔（毫秒）", ge=500, le=60000
    )

    max_duration_seconds: Optional[int] = Field(
        default=None, description="最大轮询持续时间（秒）", ge=0, le=3600
    )

    timeout_seconds: Optional[int] = Field(
        default=None, description="任务超时时间（秒）", ge=60, le=7200
    )

    reason: str = Field(..., description="轮询建议的原因")

    strategy: Optional[str] = Field(
        default=None, description="建议的轮询策略：fast/normal/slow"
    )


class RetryGuidance(BaseModel):
    """重试指导配置"""

    should_retry: bool = Field(..., description="是否应该重试")

    delay_seconds: Optional[float] = Field(
        default=None, description="重试延迟时间（秒）", ge=0.1, le=300
    )

    max_attempts: int = Field(default=3, description="最大重试次数", ge=0, le=10)

    reason: str = Field(..., description="重试建议的原因")


class ConnectionGuidance(BaseModel):
    """连接测试指导"""

    health_check_url: str = Field(..., description="健康检查URL")
    sse_test_url: str = Field(..., description="SSE测试URL")
    test_sequence: str = Field(..., description="建议的测试顺序")
    fallback_trigger: str = Field(..., description="fallback触发条件")


# ===== 任务状态扩展模式 =====


class TaskRuntimeInfo(BaseModel):
    """任务运行时信息"""

    runtime_seconds: Optional[int] = Field(default=None, description="已运行时间（秒）", ge=0)

    estimated_remaining_seconds: Optional[int] = Field(
        default=None, description="预估剩余时间（秒）", ge=0
    )

    retry_count: int = Field(default=0, description="重试次数", ge=0)

    last_heartbeat: Optional[str] = Field(default=None, description="最后心跳时间")

    worker_id: Optional[str] = Field(default=None, description="处理该任务的工作器ID")


class TaskStatusExtended(BaseModel):
    """扩展的任务状态信息

    基于通用任务模型，但添加了更多状态查询专用字段
    """

    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态")
    progress: int = Field(default=0, ge=0, le=100, description="任务进度百分比")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")
    estimated_completion: Optional[str] = Field(default=None, description="预估完成时间")
    error_message: Optional[str] = Field(default=None, description="错误信息")

    # 状态查询专用扩展字段
    polling_guidance: Optional[PollingGuidance] = Field(
        default=None, description="轮询指导信息"
    )

    runtime_info: Optional[TaskRuntimeInfo] = Field(default=None, description="运行时详细信息")

    fallback_mode: bool = Field(default=False, description="是否为fallback模式")

    fallback_reason: Optional[str] = Field(default=None, description="fallback原因")

    cache_info: Optional[JsonDict] = Field(default=None, description="缓存信息")


# ===== 批量查询结果模式 =====


class TaskStatusSummary(BaseModel):
    """任务状态摘要（用于批量查询）"""

    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态")
    progress: int = Field(default=0, ge=0, le=100, description="任务进度百分比")
    updated_at: str = Field(..., description="更新时间")
    error_message: Optional[str] = Field(default=None, description="错误信息（如果有）")


class BatchStatusResult(BaseModel):
    """批量状态查询结果"""

    total_requested: int = Field(..., description="请求查询的任务总数", ge=0)
    total_processed: int = Field(..., description="实际处理的任务数", ge=0)
    successful_count: int = Field(..., description="成功查询的任务数", ge=0)
    error_count: int = Field(..., description="查询失败的任务数", ge=0)

    tasks: Dict[str, Union[TaskStatusSummary, Dict[str, str]]] = Field(
        ..., description="任务状态结果，成功时为TaskStatusSummary，失败时为错误信息字典"
    )

    batch_optimization: bool = Field(default=False, description="是否使用了批量优化")

    fallback_mode: bool = Field(default=False, description="是否为fallback模式")

    processing_time_ms: Optional[int] = Field(
        default=None, description="处理时间（毫秒）", ge=0
    )


# ===== 状态统计模式 =====


class UserTasksStatistics(BaseModel):
    """用户任务统计信息"""

    user_id: str = Field(..., description="用户ID")

    pending: int = Field(default=0, ge=0, description="待处理任务数")
    running: int = Field(default=0, ge=0, description="运行中任务数")
    completed: int = Field(default=0, ge=0, description="已完成任务数")
    failed: int = Field(default=0, ge=0, description="失败任务数")

    total: int = Field(default=0, ge=0, description="总任务数")

    active_tasks: int = Field(default=0, ge=0, description="活跃任务数（pending + running）")

    last_activity: Optional[str] = Field(default=None, description="最近活动时间")

    @field_validator("total")
    def validate_total(cls, v: int, info: ValidationInfo) -> int:
        """验证总数一致性"""
        # Pydantic v2: 使用 ValidationInfo。info 可能未显式标注 data 属性，采用 getattr 安全获取。
        raw_data = getattr(info, "data", {})
        data: dict[str, object] = raw_data if isinstance(raw_data, dict) else {}

        def to_int(val: object) -> int:
            if isinstance(val, int):
                return val
            if isinstance(val, float):
                return int(val)
            if isinstance(val, str):
                try:
                    return int(val)
                except ValueError:
                    return 0
            return 0

        expected_total = (
            to_int(data.get("pending", 0))
            + to_int(data.get("running", 0))
            + to_int(data.get("completed", 0))
            + to_int(data.get("failed", 0))
        )

        if v != expected_total:
            raise ValueError(f"总数不一致: {v} != {expected_total}")

        return v


# ===== 系统状态模式 =====


class SystemStatusInfo(BaseModel):
    """系统状态信息"""

    active_tasks: int = Field(default=0, ge=0, description="系统活跃任务数")
    queue_size: int = Field(default=0, ge=0, description="任务队列大小")
    worker_count: int = Field(default=0, ge=0, description="活跃工作器数量")

    average_processing_time_seconds: Optional[float] = Field(
        default=None, description="平均处理时间（秒）", ge=0
    )

    success_rate: Optional[float] = Field(
        default=None, description="成功率（0-1）", ge=0, le=1
    )

    system_load: Optional[str] = Field(
        default=None, description="系统负载状态：low/medium/high"
    )

    maintenance_mode: bool = Field(default=False, description="是否为维护模式")


# ===== 错误详情模式 =====


class StatusQueryError(BaseModel):
    """状态查询错误详情"""

    error_code: str = Field(..., description="错误代码")
    error_message: str = Field(..., description="错误消息")
    task_id: Optional[str] = Field(default=None, description="相关任务ID")

    retry_guidance: Optional[RetryGuidance] = Field(default=None, description="重试建议")

    timestamp: str = Field(..., description="错误发生时间")

    context: Optional[JsonDict] = Field(default=None, description="错误上下文信息")


# ===== 响应包装器 =====


class StatusQueryResponse(BaseModel):
    """状态查询响应包装器"""

    success: bool = Field(..., description="查询是否成功")
    timestamp: str = Field(..., description="响应时间")

    data: Optional[
        Union[TaskStatusExtended, BatchStatusResult, UserTasksStatistics]
    ] = Field(default=None, description="响应数据")

    error: Optional[StatusQueryError] = Field(default=None, description="错误信息（失败时）")

    guidance: Optional[JsonDict] = Field(default=None, description="客户端指导信息")


# ===== 验证和转换工具 =====


def validate_task_id_format(task_id: str) -> bool:
    """验证任务ID格式是否有效

    Args:
        task_id: 任务ID

    Returns:
        bool: 是否有效
    """
    if not task_id or not isinstance(task_id, str):
        return False

    task_id = task_id.strip()
    if len(task_id) < 4:
        return False

    # 简单的UUID格式检查
    try:
        from uuid import UUID

        UUID(task_id)
        return True
    except ValueError:
        return False


def create_polling_guidance(
    task_status: str,
    runtime_seconds: Optional[int] = None,
    config: Optional[Any] = None,
) -> PollingGuidance:
    """创建轮询指导信息

    Args:
        task_status: 任务状态
        runtime_seconds: 运行时间
        config: 配置对象

    Returns:
        PollingGuidance: 轮询指导
    """
    from ..core.fallback import get_client_guidance

    guidance = get_client_guidance()
    guidance_dict = guidance.get_polling_guidance(task_status, runtime_seconds)

    # 为静态类型检查做显式转换，防止 JsonValue 导致的类型不匹配
    should_poll_val = guidance_dict.get("should_poll", False)
    should_poll = (
        bool(should_poll_val) if isinstance(should_poll_val, (bool, int)) else False
    )

    interval_val = guidance_dict.get("interval_ms")
    interval_ms: Optional[int] = (
        int(interval_val) if isinstance(interval_val, (int, float)) else None
    )

    max_dur_val = guidance_dict.get("max_duration_seconds")
    max_duration_seconds: Optional[int] = (
        int(max_dur_val) if isinstance(max_dur_val, (int, float)) else None
    )

    timeout_val = guidance_dict.get("timeout_seconds")
    timeout_seconds: Optional[int] = (
        int(timeout_val) if isinstance(timeout_val, (int, float)) else None
    )

    reason_val = guidance_dict.get("reason", "")
    reason: str = str(reason_val) if not isinstance(reason_val, str) else reason_val

    strategy_val = guidance_dict.get("strategy")
    strategy: Optional[str] = strategy_val if isinstance(strategy_val, str) else None

    return PollingGuidance(
        should_poll=should_poll,
        interval_ms=interval_ms,
        max_duration_seconds=max_duration_seconds,
        timeout_seconds=timeout_seconds,
        reason=reason,
        strategy=strategy,
    )
