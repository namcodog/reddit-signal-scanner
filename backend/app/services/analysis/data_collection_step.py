"""
桥接模块：tests 仍引用 app.services.analysis.data_collection_step
实际实现位于 app/services/analysis/data_collector.py
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict, List

from .data_collector import DataCollectionStep as _BaseDataCollectionStep
from app.schemas.reddit_data import RedditPost


class RateLimiter:
    def __init__(
        self, max_requests_per_minute: int = 60, min_interval_seconds: float = 0.0
    ) -> None:
        self.max_per_min = max_requests_per_minute
        self.min_interval = min_interval_seconds
        self._last_time = 0.0
        self._made = 0
        self._window_start = time.time()

    async def wait_if_needed(self) -> None:
        now = time.time()
        # reset window each minute
        if now - self._window_start >= 60:
            self._window_start = now
            self._made = 0

        # enforce per-request interval
        since_last = now - self._last_time
        if since_last < self.min_interval:
            await asyncio.sleep(self.min_interval - since_last)

        # enforce per-minute cap
        if self._made >= self.max_per_min:
            await asyncio.sleep(max(0.0, 60 - (now - self._window_start)))
            self._window_start = time.time()
            self._made = 0

        self._last_time = time.time()
        self._made += 1


class DataValidator:
    REQUIRED_FIELDS = {
        "id",
        "title",
        "selftext",
        "author",
        "created_utc",
        "score",
        "num_comments",
    }

    def validate_reddit_post(self, post: Dict[str, Any]) -> bool:
        return self.REQUIRED_FIELDS.issubset(set(post.keys()))


class DataCollectionStep(_BaseDataCollectionStep):
    async def _fetch_reddit_posts(
        self, community: str
    ) -> List[Dict[str, Any]]:  # pragma: no cover (mocked in tests)
        return []

    def _filter_quality_posts(
        self, posts: List[RedditPost], min_score: int, min_comments: int
    ) -> List[RedditPost]:
        return [
            p
            for p in posts
            if int(getattr(p, "score", 0)) >= min_score
            and int(getattr(p, "num_comments", 0)) >= min_comments
        ]


__all__ = ["DataCollectionStep", "RedditPost", "DataValidator", "RateLimiter"]
