"""
数据收集步骤单元测试 - 类型安全版本
测试Reddit数据收集和验证功能
"""

import pytest
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import asyncio

from app.services.analysis.data_collection_step import (
    DataCollectionStep,
    RedditPost,
    DataValidator,
    RateLimiter,
)
from app.models.analysis_pipeline import PipelineData, StepStatus
from app.core.analyzer_config import StepConfig

from .test_base import (
    create_test_pipeline_data,
    create_test_step_config,
    assert_pipeline_result,
)


class TestDataCollectionStep:
    """测试数据收集步骤"""

    @pytest.fixture
    def step_config(self) -> StepConfig:
        """创建步骤配置"""
        config = create_test_step_config("data_collection")
        config.config_data = {
            "max_posts_per_community": 100,
            "max_concurrent_requests": 3,
            "request_timeout": 30,
        }
        return config

    @pytest.fixture
    def step_instance(self, step_config: StepConfig) -> DataCollectionStep:
        """创建步骤实例"""
        return DataCollectionStep(step_config)

    @pytest.fixture
    def mock_communities(self) -> List[Dict[str, Any]]:
        """模拟社区数据"""
        return [
            {"name": "r/python", "subscribers": 1000000, "relevance_score": 0.9},
            {"name": "r/learnpython", "subscribers": 500000, "relevance_score": 0.8},
        ]

    @pytest.fixture
    def mock_reddit_posts(self) -> List[Dict[str, Any]]:
        """模拟Reddit帖子数据"""
        return [
            {
                "id": "post1",
                "title": "Python tips for beginners",
                "selftext": "Here are some useful Python tips",
                "author": "user1",
                "created_utc": 1234567890,
                "score": 150,
                "num_comments": 25,
                "subreddit": "python",
                "url": "https://reddit.com/r/python/post1",
                "upvote_ratio": 0.95,
            },
            {
                "id": "post2",
                "title": "Best Python libraries 2024",
                "selftext": "A comprehensive list of Python libraries",
                "author": "user2",
                "created_utc": 1234567900,
                "score": 500,
                "num_comments": 100,
                "subreddit": "python",
                "url": "https://reddit.com/r/python/post2",
                "upvote_ratio": 0.98,
            },
        ]

    @pytest.mark.asyncio
    async def test_process_step_success(
        self,
        step_instance: DataCollectionStep,
        mock_communities: List[Dict[str, Any]],
        mock_reddit_posts: List[Dict[str, Any]],
    ) -> None:
        """测试成功处理步骤"""
        # 准备测试数据
        pipeline_data = create_test_pipeline_data()
        pipeline_data.intermediate_results["community_discovery"] = {
            "communities": mock_communities
        }

        # Mock Reddit API
        with patch.object(
            step_instance, "_fetch_reddit_posts", return_value=mock_reddit_posts
        ):
            result = await step_instance._process_step(pipeline_data)

        # 验证结果
        assert_pipeline_result(result, StepStatus.COMPLETED, True)
        assert "reddit_posts" in result.data
        assert len(result.data["reddit_posts"]) == 2
        assert result.data["total_collected"] == 2
        assert result.data["communities_processed"] == 2

    @pytest.mark.asyncio
    async def test_process_step_no_communities(
        self, step_instance: DataCollectionStep
    ) -> None:
        """测试无社区数据处理"""
        pipeline_data = create_test_pipeline_data()
        # 没有社区发现结果

        result = await step_instance._process_step(pipeline_data)

        assert_pipeline_result(result, StepStatus.FAILED, False)
        assert "error" in result.data
        assert "社区" in result.data["error"]

    @pytest.mark.asyncio
    async def test_rate_limiting(self, step_instance: DataCollectionStep) -> None:
        """测试速率限制功能"""
        rate_limiter = RateLimiter(max_requests_per_minute=60, min_interval_seconds=1.0)

        # 模拟快速请求
        start_time = datetime.utcnow()
        for i in range(3):
            await rate_limiter.wait_if_needed()
            await asyncio.sleep(0.1)  # 模拟请求时间

        elapsed = (datetime.utcnow() - start_time).total_seconds()
        assert elapsed >= 2.0  # 应该至少等待2秒

    def test_validate_post_data(self, step_instance: DataCollectionStep) -> None:
        """测试帖子数据验证"""
        validator = DataValidator()

        # 有效帖子
        valid_post = {
            "id": "test123",
            "title": "Valid title",
            "selftext": "Valid content",
            "author": "user1",
            "created_utc": 1234567890,
            "score": 100,
            "num_comments": 10,
            "subreddit": "test",
        }
        assert validator.validate_reddit_post(valid_post) is True

        # 缺少必需字段
        invalid_post = {"id": "test123", "title": "Missing fields"}
        assert validator.validate_reddit_post(invalid_post) is False

    def test_filter_quality_posts(
        self, step_instance: DataCollectionStep, mock_reddit_posts: List[Dict[str, Any]]
    ) -> None:
        """测试帖子质量过滤"""
        posts = [RedditPost(**post) for post in mock_reddit_posts]

        # 添加低质量帖子
        low_quality_post = RedditPost(
            id="low_quality",
            title="[deleted]",
            content="[removed]",
            author="[deleted]",
            created_utc=1234567890,
            score=0,
            comment_count=0,
            subreddit="test",
            url="",
            upvote_ratio=0.5,
        )
        posts.append(low_quality_post)

        filtered = step_instance._filter_quality_posts(
            posts, min_score=10, min_comments=5
        )

        assert len(filtered) == 2  # 只保留高质量帖子
        assert all(p.score >= 10 for p in filtered)
        assert all(p.comment_count >= 5 for p in filtered)

    @pytest.mark.asyncio
    async def test_concurrent_collection(
        self, step_instance: DataCollectionStep, mock_communities: List[Dict[str, Any]]
    ) -> None:
        """测试并发数据收集"""
        pipeline_data = create_test_pipeline_data()
        pipeline_data.intermediate_results["community_discovery"] = {
            "communities": mock_communities * 5  # 10个社区
        }

        call_count = 0

        async def mock_fetch(community: str) -> List[Dict[str, Any]]:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # 模拟API延迟
            return [{"id": f"post_{call_count}", "title": f"Post {call_count}"}]

        with patch.object(step_instance, "_fetch_reddit_posts", mock_fetch):
            start_time = datetime.utcnow()
            result = await step_instance._process_step(pipeline_data)
            elapsed = (datetime.utcnow() - start_time).total_seconds()

        assert result.success
        assert call_count == 10
        # 并发执行应该比串行快
        assert elapsed < 1.0  # 10个请求并发应该在1秒内完成


