"""
数据收集系统单元测试 - PRD03-08
验证缓存优先+API补充的混合数据源策略

严格类型安全：
- 禁止Any类型
- 100% mypy --strict兼容
- 禁止type: ignore
"""

import pytest
import asyncio
from typing import Dict, List, Optional, Union
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
import redis

from app.services.analysis.data_collector import DataCollectionStep
from app.models.analysis_pipeline import PipelineData
from app.core.step_base import StepResult, StepConfig
from app.core.redis_client import get_redis


class TestDataCollectionStrategy:
    """数据收集策略测试"""

    @pytest.fixture
    def step_config(self) -> StepConfig:
        """步骤配置"""
        return StepConfig(
            max_duration=30,
            enabled=True,
            params={
                "cache_enabled": True,
                "cache_ttl": 3600,  # 1小时
                "api_rate_limit": 100,  # 每分钟100次
                "batch_size": 10,
            },
        )

    @pytest.fixture
    def data_collector(self, step_config: StepConfig) -> DataCollectionStep:
        """创建数据收集步骤实例"""
        return DataCollectionStep(step_config)

    @pytest.fixture
    def pipeline_data_with_communities(self) -> PipelineData:
        """包含社区发现结果的流水线数据"""
        data = PipelineData(
            product_description="Test product", pipeline_id="test-collection-001"
        )

        # 添加社区发现结果
        data.step_results["community_discovery"] = {
            "communities": [
                {"name": "r/startup", "relevance_score": {"final_score": 0.95}},
                {"name": "r/SaaS", "relevance_score": {"final_score": 0.90}},
                {"name": "r/entrepreneur", "relevance_score": {"final_score": 0.85}},
                {"name": "r/technology", "relevance_score": {"final_score": 0.75}},
                {"name": "r/business", "relevance_score": {"final_score": 0.70}},
            ]
        }

        return data

    @pytest.mark.asyncio
    async def test_cache_first_strategy(
        self,
        data_collector: DataCollectionStep,
        pipeline_data_with_communities: PipelineData,
    ) -> None:
        """测试缓存优先策略"""
        # Mock Redis客户端
        mock_redis = Mock()
        mock_redis.get = Mock(return_value=b'{"posts": [{"title": "Cached post"}]}')
        mock_redis.exists = Mock(return_value=1)
        mock_redis.ttl = Mock(return_value=1800)  # 还有30分钟过期

        with patch(
            "app.services.analysis.data_collector.get_redis", return_value=mock_redis
        ):
            result = await data_collector.process(pipeline_data_with_communities)

            assert result.success
            assert "posts" in result.data
            assert "cache_hit_rate" in result.data

            # 验证缓存命中率
            cache_hit_rate = result.data["cache_hit_rate"]
            assert cache_hit_rate > 0  # 有缓存命中

            # 验证Redis被查询
            assert mock_redis.get.called
            assert mock_redis.exists.called

    @pytest.mark.asyncio
    async def test_api_fallback_on_cache_miss(
        self,
        data_collector: DataCollectionStep,
        pipeline_data_with_communities: PipelineData,
    ) -> None:
        """测试缓存未命中时的API回退"""
        # Mock Redis返回空
        mock_redis = Mock()
        mock_redis.get = Mock(return_value=None)
        mock_redis.exists = Mock(return_value=0)
        mock_redis.setex = Mock()

        # Mock API客户端
        mock_api_response = {
            "posts": [
                {"title": "Fresh API post", "score": 100},
                {"title": "Another fresh post", "score": 200},
            ]
        }

        with patch(
            "app.services.analysis.data_collector.get_redis", return_value=mock_redis
        ):
            with patch.object(
                data_collector, "_fetch_from_api", return_value=mock_api_response
            ):
                result = await data_collector.process(pipeline_data_with_communities)

                assert result.success
                assert result.data["cache_hit_rate"] < 1.0  # 不是100%缓存命中
                assert result.data["api_calls"] > 0  # 有API调用

                # 验证数据被缓存
                assert mock_redis.setex.called

    @pytest.mark.asyncio
    async def test_mixed_cache_api_data(
        self,
        data_collector: DataCollectionStep,
        pipeline_data_with_communities: PipelineData,
    ) -> None:
        """测试缓存和API混合数据源"""
        # 模拟部分缓存命中
        cache_responses = {
            "r/startup": b'{"posts": [{"title": "Cached startup post"}]}',
            "r/SaaS": None,  # 缓存未命中
            "r/entrepreneur": b'{"posts": [{"title": "Cached entrepreneur post"}]}',
            "r/technology": None,  # 缓存未命中
            "r/business": b'{"posts": [{"title": "Cached business post"}]}',
        }

        mock_redis = Mock()
        mock_redis.get = Mock(
            side_effect=lambda key: cache_responses.get(key.decode().split(":")[-1])
        )
        mock_redis.exists = Mock(
            side_effect=lambda key: 1
            if cache_responses.get(key.decode().split(":")[-1])
            else 0
        )
        mock_redis.setex = Mock()

        api_call_count = 0

        async def mock_api_fetch(
            subreddit: str,
        ) -> Dict[str, List[Dict[str, Union[str, int]]]]:
            nonlocal api_call_count
            api_call_count += 1
            return {"posts": [{"title": f"API post for {subreddit}", "score": 100}]}

        with patch(
            "app.services.analysis.data_collector.get_redis", return_value=mock_redis
        ):
            with patch.object(
                data_collector, "_fetch_from_api", side_effect=mock_api_fetch
            ):
                result = await data_collector.process(pipeline_data_with_communities)

                assert result.success

                # 验证混合数据源
                cache_hit_rate = result.data["cache_hit_rate"]
                assert 0 < cache_hit_rate < 1  # 部分缓存命中
                assert cache_hit_rate == pytest.approx(0.6, 0.1)  # 约60%命中率

                # 验证API只为缓存未命中的调用
                assert api_call_count == 2  # r/SaaS 和 r/technology

    @pytest.mark.asyncio
    async def test_rate_limiting_compliance(
        self,
        data_collector: DataCollectionStep,
        pipeline_data_with_communities: PipelineData,
    ) -> None:
        """测试API速率限制遵守"""
        # 添加更多社区以触发速率限制
        communities = [
            {"name": f"r/sub_{i}", "relevance_score": {"final_score": 0.8}}
            for i in range(50)
        ]
        pipeline_data_with_communities.step_results["community_discovery"][
            "communities"
        ] = communities

        api_calls_times: List[float] = []

        async def track_api_calls(
            subreddit: str,
        ) -> Dict[str, List[Dict[str, Union[str, int]]]]:
            api_calls_times.append(asyncio.get_event_loop().time())
            await asyncio.sleep(0.01)  # 模拟API延迟
            return {"posts": []}

        mock_redis = Mock()
        mock_redis.get = Mock(return_value=None)  # 全部缓存未命中
        mock_redis.exists = Mock(return_value=0)
        mock_redis.setex = Mock()

        with patch(
            "app.services.analysis.data_collector.get_redis", return_value=mock_redis
        ):
            with patch.object(
                data_collector, "_fetch_from_api", side_effect=track_api_calls
            ):
                data_collector.config.params["api_rate_limit"] = 10  # 降低限制以便测试

                result = await data_collector.process(pipeline_data_with_communities)

                assert result.success

                # 验证速率限制
                if len(api_calls_times) > 10:
                    # 计算每10个调用的时间窗口
                    for i in range(10, len(api_calls_times)):
                        time_window = api_calls_times[i] - api_calls_times[i - 10]
                        assert time_window >= 1.0  # 至少1秒内不超过10个调用

    @pytest.mark.asyncio
    async def test_cache_freshness_validation(
        self,
        data_collector: DataCollectionStep,
        pipeline_data_with_communities: PipelineData,
    ) -> None:
        """测试缓存新鲜度验证"""
        # 模拟不同新鲜度的缓存
        cache_data = {
            "r/startup": (
                b'{"posts": [], "cached_at": "2024-01-01T00:00:00"}',
                60,
            ),  # 1分钟后过期
            "r/SaaS": (
                b'{"posts": [], "cached_at": "2024-01-01T00:00:00"}',
                3000,
            ),  # 50分钟后过期
        }

        mock_redis = Mock()
        mock_redis.get = Mock(
            side_effect=lambda key: cache_data.get(
                key.decode().split(":")[-1], (None, 0)
            )[0]
        )
        mock_redis.ttl = Mock(
            side_effect=lambda key: cache_data.get(
                key.decode().split(":")[-1], (None, 0)
            )[1]
        )
        mock_redis.exists = Mock(
            side_effect=lambda key: key.decode().split(":")[-1] in cache_data
        )
        mock_redis.setex = Mock()

        with patch(
            "app.services.analysis.data_collector.get_redis", return_value=mock_redis
        ):
            result = await data_collector.process(pipeline_data_with_communities)

            assert result.success

            # 验证新鲜度评分
            freshness_score = result.data.get("freshness_score", 0)
            assert 0 <= freshness_score <= 1

            # TTL短的缓存应该降低新鲜度分数
            assert freshness_score < 0.5  # 因为有即将过期的缓存

    @pytest.mark.asyncio
    async def test_batch_processing_efficiency(
        self,
        data_collector: DataCollectionStep,
        pipeline_data_with_communities: PipelineData,
    ) -> None:
        """测试批量处理效率"""
        # 大量社区
        communities = [
            {"name": f"r/sub_{i}", "relevance_score": {"final_score": 0.8}}
            for i in range(100)
        ]
        pipeline_data_with_communities.step_results["community_discovery"][
            "communities"
        ] = communities

        batch_sizes: List[int] = []

        async def track_batch_size(
            *subreddits: str,
        ) -> Dict[str, Dict[str, List[Dict[str, Union[str, int]]]]]:
            batch_sizes.append(len(subreddits))
            return {sub: {"posts": []} for sub in subreddits}

        mock_redis = Mock()
        mock_redis.get = Mock(return_value=None)
        mock_redis.exists = Mock(return_value=0)
        mock_redis.mget = Mock(return_value=[None] * 10)  # 批量获取
        mock_redis.pipeline = Mock()

        with patch(
            "app.services.analysis.data_collector.get_redis", return_value=mock_redis
        ):
            with patch.object(
                data_collector, "_batch_fetch_from_api", side_effect=track_batch_size
            ):
                data_collector.config.params["batch_size"] = 10

                result = await data_collector.process(pipeline_data_with_communities)

                assert result.success

                # 验证批量处理
                assert len(batch_sizes) > 0
                assert max(batch_sizes) <= 10  # 不超过配置的批量大小
                assert sum(batch_sizes) >= len(communities)  # 处理了所有社区

    @pytest.mark.asyncio
    async def test_error_recovery_mechanism(
        self,
        data_collector: DataCollectionStep,
        pipeline_data_with_communities: PipelineData,
    ) -> None:
        """测试错误恢复机制"""
        # 模拟间歇性故障
        call_count = 0

        async def flaky_api_fetch(
            subreddit: str,
        ) -> Dict[str, List[Dict[str, Union[str, int]]]]:
            nonlocal call_count
            call_count += 1

            if call_count % 3 == 0:
                raise ConnectionError("API temporarily unavailable")

            return {"posts": [{"title": f"Post from {subreddit}"}]}

        mock_redis = Mock()
        mock_redis.get = Mock(return_value=None)
        mock_redis.exists = Mock(return_value=0)
        mock_redis.setex = Mock()

        with patch(
            "app.services.analysis.data_collector.get_redis", return_value=mock_redis
        ):
            with patch.object(
                data_collector, "_fetch_from_api", side_effect=flaky_api_fetch
            ):
                with patch.object(data_collector, "_retry_with_backoff") as mock_retry:
                    mock_retry.return_value = {"posts": []}

                    result = await data_collector.process(
                        pipeline_data_with_communities
                    )

                    assert result.success
                    assert mock_retry.called  # 重试机制被触发

                    # 验证部分数据仍然被收集
                    assert len(result.data.get("posts", {})) > 0

    @pytest.mark.asyncio
    async def test_data_deduplication(
        self,
        data_collector: DataCollectionStep,
        pipeline_data_with_communities: PipelineData,
    ) -> None:
        """测试数据去重"""
        # 模拟包含重复的数据
        duplicate_posts = [
            {"id": "post1", "title": "First post", "score": 100},
            {"id": "post2", "title": "Second post", "score": 200},
            {"id": "post1", "title": "First post", "score": 100},  # 重复
            {"id": "post3", "title": "Third post", "score": 150},
            {"id": "post2", "title": "Second post", "score": 200},  # 重复
        ]

        mock_redis = Mock()
        mock_redis.get = Mock(return_value=None)
        mock_redis.exists = Mock(return_value=0)
        mock_redis.setex = Mock()

        async def return_duplicates(
            subreddit: str,
        ) -> Dict[str, List[Dict[str, Union[str, int]]]]:
            return {"posts": duplicate_posts}

        with patch(
            "app.services.analysis.data_collector.get_redis", return_value=mock_redis
        ):
            with patch.object(
                data_collector, "_fetch_from_api", side_effect=return_duplicates
            ):
                result = await data_collector.process(pipeline_data_with_communities)

                assert result.success

                # 验证去重
                all_posts = []
                for community_posts in result.data["posts"].values():
                    all_posts.extend(community_posts)

                post_ids = [p["id"] for p in all_posts if "id" in p]
                unique_ids = set(post_ids)

                # 每个社区内部应该无重复
                for community_posts in result.data["posts"].values():
                    community_ids = [p["id"] for p in community_posts if "id" in p]
                    assert len(community_ids) == len(set(community_ids))
