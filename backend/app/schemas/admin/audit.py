from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AuditRecord(BaseModel):
    timestamp: str = Field(..., description="ISO8601 UTC 时间戳")
    trace_id: Optional[str] = Field(default=None, description="请求跟踪ID")
    user_id: Optional[str] = Field(default=None, description="操作者用户ID")
    path: str = Field(..., description="请求路径")
    method: str = Field(..., description="HTTP 方法")
    action: str = Field(..., description="语义化动作名，例如 community_decision/analysis_feedback/export_patch")
    status_code: int = Field(..., description="响应状态码")

