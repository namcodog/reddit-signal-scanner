from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, List, Mapping, Optional

from app.schemas.reddit_data import RedditPost


class RedditAPIClientMock:
    """Reddit API 的最小可用 Mock，实现与真实客户端一致的方法签名。"""

    def __init__(self) -> None:
        self._closed = False

    async def __aenter__(self) -> "RedditAPIClientMock":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self._closed = True

    async def close(self) -> None:
        self._closed = True

    async def get_community_posts(
        self,
        subreddit: str,
        limit: int = 100,
        time_filter: str = "day",
        sort: str = "hot",
    ) -> List[RedditPost]:
        # 返回稳定的、可预测的模拟数据
        clean = subreddit.replace("r/", "").strip("/")
        posts: List[RedditPost] = []
        for i in range(min(limit, 5)):
            posts.append(
                RedditPost(
                    id=f"mock_{clean}_{i}",
                    community=f"r/{clean}",
                    title=f"Mock Post {i} in r/{clean}",
                    content="This is mock content",
                    author="mock_author",
                    created_utc=0,
                    score=100 + i,
                    num_comments=10 + i,
                    url=f"https://reddit.com/r/{clean}/mock/{i}",
                    flair_text=None,
                    is_deleted=False,
                    is_removed=False,
                    upvote_ratio=0.9,
                    permalink=f"/r/{clean}/mock/{i}",
                    domain="reddit.com",
                    is_self=True,
                    selftext_html=None,
                    distinguished=None,
                    stickied=False,
                )
            )
        # 模拟网络延迟
        await asyncio.sleep(0)
        return posts

    async def check_subreddit_exists(self, subreddit: str) -> bool:
        await asyncio.sleep(0)
        return True

    async def get_community_info(self, subreddit: str) -> Optional[Mapping[str, Any]]:
        clean = subreddit.replace("r/", "").strip("/")
        await asyncio.sleep(0)
        return {
            "name": clean,
            "description": "Mock community",
            "subscribers": 12345,
            "active_users": 123,
            "created_utc": 0,
            "is_over18": False,
            "lang": "en",
        }

