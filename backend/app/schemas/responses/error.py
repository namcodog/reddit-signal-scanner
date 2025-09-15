"""
错误相关响应模型 - 替代错误处理中的Dict[str, Any]
"""

from typing import Dict, Optional

from pydantic import BaseModel, Field

from ...core.types import JsonValue
from ..common.base import BaseStatisticsResponse


class ErrorStatisticsResponse(BaseStatisticsResponse):
    """错误统计响应

    替代: ErrorMiddleware.get_error_statistics() -> Dict[str, Any]
    """

    total_errors: int = Field(default=0, description="错误总数")
    error_breakdown: dict[str, int] = Field(default_factory=dict, description="错误类型统计")
    most_common_error: Optional[str] = Field(default=None, description="最常见的错误类型")
    error_rate: Optional[float] = Field(default=None, description="错误率（0-1之间）")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "total_errors": 42,
                "error_breakdown": {
                    "ValidationError": 25,
                    "DatabaseError": 10,
                    "AuthenticationError": 7,
                },
                "most_common_error": "ValidationError",
                "error_rate": 0.05,
                "total_count": 42,
                "generated_at": "2025-01-06T12:00:00.000Z",
            }
        }


class ErrorDetailResponse(BaseModel):
    """错误详情响应"""

    error_id: str = Field(..., description="错误ID")
    error_type: str = Field(..., description="错误类型")
    error_message: str = Field(..., description="错误消息")
    occurred_at: str = Field(..., description="发生时间")
    client_ip: Optional[str] = Field(default=None, description="客户端IP")
    user_id: Optional[str] = Field(default=None, description="用户ID")
    request_path: Optional[str] = Field(default=None, description="请求路径")
    stack_trace: Optional[str] = Field(default=None, description="堆栈跟踪")


class HealthCheckResponse(BaseModel):
    """健康检查响应"""

    status: str = Field(..., description="健康状态: healthy, degraded, unhealthy")
    checks: dict[str, str] = Field(default_factory=dict, description="各组件检查结果")
    errors: Optional[dict[str, str]] = Field(default=None, description="错误信息")
    uptime: Optional[float] = Field(default=None, description="运行时间（秒）")
    version: Optional[str] = Field(default=None, description="系统版本")
