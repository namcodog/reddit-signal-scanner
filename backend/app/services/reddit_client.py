"""
Reddit Signal Scanner - Reddit API客户端

PRD-03 缓存优先架构的API补充组件
基于Linus设计原则：简洁、可靠、限制明确

核心职责：
- 提供Reddit API的简洁封装
- 严格的速率限制管理（<20请求/分钟）
- 统一的错误处理和重试机制
- 与缓存系统的无缝集成
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Mapping, Optional

import aiohttp
from aiohttp import ClientSession, ClientTimeout
from pathlib import Path
import importlib.util

from ..core.config import get_settings
from ..schemas.reddit_data import RedditPost

logger = logging.getLogger(__name__)


@dataclass
class APIRateLimit:
    """API速率限制状态管理"""

    requests_per_minute: int = 20  # PRD-03要求：远低于60次/分钟限制
    request_interval: float = field(default_factory=lambda: 60.0 / 20)  # 3秒间隔
    last_request_time: float = 0.0
    requests_made: int = 0
    reset_time: float = 0.0

    def can_make_request(self) -> bool:
        """检查是否可以发起API请求"""
        current_time = time.time()

        # 重置计数器（每分钟）
        if current_time - self.reset_time >= 60:
            self.requests_made = 0
            self.reset_time = current_time

        # 检查请求频率限制
        if current_time - self.last_request_time < self.request_interval:
            return False

        # 检查总请求数限制
        if self.requests_made >= self.requests_per_minute:
            return False

        return True

    def record_request(self) -> None:
        """记录API请求"""
        self.last_request_time = time.time()
        self.requests_made += 1

    def time_until_next_request(self) -> float:
        """计算距离下次可请求的时间（秒）"""
        interval_wait = self.request_interval - (time.time() - self.last_request_time)
        return max(0, interval_wait)


class RedditAPIClient:
    """Reddit API客户端

    基于PRD-03要求的精准API补充策略：
    - 仅在缓存不足时调用API
    - 严格限制请求频率（<20/分钟）
    - 统一的数据格式转换
    - 完整的错误处理和降级
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.rate_limiter = APIRateLimit()
        self.session: Optional[ClientSession] = None
        self.base_url = "https://www.reddit.com"

        # OAuth配置（如果需要）
        self.client_id = getattr(self.settings, "REDDIT_CLIENT_ID", None)
        self.client_secret = getattr(self.settings, "REDDIT_CLIENT_SECRET", None)
        self.user_agent = "RedditSignalScanner/1.0 by cache_first_architecture"

    async def __aenter__(self) -> "RedditAPIClient":
        """异步上下文管理器入口"""
        timeout = ClientTimeout(total=30, connect=10)
        headers = {"User-Agent": self.user_agent}

        self.session = aiohttp.ClientSession(timeout=timeout, headers=headers)
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()

    async def close(self) -> None:
        """显式关闭客户端"""
        if self.session:
            await self.session.close()

    async def get_community_posts(
        self,
        subreddit: str,
        limit: int = 100,
        time_filter: str = "day",
        sort: str = "hot",
    ) -> List[RedditPost]:
        """获取社区帖子数据

        Args:
            subreddit: 社区名称（不含r/前缀）
            limit: 帖子数量限制
            time_filter: 时间过滤器 ('day', 'week', 'month')
            sort: 排序方式 ('hot', 'new', 'top')

        Returns:
            List[RedditPost]: 帖子列表

        Raises:
            APIRateLimitError: 超出速率限制
            APIRequestError: API请求失败
        """
        if not self.session:
            raise RuntimeError("RedditAPIClient 未初始化，请使用 async with 语句")

        # 速率限制检查
        if not self.rate_limiter.can_make_request():
            wait_time = self.rate_limiter.time_until_next_request()
            logger.warning(f"API速率限制，需等待 {wait_time:.1f} 秒")
            await asyncio.sleep(wait_time)

        try:
            # 构建API URL
            clean_subreddit = subreddit.replace("r/", "").strip("/")
            url = f"{self.base_url}/r/{clean_subreddit}/{sort}.json"

            params: dict[str, str | int | float] = {
                "limit": min(limit, 100),  # Reddit API限制
                "t": time_filter,
                "raw_json": 1,  # 避免HTML实体编码
            }

            # 记录请求
            self.rate_limiter.record_request()

            logger.debug(f"API请求: {url}, 参数: {params}")

            # 发起请求
            async with self.session.get(url, params=params) as response:
                if response.status == 429:
                    # Reddit返回的速率限制
                    raise APIRateLimitError("Reddit API速率限制")

                if response.status == 403:
                    raise APIRequestError(f"访问被禁止: r/{clean_subreddit}")

                if response.status == 404:
                    raise APIRequestError(f"社区不存在: r/{clean_subreddit}")

                if response.status != 200:
                    raise APIRequestError(f"API请求失败: {response.status}")

                data = await response.json()
                return self._parse_reddit_response(data, clean_subreddit)

        except asyncio.TimeoutError:
            raise APIRequestError("API请求超时")
        except aiohttp.ClientError as e:
            raise APIRequestError(f"网络请求失败: {str(e)}")
        except json.JSONDecodeError as e:
            raise APIRequestError(f"API响应解析失败: {str(e)}")

    def _parse_reddit_response(
        self, data: Mapping[str, Any], subreddit: str
    ) -> List[RedditPost]:
        """解析Reddit API响应数据

        将Reddit的复杂JSON结构转换为统一的RedditPost模型
        """
        posts: List[RedditPost] = []

        try:
            if not data or "data" not in data:
                logger.warning(f"无效的Reddit API响应: {subreddit}")
                return posts

            children = data["data"].get("children", [])

            for child in children:
                if child.get("kind") != "t3":  # t3 = 帖子类型
                    continue

                post_data = child.get("data", {})

                # 基础数据验证
                if not post_data.get("id") or not post_data.get("title"):
                    continue

                try:
                    # 构建RedditPost对象
                    post = RedditPost(
                        id=post_data["id"],
                        community=f"r/{subreddit}",
                        title=post_data["title"],
                        content=post_data.get("selftext", ""),
                        author=post_data.get("author", "[deleted]"),
                        created_utc=int(post_data.get("created_utc", 0)),
                        score=int(post_data.get("score", 0)),
                        num_comments=int(post_data.get("num_comments", 0)),
                        url=post_data.get("url", ""),
                        flair_text=post_data.get("link_flair_text"),
                        is_deleted=(post_data.get("author") == "[deleted]"),
                        is_removed=(post_data.get("removed_by_category") is not None),
                        upvote_ratio=float(post_data.get("upvote_ratio", 0.5)),
                        permalink=post_data.get("permalink", ""),
                        domain=post_data.get("domain", ""),
                        is_self=bool(post_data.get("is_self", False)),
                        selftext_html=post_data.get("selftext_html"),
                        distinguished=post_data.get("distinguished"),
                        stickied=bool(post_data.get("stickied", False)),
                    )

                    posts.append(post)

                except (KeyError, ValueError, TypeError) as e:
                    logger.warning(
                        f"解析帖子数据失败 {post_data.get('id', 'unknown')}: {str(e)}"
                    )
                    continue

        except (KeyError, TypeError, ValueError) as e:
            logger.error(f"解析Reddit响应失败 {subreddit}: {str(e)}")

        logger.info(f"成功解析 r/{subreddit} 的 {len(posts)} 个帖子")
        return posts

    async def check_subreddit_exists(self, subreddit: str) -> bool:
        """检查社区是否存在

        Args:
            subreddit: 社区名称

        Returns:
            bool: 社区是否存在
        """
        try:
            posts = await self.get_community_posts(subreddit, limit=1)
            return True
        except APIRequestError as e:
            if "不存在" in str(e) or "404" in str(e):
                return False
            raise

    async def get_community_info(self, subreddit: str) -> Optional[Mapping[str, Any]]:
        """获取社区基本信息

        Args:
            subreddit: 社区名称

        Returns:
            Dict: 社区信息，如果获取失败则返回None
        """
        if not self.session:
            raise RuntimeError("RedditAPIClient 未初始化")

        # 速率限制检查
        if not self.rate_limiter.can_make_request():
            wait_time = self.rate_limiter.time_until_next_request()
            await asyncio.sleep(wait_time)

        try:
            clean_subreddit = subreddit.replace("r/", "").strip("/")
            url = f"{self.base_url}/r/{clean_subreddit}/about.json"

            self.rate_limiter.record_request()

            async with self.session.get(url) as response:
                if response.status != 200:
                    return None

                data = await response.json()

                if "data" not in data:
                    return None

                community_data = data["data"]

                return {
                    "name": community_data.get("display_name", ""),
                    "description": community_data.get("public_description", ""),
                    "subscribers": community_data.get("subscribers", 0),
                    "active_users": community_data.get("active_user_count", 0),
                    "created_utc": community_data.get("created_utc", 0),
                    "is_over18": community_data.get("over18", False),
                    "lang": community_data.get("lang", "en"),
                }

        except asyncio.TimeoutError as e:
            logger.error(f"获取社区信息超时 r/{subreddit}: {str(e)}")
            return None
        except aiohttp.ClientError as e:
            logger.error(f"获取社区信息网络异常 r/{subreddit}: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"获取社区信息解析失败 r/{subreddit}: {str(e)}")
            return None


# 异常类定义
class APIRateLimitError(Exception):
    """API速率限制异常"""

    pass


class APIRequestError(Exception):
    """API请求异常"""

    pass


# 工厂函数
from typing import cast


async def create_reddit_client() -> RedditAPIClient:
    """创建Reddit API客户端的工厂函数"""
    settings = get_settings()
    if getattr(settings, "use_mocks", True):
        # 动态加载测试目录中的 Mock 客户端
        tests_mock_path = (
            Path(__file__).resolve().parents[2]
            / "tests"
            / "mocks"
            / "reddit_client_mock.py"
        )
        if tests_mock_path.exists():
            spec = importlib.util.spec_from_file_location(
                "reddit_client_mock", str(tests_mock_path)
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                MockClient = getattr(module, "RedditAPIClientMock")
                client = cast(RedditAPIClient, MockClient())
            else:
                client = RedditAPIClient()
        else:
            client = RedditAPIClient()
    else:
        client = RedditAPIClient()
    await client.__aenter__()
    return client
