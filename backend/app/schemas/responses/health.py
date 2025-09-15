"""
健康检查响应模型（新架构）

目的：替代 legacy app/api/models.py 中的 HealthStatus/HealthResponse
"""

from pydantic import BaseModel, Field

from ...schemas.common.responses import SuccessResponse


class HealthStatus(BaseModel):
    """系统健康状态"""

    service: str = Field(default="reddit-signal-scanner")
    status: str = Field(default="healthy")
    version: str = Field(..., description="API版本")
    timestamp: str = Field(..., description="检查时间")
    dependencies: dict[str, str] = Field(default={}, description="依赖服务状态")


class HealthResponse(SuccessResponse):
    """健康检查响应"""

    data: HealthStatus = Field(..., description="健康状态")