@pytest.mark.integration
class TestDataCollectionIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_full_collection_flow(self) -> None:
        """测试完整的数据收集流程"""
        config = create_test_step_config("data_collection")
        step = DataCollectionStep(config)

        # 准备完整的管道数据
        pipeline_data = create_test_pipeline_data()
        pipeline_data.intermediate_results["community_discovery"] = {
            "communities": [
                {"name": f"r/community_{i}", "subscribers": 10000 * (i + 1)}
                for i in range(3)
            ]
        }

        # Mock所有Reddit API调用
        async def mock_fetch(community: str) -> List[Dict[str, Any]]:
            return [
                {
                    "id": f"{community}_post_{i}",
                    "title": f"Post {i} in {community}",
                    "selftext": f"Content for post {i}",
                    "author": f"user_{i}",
                    "created_utc": 1234567890 + i,
                    "score": 100 + i * 10,
                    "num_comments": 10 + i,
                    "subreddit": community.replace("r/", ""),
                    "url": f"https://reddit.com/{community}/post_{i}",
                    "upvote_ratio": 0.9,
                }
                for i in range(5)
            ]

        with patch.object(step, "_fetch_reddit_posts", mock_fetch):
            result = await step._process_step(pipeline_data)

        assert result.success
        assert result.data["total_collected"] == 15  # 3社区 * 5帖子
        assert result.data["communities_processed"] == 3
        assert "collection_stats" in result.data
