"""
精简版爬虫调度器 - PRD03-06 平衡实现

Linus原则：数据结构决定算法，消除特殊情况
- 基于现有community_cache表，零Schema变更
- 保留priority_score排序（PRD核心需求）
- 统一爬取逻辑，无类型区分
"""

import logging
from typing import List

from sqlalchemy import or_, text

from ..core.database import get_session_sync
from ..core.sqlalchemy_typing import as_bool_clause
from ..models.community_cache import CommunityCache

logger = logging.getLogger(__name__)


class SimpleCrawlerScheduler:
    """精简爬虫调度器 - 50行核心逻辑"""

    def __init__(self, batch_size: int = 3, api_rate_limit: int = 15) -> None:
        """初始化调度器

        Args:
            batch_size: 每批爬取的社区数量
            api_rate_limit: API速率限制（请求/分钟）
        """
        self.batch_size = batch_size
        self.api_rate_limit = api_rate_limit

    def get_communities_to_crawl(self) -> List[CommunityCache]:
        """获取需要爬取的社区列表 - 保留优先级排序

        Returns:
            按priority_score排序的过期社区列表
        """
        try:
            session = get_session_sync()

            # 查询过期或未爬取的社区
            # 关键：保留priority_score排序以满足PRD需求
            communities = (
                session.query(CommunityCache)
                .filter(
                    as_bool_clause(
                        or_(
                            CommunityCache.last_crawled_at == None,  # noqa: E711
                            text(
                                "EXTRACT(EPOCH FROM "
                                "(CURRENT_TIMESTAMP - last_crawled_at)) > ttl_seconds"
                            ),
                        )
                    )
                )
                .order_by(CommunityCache.crawl_priority.desc())  # 优先级排序
                .limit(self.batch_size)
                .all()
            )

            # 按priority_score二次排序（如果有自定义算法）
            if communities and hasattr(communities[0], "get_priority_score"):
                communities.sort(key=lambda x: x.get_priority_score(), reverse=True)

            logger.info(f"找到 {len(communities)} 个需要爬取的社区")
            return communities

        except Exception as e:
            logger.error(f"获取爬取社区列表失败: {e}")
            return []
        finally:
            session.close()


# 工厂函数
def get_scheduler(
    batch_size: int = 3, api_rate_limit: int = 15
) -> SimpleCrawlerScheduler:
    """获取调度器实例"""
    return SimpleCrawlerScheduler(batch_size, api_rate_limit)
