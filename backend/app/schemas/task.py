"""
Reddit Signal Scanner - 任务相关的Pydantic模式

PRD02-02 实现的请求响应模式：
- AnalyzeRequest: 分析任务创建请求
- AnalyzeResponse: 分析任务创建响应
- TaskInfo: 任务状态信息
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, validator

# 导入通用响应基类（新架构，无循环依赖）
from .common.responses import ResponseStatus, SuccessResponse


class TaskStatus(str, Enum):
    """任务状态枚举（新架构）"""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AnalyzeRequest(BaseModel):
    """分析请求模型

    PRD02-02要求：
    - product_description字段，10-2000字符限制
    - 恶意输入过滤通过validator实现
    - 快速响应，<200ms
    """

    product_description: str = Field(
        ..., min_length=10, max_length=2000, description="产品或服务描述，10-2000字符"
    )

    @validator("product_description")
    def validate_content(cls, v: str) -> str:
        """内容安全验证 - 过滤恶意输入"""
        import re

        # 去除首尾空白
        v = v.strip()

        # 检查长度（Pydantic已验证，但双重保险）
        if not (10 <= len(v) <= 2000):
            raise ValueError("产品描述长度必须在10-2000字符之间")

        # 过滤HTML标签
        if re.search(r"<[^>]*>", v):
            raise ValueError("产品描述不允许包含HTML标签")

        # 过滤脚本内容
        if re.search(r"(script|javascript|vbscript)", v, re.IGNORECASE):
            raise ValueError("产品描述不允许包含脚本内容")

        # 过滤SQL注入模式
        if re.search(r"(union\s+select|drop\s+table|insert\s+into)", v, re.IGNORECASE):
            raise ValueError("产品描述包含不安全内容")

        return v


class TaskInfo(BaseModel):
    """任务信息模型"""

    task_id: str = Field(..., description="任务ID")
    status: TaskStatus = Field(..., description="任务状态")
    progress: int = Field(default=0, ge=0, le=100, description="任务进度百分比")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")
    estimated_completion: Optional[str] = Field(default=None, description="预估完成时间")
    error_message: Optional[str] = Field(default=None, description="错误信息")


class AnalyzeResponse(SuccessResponse):
    """分析任务创建响应"""

    data: TaskInfo = Field(..., description="任务信息")
