"""
精简版后台爬虫任务 - PRD03-06 平衡实现

Linus原则：一个任务做好一件事
- 统一爬取逻辑，无类型区分
- 保留API速率限制和基本错误处理
- 专用队列隔离，24/7持续运行
"""

import logging
from datetime import datetime
from typing import Any, Dict, Union, cast

from celery import Task
from sqlalchemy.sql.elements import ColumnElement

from ..core.celery_app import get_celery_app
from ..core.crawler_scheduler import get_scheduler
from ..core.database import get_session_sync
from ..core.types import JsonValue
from ..models.community_cache import CommunityCache
from ..schemas.common.adapters import TransitionResponse

# 新增：Pydantic模型和适配器导入
from ..schemas.responses.crawler import (
    CrawlBatchResponse,
    CrawlerBeatConfigResponse,
    CrawlerStatusResponse,
    adapt_crawl_batch_result,
    adapt_crawler_beat_config,
    adapt_crawler_status,
)
from ..services.cache_updater import get_cache_updater

logger = logging.getLogger(__name__)
celery_app = get_celery_app()

# 配置常量
CRAWLER_QUEUE = "crawler_queue"
TASK_PRIORITY = 6
API_RATE_LIMIT = 15  # 请求/分钟
BATCH_SIZE = 3


class APIRateLimiter:
    """简单的API速率限制器"""

    def __init__(self, max_requests_per_minute: int = 15) -> None:
        self.max_requests = max_requests_per_minute
        self.requests_made = 0
        self.reset_time = datetime.utcnow()

    def can_proceed(self) -> bool:
        """检查是否可以继续请求"""
        now = datetime.utcnow()
        if (now - self.reset_time).seconds >= 60:
            self.requests_made = 0
            self.reset_time = now
        return self.requests_made < self.max_requests

    def record_request(self) -> None:
        """记录一次请求"""
        self.requests_made += 1


def _crawl_batch_typed(self: Task) -> CrawlBatchResponse:
    """类型安全的爬虫批次任务执行 - 新版本

    Returns:
        CrawlBatchResponse: 执行结果统计
    """
    logger.info("开始执行爬虫批次任务")

    try:
        scheduler = get_scheduler(BATCH_SIZE, API_RATE_LIMIT)
        cache_updater = get_cache_updater()
        rate_limiter = APIRateLimiter(API_RATE_LIMIT)

        # 获取需要爬取的社区（已按优先级排序）
        communities = scheduler.get_communities_to_crawl()

        if not communities:
            logger.info("没有需要爬取的社区")
            return CrawlBatchResponse(
                success=True,
                status="success",
                crawled=0,
                total=0,
                timestamp=datetime.utcnow().isoformat(),
            )

        crawled_count = 0
        for community in communities:
            # 检查API速率限制
            if not rate_limiter.can_proceed():
                logger.warning("API速率限制，停止本批次爬取")
                break

            # 统一爬取逻辑：获取最新50个帖子
            success = crawl_community(
                community.community_name, cache_updater, rate_limiter
            )

            if success:
                # 更新爬取时间
                update_crawl_time(community.community_name)
                crawled_count += 1

        logger.info(f"批次完成 - 爬取 {crawled_count}/{len(communities)} 个社区")
        return CrawlBatchResponse(
            success=True,
            status="success",
            crawled=crawled_count,
            total=len(communities),
            failed=len(communities) - crawled_count,
            timestamp=datetime.utcnow().isoformat(),
        )

    except Exception as exc:
        logger.error(f"批次任务失败: {exc}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return CrawlBatchResponse(
            success=False,
            status="failed",
            crawled=0,
            total=0,
            timestamp=datetime.utcnow().isoformat(),
        )


from ..core.types import celery_task


@celery_task(
    bind=True,
    name="tasks.crawler.crawl_batch",
    queue=CRAWLER_QUEUE,
    priority=TASK_PRIORITY,
    max_retries=3,
    default_retry_delay=300,
)
def crawl_batch(self: Task) -> CrawlBatchResponse:
    """爬取批次任务 - 类型安全实现

    迁移到完全类型安全的返回类型，Pydantic模型提供自动序列化支持
    FastAPI自动处理Pydantic模型的JSON序列化，无需手动转换

    Returns:
        CrawlBatchResponse: 执行结果统计（类型安全）
    """
    # 直接返回类型安全的实现
    return _crawl_batch_typed(self)


