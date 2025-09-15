"""
任务相关响应模型 - 替代任务处理中的Dict[str, Any]
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ...core.types import JsonValue
from ..common.base import BaseTaskResponse


class CrawlerTaskResponse(BaseTaskResponse):
    """爬虫任务响应

    替代: crawl_batch() -> Dict[str, Any]
    """

    crawled: int = Field(default=0, description="成功爬取的数量")
    total: int = Field(default=0, description="计划爬取的总数")
    failed: int = Field(default=0, description="失败的数量")
    rate_limited: bool = Field(default=False, description="是否受到速率限制")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "status": "completed",
                "crawled": 8,
                "total": 10,
                "failed": 2,
                "execution_time_seconds": 45.2,
                "rate_limited": False,
                "timestamp": "2025-01-06T12:00:00.000Z",
            }
        }


class CrawlerStatusResponse(BaseModel):
    """爬虫状态响应

    替代: get_crawler_status() -> Dict[str, Any]
    """

    is_running: bool = Field(..., description="是否正在运行")
    active_tasks: int = Field(default=0, description="活跃任务数")
    next_run_time: Optional[str] = Field(default=None, description="下次运行时间")
    last_run_time: Optional[str] = Field(default=None, description="上次运行时间")
    last_run_status: Optional[str] = Field(default=None, description="上次运行状态")
    queue_size: int = Field(default=0, description="队列大小")


class CleanupOperationResponse(BaseTaskResponse):
    """清理操作响应

    替代: data_cleanup_v2各函数 -> Dict[str, Any]
    """

    total_records_cleaned: int = Field(default=0, description="清理的记录总数")
    breakdown: list[dict[str, JsonValue]] = Field(
        default_factory=list, description="清理明细"
    )  # 待进一步细化
    database_stats: dict[str, JsonValue] = Field(
        default_factory=dict, description="数据库统计"
    )  # 待进一步细化
    space_freed_mb: Optional[float] = Field(default=None, description="释放的存储空间（MB）")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "status": "completed",
                "total_records_cleaned": 1250,
                "execution_time_seconds": 12.5,
                "breakdown": [
                    {"table": "posts", "cleaned": 800},
                    {"table": "comments", "cleaned": 450},
                ],
                "database_stats": {"tables_processed": 2, "indexes_rebuilt": 5},
                "space_freed_mb": 45.2,
                "timestamp": "2025-01-06T12:00:00.000Z",
            }
        }


class TaskProgressResponse(BaseModel):
    """任务进度响应"""

    task_id: str = Field(..., description="任务ID")
    progress: float = Field(..., description="进度百分比（0-100）")
    current_step: str = Field(..., description="当前步骤")
    estimated_remaining_seconds: Optional[int] = Field(
        default=None, description="预估剩余时间（秒）"
    )
    details: Optional[dict[str, JsonValue]] = Field(default=None, description="详细信息")


class BatchTaskResponse(BaseModel):
    """批量任务响应"""

    batch_id: str = Field(..., description="批次ID")
    total_tasks: int = Field(..., description="任务总数")
    completed_tasks: int = Field(default=0, description="已完成任务数")
    failed_tasks: int = Field(default=0, description="失败任务数")
    success_rate: float = Field(default=0.0, description="成功率（0-1）")
    results: list[dict[str, JsonValue]] = Field(
        default_factory=list, description="任务结果列表"
    )
