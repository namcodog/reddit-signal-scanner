"""
通用响应模型（新架构）

目的：
- 逐步替换 legacy `app/api/models.py` 中的通用响应定义
- 为 `schemas/*` 提供独立的、无循环依赖的响应基类

注意：
- 这是过渡阶段的文件。完成全量迁移后，将统一以本文件为单一来源。
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ResponseStatus(str, Enum):
    """统一响应状态枚举"""

    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"


class BaseResponse(BaseModel):
    """统一响应格式基类"""

    status: ResponseStatus = Field(..., description="响应状态")
    message: str = Field(default="操作成功", description="响应消息")
    timestamp: str = Field(..., description="时间戳（ISO格式）")
    request_id: Optional[str] = Field(default=None, description="请求追踪ID")


class SuccessResponse(BaseResponse):
    """成功响应格式"""

    status: ResponseStatus = Field(default=ResponseStatus.SUCCESS)
    data: Optional[Any] = Field(default=None, description="响应数据")
