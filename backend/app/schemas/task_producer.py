"""
任务生产者数据结构 - prd04-02实现
基于Linus设计哲学：统一数据结构，消除特殊情况

核心设计原则：
1. TaskData统一抽象 - 消除任务类型特殊情况
2. 配置驱动队列选择 - 消除硬编码if-else分支
3. 简单数据结构 - 数据结构决定代码复杂度
4. 零特殊情况分支 - 好品味的标志
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import uuid

from pydantic import BaseModel, Field


class TaskSubmissionRequest(BaseModel):
    """
    统一的任务提交请求
    消除任务类型的特殊情况处理
    """

    product_description: str = Field(
        ..., min_length=10, max_length=2000, description="产品描述内容"
    )
    priority: Optional[int] = Field(
        default=1, ge=1, le=5, description="任务优先级(1-5)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="附加元数据"
    )


class TaskSubmissionResponse(BaseModel):
    """
    统一的任务提交响应
    """

    task_id: str = Field(..., description="任务唯一标识")
    status: str = Field(default="queued", description="任务状态")
    queue_name: str = Field(..., description="任务队列名称")
    estimated_start_time: Optional[datetime] = Field(
        default=None, description="预计开始时间"
    )
    submitted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="提交时间"
    )


@dataclass
class TaskData:
    """
    统一的任务数据结构 - 消除所有类型特殊情况

    这是Linus式"好品味"设计的核心：
    - 单一数据结构处理所有任务类型
    - 配置驱动而非代码逻辑驱动
    - 无特殊情况分支
    """

    task_id: str
    task_type: str
    payload: Dict[str, Any]
    priority: int
    queue_name: str
    metadata: Dict[str, Any]
    created_at: datetime

    @classmethod
    def from_request(
        cls,
        request: TaskSubmissionRequest,
        task_type: str = "analysis",
        queue_config: Optional[Dict[str, str]] = None,
    ) -> "TaskData":
        """
        从HTTP请求构造任务数据 - 单一转换点

        消除特殊情况的关键：所有任务都通过同一个转换函数

        Args:
            request: HTTP请求数据
            task_type: 任务类型（当前版本固定为analysis）
            queue_config: 队列配置字典

        Returns:
            TaskData: 统一的任务数据结构
        """
        # 配置驱动的队列选择 - 消除if-else分支
        default_queue_config = {
            "analysis": "analysis_queue",
            "maintenance": "maintenance_queue",
            "cleanup": "cleanup_queue",
            "monitoring": "monitoring_queue",
        }

        queue_config = queue_config or default_queue_config
        queue_name = queue_config.get(task_type, "default_queue")

        # 确保priority为非None的int类型
        priority = request.priority or 1

        return cls(
            task_id=str(uuid.uuid4()),
            task_type=task_type,
            payload={
                "product_description": request.product_description,
                "priority": priority,
                "metadata": request.metadata or {},
            },
            priority=priority,
            queue_name=queue_name,
            metadata=request.metadata or {},
            created_at=datetime.now(timezone.utc),
        )

    def to_celery_kwargs(self) -> Dict[str, Any]:
        """
        转换为Celery任务调用参数

        统一的参数转换，避免每个任务类型的特殊处理

        Returns:
            Dict: Celery send_task所需的参数
        """
        return {
            "args": [self.payload],
            "task_id": self.task_id,
            "queue": self.queue_name,
            "priority": self.priority,
            "kwargs": {
                "task_data": {
                    "task_id": self.task_id,
                    "task_type": self.task_type,
                    "created_at": self.created_at.isoformat(),
                    "metadata": self.metadata,
                }
            },
        }


@dataclass
class TaskConfig:
    """
    任务配置 - Linus修复：Magic Numbers集中管理

    修复前: 超时、重试等参数散落各处
    修复后: 统一配置管理，便于调优和维护
    """

    # 队列映射配置
    queue_mapping: Dict[str, str] = field(
        default_factory=lambda: {
            "analysis": "analysis_queue",
            "batch": "batch_queue",
            "priority": "priority_queue",
            "default": "default_queue",
        }
    )

    # Celery任务配置 - 集中管理所有超时和重试参数
    task_timeout: int = 300  # 5分钟硬超时
    task_soft_timeout: int = 240  # 4分钟软超时
    max_retries: int = 3  # 最大重试次数
    base_retry_delay: int = 60  # 基础重试延迟（秒）

    # 重试延迟序列 - 指数退避策略
    retry_delays: List[int] = field(
        default_factory=lambda: [60, 120, 240]
    )  # 60s, 2min, 4min

    # 任务执行配置
    average_task_duration_minutes: int = 2  # 每个任务平均处理时间（分钟）
    queue_length_threshold: int = 1000  # 队列长度告警阈值

    # 数据库操作配置
    db_connection_timeout: int = 30  # 数据库连接超时（秒）
    db_query_timeout: int = 10  # 数据库查询超时（秒）

    # 性能监控配置
    api_response_time_threshold_ms: int = 200  # API响应时间阈值（毫秒）
    task_failure_rate_threshold: float = 0.05  # 任务失败率阈值（5%）

    @classmethod
    def default_config(cls) -> "TaskConfig":
        """
        创建默认配置

        Returns:
            TaskConfig: 默认任务配置
        """
        return cls()

    @classmethod
    def production_config(cls) -> "TaskConfig":
        """
        生产环境配置 - 更严格的超时和更保守的重试

        Returns:
            TaskConfig: 生产环境任务配置
        """
        return cls(
            task_timeout=600,  # 10分钟
            task_soft_timeout=540,  # 9分钟
            max_retries=5,
            retry_delays=[30, 60, 120, 300, 600],  # 更细粒度的重试策略
            average_task_duration_minutes=3,
            api_response_time_threshold_ms=100,  # 更严格的响应时间要求
        )

    @classmethod
    def development_config(cls) -> "TaskConfig":
        """
        开发环境配置 - 更快的超时用于调试

        Returns:
            TaskConfig: 开发环境任务配置
        """
        return cls(
            task_timeout=120,  # 2分钟
            task_soft_timeout=90,  # 1.5分钟
            max_retries=1,  # 开发环境快速失败
            retry_delays=[10],  # 快速重试
            average_task_duration_minutes=1,
            api_response_time_threshold_ms=500,  # 开发环境较宽松
        )
