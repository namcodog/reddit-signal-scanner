"""
Reddit Signal Scanner - API数据模型

Linus原则："数据结构决定一切"
- 所有API响应使用统一格式
- 消除特殊情况，统一成功/错误处理
- 类型安全，100%类型注解
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator

# ===== 通用响应格式 =====


class ResponseStatus(str, Enum):
    """响应状态枚举"""

    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"


class BaseResponse(BaseModel):
    """统一响应格式基类 - 消除所有API响应格式的特殊情况"""

    status: ResponseStatus = Field(..., description="响应状态")
    message: str = Field(default="操作成功", description="响应消息")
    timestamp: str = Field(..., description="时间戳，ISO格式")
    request_id: Optional[str] = Field(default=None, description="请求追踪ID")


class SuccessResponse(BaseResponse):
    """成功响应格式"""

    status: ResponseStatus = Field(default=ResponseStatus.SUCCESS)
    data: Optional[Any] = Field(default=None, description="响应数据")


class ErrorResponse(BaseResponse):
    """错误响应格式"""

    status: ResponseStatus = Field(default=ResponseStatus.ERROR)
    error_code: Optional[str] = Field(default=None, description="错误代码")
    error_details: Optional[Dict[str, Any]] = Field(
        default=None, description="错误详情"
    )


class PendingResponse(BaseResponse):
    """异步任务挂起响应"""

    status: ResponseStatus = Field(default=ResponseStatus.PENDING)
    task_id: str = Field(..., description="任务ID")
    estimated_seconds: Optional[int] = Field(
        default=None, description="预估完成时间（秒）"
    )


# ===== 任务相关模型 =====


class TaskStatus(str, Enum):
    """任务状态枚举"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskInfo(BaseModel):
    """任务信息模型"""

    task_id: str = Field(..., description="任务ID")
    status: TaskStatus = Field(..., description="任务状态")
    progress: int = Field(default=0, ge=0, le=100, description="任务进度百分比")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")
    estimated_completion: Optional[str] = Field(
        default=None, description="预估完成时间"
    )
    error_message: Optional[str] = Field(default=None, description="错误信息")


# ===== 分析请求/响应模型 =====


# AnalyzeRequest 已迁移到 schemas/task.py
# 避免重复定义，保持单一数据源


class AnalyzeResponse(SuccessResponse):
    """分析任务创建响应"""

    data: TaskInfo = Field(..., description="任务信息")


# ===== 流式响应模型 =====


class StreamEvent(BaseModel):
    """SSE流事件模型"""

    event: str = Field(..., description="事件类型")
    data: Dict[str, Any] = Field(..., description="事件数据")
    timestamp: str = Field(..., description="事件时间戳")


class ProgressEvent(StreamEvent):
    """进度更新事件"""

    event: str = Field(default="progress")
    data: Dict[str, Union[int, str]] = Field(
        ..., description="进度数据：{progress: int, message: str, stage: str}"
    )


class ErrorEvent(StreamEvent):
    """错误事件"""

    event: str = Field(default="error")
    data: Dict[str, str] = Field(
        ..., description="错误数据：{error_code: str, message: str}"
    )


class CompleteEvent(StreamEvent):
    """完成事件"""

    event: str = Field(default="complete")
    data: Dict[str, Any] = Field(..., description="完成数据：分析结果")


# ===== 报告模型 =====


class InsightItem(BaseModel):
    """洞察项目模型"""

    title: str = Field(..., description="洞察标题")
    content: str = Field(..., description="洞察内容")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度")
    source_count: int = Field(..., ge=0, description="数据源数量")
    tags: List[str] = Field(default=[], description="标签列表")


class SignalReport(BaseModel):
    """信号分析报告模型"""

    task_id: str = Field(..., description="任务ID")
    query: str = Field(..., description="查询关键词")
    total_posts: int = Field(..., ge=0, description="分析帖子总数")
    total_comments: int = Field(..., ge=0, description="分析评论总数")
    analysis_duration: float = Field(..., ge=0, description="分析耗时（秒）")

    # 核心洞察
    key_insights: List[InsightItem] = Field(default=[], description="关键洞察")
    sentiment_summary: Dict[str, float] = Field(default={}, description="情感分析摘要")
    trending_topics: List[str] = Field(default=[], description="趋势话题")
    user_personas: List[Dict[str, Any]] = Field(default=[], description="用户画像")

    # 元数据
    generated_at: str = Field(..., description="报告生成时间")
    data_freshness: str = Field(..., description="数据新鲜度")


class ReportResponse(SuccessResponse):
    """报告响应模型"""

    data: SignalReport = Field(..., description="分析报告")


# ===== 健康检查模型 =====


class HealthStatus(BaseModel):
    """系统健康状态"""

    service: str = Field(default="reddit-signal-scanner")
    status: str = Field(default="healthy")
    version: str = Field(..., description="API版本")
    timestamp: str = Field(..., description="检查时间")
    dependencies: Dict[str, str] = Field(default={}, description="依赖服务状态")


class HealthResponse(SuccessResponse):
    """健康检查响应"""

    data: HealthStatus = Field(..., description="健康状态")