def crawl_community(
    community_name: str, cache_updater: Any, rate_limiter: APIRateLimiter
) -> bool:
    """爬取单个社区 - 统一逻辑

    Args:
        community_name: 社区名称
        cache_updater: 缓存更新服务
        rate_limiter: API速率限制器

    Returns:
        是否成功
    """
    try:
        # TODO: 集成真实Reddit API客户端
        # from ..services.reddit_client import get_reddit_client
        # reddit = get_reddit_client()
        # posts = reddit.get_posts(community_name, limit=50)

        # 临时Mock数据
        posts = {
            "posts": [
                {"id": f"post_{i}", "title": f"Post {i}", "score": i * 10}
                for i in range(50)
            ],
            "timestamp": datetime.utcnow().isoformat(),
        }

        # 更新缓存
        cache_updater.update_community_posts(community_name, posts)

        # 记录API请求
        rate_limiter.record_request()

        logger.info(f"成功爬取社区: {community_name}")
        return True

    except Exception as e:
        logger.error(f"爬取社区失败 {community_name}: {e}")
        return False


def update_crawl_time(community_name: str) -> None:
    """更新社区爬取时间"""
    try:
        session = get_session_sync()
        community = (
            session.query(CommunityCache)
            .filter(CommunityCache.community_name == community_name)
            .first()
        )

        if community:
            community.last_crawled_at = datetime.utcnow()
            community.hit_count = (community.hit_count or 0) + 1
            session.commit()

        session.close()

    except Exception as e:
        logger.error(f"更新爬取时间失败 {community_name}: {e}")


# Beat配置
def _get_crawler_beat_config_typed() -> CrawlerBeatConfigResponse:
    """
    类型安全的Celery Beat配置生成 - 新版本
    基于Context7研究：使用嵌套Pydantic模型清晰表达配置层次

    Returns:
        CrawlerBeatConfigResponse: 完整的Beat配置模型
    """
    from ..schemas.responses.crawler import (
        BeatTaskConfig,
        CrawlerBeatConfigResponse,
        ScheduleConfig,
        TaskOptions,
    )

    return CrawlerBeatConfigResponse(
        crawler_scheduler=BeatTaskConfig(
            task="tasks.crawler.crawl_batch",
            schedule=ScheduleConfig(minute="*/5"),
            options=TaskOptions(queue=CRAWLER_QUEUE, priority=TASK_PRIORITY),
        )
    )


def get_crawler_beat_config() -> dict[str, JsonValue]:
    """
    获取Celery Beat配置 - 兼容性包装器

    保持原有API接口不变，内部调用类型安全的实现
    确保与Celery框架的完全兼容性

    Returns:
        Dict[str, Any]: Celery Beat标准配置格式
    """
    # 调用类型安全的实现
    config_model = _get_crawler_beat_config_typed()

    # 转换为Celery框架期望的dict格式
    return config_model.to_beat_config()


def _get_crawler_status_typed() -> CrawlerStatusResponse:
    """
    类型安全的爬虫状态获取 - 新版本

    Returns:
        CrawlerStatusResponse: 爬虫状态响应模型
    """
    try:
        scheduler = get_scheduler()
        communities = scheduler.get_communities_to_crawl()

        return CrawlerStatusResponse(
            success=True,
            status="active",
            pending_communities=len(communities),
            queue=CRAWLER_QUEUE,
            timestamp=datetime.utcnow().isoformat(),
        )
    except Exception as e:
        return CrawlerStatusResponse(
            success=False,
            status="error",
            pending_communities=0,
            queue=CRAWLER_QUEUE,
            error_details=str(e),
            timestamp=datetime.utcnow().isoformat(),
        )


@celery_task(name="tasks.crawler.get_status")
def get_crawler_status() -> CrawlerStatusResponse:
    """
    获取爬虫状态 - 类型安全实现

    迁移到完全类型安全的返回类型，Pydantic模型提供自动序列化支持
    FastAPI和Celery都能自动处理Pydantic模型的序列化

    Returns:
        CrawlerStatusResponse: 爬虫状态信息（类型安全）
    """
    # 直接返回类型安全的实现
    return _get_crawler_status_typed()
