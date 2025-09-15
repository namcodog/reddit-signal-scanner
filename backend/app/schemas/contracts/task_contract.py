from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, TypedDict

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


class TaskRetryInfo(BaseModel):
    attempt_count: int
    max_retries: int = 3
    last_error: Optional[str] = None
    next_retry_at: Optional[datetime] = None
    exponential_backoff: bool = True


class TaskProcessedData(BaseModel):
    status: TaskStatus
    progress_percentage: int = Field(ge=0, le=100)
    retry_info: Optional[TaskRetryInfo] = None
    # 过渡期保留未严格建模的数据载荷
    result_data: Optional[Dict[str, object]] = None
    processing_time_seconds: Optional[float] = None


class AdditionalStatusData(TypedDict, total=False):
    """任务快照构建时可选的附加数据（缓存与监控途径）。"""

    worker_id: str
    queue_name: str
    retry_count: int
    error_type: str
    error_code: str
    keywords: list[str]
    queue_wait_duration: float
