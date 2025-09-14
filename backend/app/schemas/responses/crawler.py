"""
爬虫相关响应模型
专门为background_crawler.py中的Dict[str, Any]替换而设计
"""

from typing import Any, Dict, Mapping, Optional

from pydantic import BaseModel, Field

from ...core.types import JsonValue
from ..common.base import BaseResponse, BaseTaskResponse


# -----------------------------
# 本地类型收敛助手（仅本文件使用）
# -----------------------------
def as_str(v: object, default: str = "") -> str:
    if isinstance(v, str):
        return v
    if v is None:
        return default
    return str(v)


def as_optional_str(v: object) -> Optional[str]:
    if v is None:
        return None
    return as_str(v)


def as_int(v: object, default: int = 0) -> int:
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    if isinstance(v, str):
        try:
            return int(v)
        except ValueError:
            try:
                return int(float(v))
            except ValueError:
                return default
    return default


def as_float(v: object, default: float = 0.0) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return default
    if isinstance(v, bool):
        return float(int(v))
    return default


def as_bool(v: object, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        return v.strip().lower() in {"1", "true", "yes", "on"}
    return default


def as_mapping(v: object) -> Mapping[str, JsonValue]:
    if isinstance(v, Mapping):
        return v
    return {}


class CrawlBatchResponse(BaseTaskResponse):
    """
    爬虫批次执行结果响应模型
    替换 crawl_batch() 函数的 Dict[str, Any] 返回值
    """

    crawled: int = Field(..., description="成功爬取的社区数量", ge=0)
    total: int = Field(..., description="计划爬取的总社区数", ge=0)
    failed: int = Field(default=0, description="失败的爬取数量", ge=0)
    rate_limited: bool = Field(default=False, description="是否遇到API速率限制")

    @property
    def success_rate(self) -> float:
        """计算成功率"""
        if self.total == 0:
            return 1.0
        return self.crawled / self.total


# 基于Context7研究，为Celery Beat配置建模的正确方式
class ScheduleConfig(BaseModel):
    """Celery Beat调度配置"""

    minute: str = Field(..., description="分钟调度表达式，如'*/5'")


class TaskOptions(BaseModel):
    """Celery任务选项配置"""

    queue: str = Field(..., description="任务队列名称")
    priority: int = Field(..., description="任务优先级")


class BeatTaskConfig(BaseModel):
    """单个Celery Beat任务配置"""

    task: str = Field(..., description="任务模块路径")
    schedule: ScheduleConfig = Field(..., description="调度配置")
    options: TaskOptions = Field(..., description="任务选项")


class CrawlerBeatConfigResponse(BaseModel):
    """
    Celery Beat配置响应模型 - 完整的配置结构
    替换 get_crawler_beat_config() 函数的 Dict[str, Any] 返回值
    基于Context7最佳实践：分离validation和serialization，使用标准Python字段名
    """

    crawler_scheduler: BeatTaskConfig = Field(
        serialization_alias="crawler-scheduler", description="爬虫调度任务配置"
    )

    def to_beat_config(self) -> dict[str, JsonValue]:
        """
        转换为Celery Beat标准配置格式
        确保完全兼容Celery框架要求
        """
        return self.model_dump(by_alias=True, mode="json")


class CrawlerStatusResponse(BaseResponse):
    """
    爬虫状态响应模型
    替换 get_crawler_status() 函数的 Dict[str, Any] 返回值
    """

    status: str = Field(..., description="爬虫状态", pattern="^(active|inactive|error)$")
    pending_communities: int = Field(..., description="待爬取社区数量", ge=0)
    queue: str = Field(..., description="任务队列名称")
    error_details: Optional[str] = Field(default=None, description="错误详情（如果有）")
    last_crawl_time: Optional[str] = Field(default=None, description="最后一次爬取时间")

    @property
    def is_healthy(self) -> bool:
        """检查爬虫是否健康"""
        return self.status == "active" and self.error_details is None


# 兼容性适配器函数
def adapt_crawl_batch_result(data: dict[str, JsonValue]) -> CrawlBatchResponse:
    """
    将旧的dict格式转换为CrawlBatchResponse
    确保向后兼容性
    """
    # 处理成功状态
    status_val = as_str(data.get("status", ""))
    success = status_val == "success"

    # 提取基本字段
    crawled_i = as_int(data.get("crawled", 0))
    total_i = as_int(data.get("total", 0))
    timestamp_s = as_optional_str(data.get("timestamp"))

    # 推断失败数量（如果有total信息）
    failed_i = max(0, total_i - crawled_i) if total_i > 0 else 0

    return CrawlBatchResponse(
        success=success,
        task_id=as_optional_str(data.get("task_id")),
        status=status_val or "unknown",
        timestamp=timestamp_s,
        crawled=crawled_i,
        total=total_i,
        failed=failed_i,
        rate_limited=as_bool(data.get("rate_limited", False)),
    )


def adapt_crawler_beat_config(data: dict[str, JsonValue]) -> CrawlerBeatConfigResponse:
    """
    将旧的Beat配置dict转换为CrawlerBeatConfigResponse
    基于Context7最佳实践：保持向后兼容的同时提供类型安全
    """
    # 期望的数据格式：{"crawler-scheduler": {...}}
    scheduler_config = as_mapping(data.get("crawler-scheduler", {}))

    if not scheduler_config:
        # 提供默认配置以防数据结构异常
        scheduler_config = {
            "task": "tasks.crawler.crawl_batch",
            "schedule": {"minute": "*/5"},
            "options": {"queue": "crawler", "priority": 5},
        }

    return CrawlerBeatConfigResponse(
        crawler_scheduler=BeatTaskConfig(
            task=as_str(
                scheduler_config.get("task", "tasks.crawler.crawl_batch"),
                "tasks.crawler.crawl_batch",
            ),
            schedule=ScheduleConfig(
                minute=as_str(
                    as_mapping(scheduler_config.get("schedule", {})).get(
                        "minute", "*/5"
                    ),
                    "*/5",
                )
            ),
            options=TaskOptions(
                queue=as_str(
                    as_mapping(scheduler_config.get("options", {})).get(
                        "queue", "crawler"
                    ),
                    "crawler",
                ),
                priority=as_int(
                    as_mapping(scheduler_config.get("options", {})).get("priority", 5),
                    5,
                ),
            ),
        )
    )


def adapt_crawler_status(data: dict[str, JsonValue]) -> CrawlerStatusResponse:
    """
    将旧的状态dict转换为CrawlerStatusResponse
    """
    status_s = as_str(data.get("status", ""))
    return CrawlerStatusResponse(
        success=status_s != "error",
        timestamp=as_optional_str(data.get("timestamp")),
        status=status_s or "unknown",
        pending_communities=as_int(data.get("pending_communities", 0)),
        queue=as_str(data.get("queue", "default"), "default"),
        error_details=as_optional_str(data.get("error")),
    )
