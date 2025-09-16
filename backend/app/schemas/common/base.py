"""
基础响应模型 - 替代Dict[str, Any]的类型安全方案

基于FastAPI和Pydantic最佳实践：
1. 所有响应使用具体的Pydantic模型
2. 通过继承减少重复代码
3. 保持语义清晰和类型安全
4. 支持自动API文档生成
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ...core.types import JsonValue


class BaseResponse(BaseModel):
    """基础响应模型 - 所有响应的基类"""

    success: bool = Field(default=True, description="操作是否成功")
    message: Optional[str] = Field(default=None, description="响应消息")
    timestamp: Optional[str] = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="响应时间戳",
    )


class BaseTaskResponse(BaseResponse):
    """基础任务响应模型 - 所有任务相关响应的基类"""

    task_id: Optional[str] = Field(default=None, description="任务ID")
    status: str = Field(..., description="任务状态")
    execution_time_seconds: Optional[float] = Field(default=None, description="执行时间（秒）")


class BaseStatusResponse(BaseResponse):
    """基础状态响应模型 - 状态检查响应的基类"""

    health_status: str = Field(..., description="健康状态")
    checked_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="检查时间",
    )


class BaseStatisticsResponse(BaseResponse):
    """基础统计响应模型 - 统计数据响应的基类"""

    total_count: int = Field(default=0, description="总数")
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="统计生成时间",
    )


# 临时过渡类型 - 用于逐步迁移
class TemporaryDictResponse(BaseResponse):
    """临时字典响应 - 用于暂时无法完全定义结构的场景

    注意：这只是过渡方案，应该逐步替换为具体的Pydantic模型
    """

    data: dict[str, JsonValue] = Field(default_factory=dict, description="响应数据")

    class Config:
        # 允许额外字段，但会给出警告
        extra = "allow"
