"""
分析引擎集成测试 - 类型安全版本
测试完整的分析流水线执行
"""

import pytest
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import asyncio

from app.services.analysis_engine import (
    AnalysisEngine,
    AnalysisRequest,
    AnalysisResponse,
    AnalysisStatus,
)
from app.models.analysis_pipeline import PipelineData, PipelineResult, StepStatus
from app.core.analyzer_config import ConfigManager, StepConfig

from .test_base import (
    create_test_pipeline_data,
    create_mock_redis_client,
    assert_pipeline_result,
)


class TestAnalysisEngine:
    """测试分析引擎"""

    @pytest.fixture
    def mock_config_manager(self) -> Mock:
        """创建模拟配置管理器"""
        mock_config = Mock(spec=ConfigManager)
        mock_config.get.return_value = 300  # max_total_duration
        mock_config.get_step_config.return_value = StepConfig(
            step_name="test_step", max_duration=60.0, config_data={}
        )
        return mock_config

    @pytest.fixture
    def mock_redis(self) -> Mock:
        """创建模拟Redis客户端"""
        return create_mock_redis_client()

    @pytest.fixture
    def engine(self, mock_config_manager: Mock, mock_redis: Mock) -> AnalysisEngine:
        """创建分析引擎实例"""
        with patch("app.services.analysis_engine.config_manager", mock_config_manager):
            with patch("app.services.analysis_engine.redis_client", mock_redis):
                engine = AnalysisEngine()
                engine.redis_client = mock_redis
                return engine

    @pytest.fixture
    def analysis_request(self) -> AnalysisRequest:
        """创建分析请求"""
        return AnalysisRequest(
            analysis_id="test_analysis_123",
            keywords=["python", "machine learning", "data science"],
            min_subscribers=10000,
            max_communities=5,
            user_id="test_user",
        )

    @pytest.mark.asyncio
    async def test_execute_analysis_success(
        self, engine: AnalysisEngine, analysis_request: AnalysisRequest
    ) -> None:
        """测试成功执行分析"""
        # Mock各个步骤
        with patch.object(engine, "_execute_pipeline") as mock_pipeline:
            mock_pipeline.return_value = PipelineResult(
                step_name="complete",
                status=StepStatus.COMPLETED,
                success=True,
                data={
                    "ranked_signals": [
                        {
                            "signal_type": "PAIN_POINT",
                            "content": "Test signal",
                            "final_score": 0.9,
                        }
                    ],
                    "total_signals": 1,
                },
                duration=10.0,
                timestamp=datetime.utcnow(),
            )

            # 执行分析
            response = await engine.execute_analysis(analysis_request)

        # 验证响应
        assert isinstance(response, AnalysisResponse)
        assert response.status == AnalysisStatus.COMPLETED
        assert response.success is True
        assert len(response.results) > 0
        assert response.execution_time > 0

    @pytest.mark.asyncio
    async def test_execute_pipeline_all_steps(
        self, engine: AnalysisEngine, analysis_request: AnalysisRequest
    ) -> None:
        """测试执行完整流水线"""
        pipeline_data = PipelineData(
            analysis_id=analysis_request.analysis_id,
            input_data={
                "keywords": analysis_request.keywords,
                "min_subscribers": analysis_request.min_subscribers,
                "max_communities": analysis_request.max_communities,
            },
            intermediate_results={},
            context={"user_id": analysis_request.user_id},
        )

        # Mock所有步骤
        mock_steps = {
            "community_discovery": Mock(),
            "data_collection": Mock(),
            "signal_extraction": Mock(),
            "result_ranking": Mock(),
        }

        for step_name, mock_step in mock_steps.items():
            mock_step._process_step = AsyncMock(
                return_value=PipelineResult(
                    step_name=step_name,
                    status=StepStatus.COMPLETED,
                    success=True,
                    data={f"{step_name}_result": "test_data"},
                    duration=1.0,
                    timestamp=datetime.utcnow(),
                )
            )

        with patch.object(engine, "_load_analysis_steps", return_value=mock_steps):
            result = await engine._execute_pipeline(pipeline_data)

        # 验证所有步骤都被执行
        for mock_step in mock_steps.values():
            mock_step._process_step.assert_called_once()

        assert result.success
        assert result.status == StepStatus.COMPLETED

    def test_validate_request(self, engine: AnalysisEngine) -> None:
        """测试请求验证"""
        # 有效请求
        valid_request = AnalysisRequest(
            analysis_id="valid_123",
            keywords=["keyword1", "keyword2"],
            min_subscribers=1000,
            max_communities=10,
            user_id="user1",
        )
        assert engine._validate_request(valid_request) is True

        # 无效请求 - 空关键词
        invalid_request = AnalysisRequest(
            analysis_id="invalid_123",
            keywords=[],
            min_subscribers=1000,
            max_communities=10,
            user_id="user1",
        )
        assert engine._validate_request(invalid_request) is False

        # 无效请求 - 过多关键词
        too_many_keywords = AnalysisRequest(
            analysis_id="invalid_123",
            keywords=["kw" + str(i) for i in range(21)],
            min_subscribers=1000,
            max_communities=10,
            user_id="user1",
        )
        assert engine._validate_request(too_many_keywords) is False

    @pytest.mark.asyncio
    async def test_handle_step_failure(
        self, engine: AnalysisEngine, analysis_request: AnalysisRequest
    ) -> None:
        """测试步骤失败处理"""
        pipeline_data = create_test_pipeline_data(analysis_request.analysis_id)

        # Mock一个失败的步骤
        failing_step = Mock()
        failing_step._process_step = AsyncMock(
            return_value=PipelineResult(
                step_name="failing_step",
                status=StepStatus.FAILED,
                success=False,
                data={"error": "Step failed"},
                duration=0.0,
                timestamp=datetime.utcnow(),
            )
        )

        with patch.object(
            engine, "_load_analysis_steps", return_value={"failing_step": failing_step}
        ):
            result = await engine._execute_pipeline(pipeline_data)

        assert not result.success
        assert result.status == StepStatus.FAILED
        assert "error" in result.data

    @pytest.mark.asyncio
    async def test_timeout_handling(
        self, engine: AnalysisEngine, analysis_request: AnalysisRequest
    ) -> None:
        """测试超时处理"""
        pipeline_data = create_test_pipeline_data(analysis_request.analysis_id)

        # Mock一个超时的步骤
        slow_step = Mock()

        async def slow_process(data: PipelineData) -> PipelineResult:
            await asyncio.sleep(10)  # 模拟长时间运行
            return PipelineResult(
                step_name="slow_step",
                status=StepStatus.COMPLETED,
                success=True,
                data={},
                duration=10.0,
                timestamp=datetime.utcnow(),
            )

        slow_step._process_step = slow_process

        with patch.object(
            engine, "_load_analysis_steps", return_value={"slow_step": slow_step}
        ):
            with patch.object(engine, "max_total_duration", 0.1):  # 设置很短的超时
                result = await engine._execute_pipeline(pipeline_data)

        assert not result.success
        assert "超时" in result.data.get("error", "")

    def test_cache_analysis_result(
        self, engine: AnalysisEngine, mock_redis: Mock
    ) -> None:
        """测试结果缓存"""
        analysis_id = "test_123"
        result = AnalysisResponse(
            analysis_id=analysis_id,
            status=AnalysisStatus.COMPLETED,
            success=True,
            results=[{"test": "data"}],
            execution_time=5.0,
            timestamp=datetime.utcnow(),
        )

        # 缓存结果
        engine._cache_result(analysis_id, result)

        # 验证Redis调用
        mock_redis.set.assert_called()
        call_args = mock_redis.set.call_args
        assert analysis_id in call_args[0][0]  # key包含analysis_id
        assert call_args[1]["ex"] == 3600  # TTL设置

    def test_get_cached_result(self, engine: AnalysisEngine, mock_redis: Mock) -> None:
        """测试获取缓存结果"""
        analysis_id = "test_123"
        cached_data = {
            "status": "COMPLETED",
            "success": True,
            "results": [{"test": "data"}],
            "execution_time": 5.0,
            "timestamp": datetime.utcnow().isoformat(),
        }

        mock_redis.get.return_value = str(cached_data).encode()

        result = engine._get_cached_result(analysis_id)

        assert result is not None
        mock_redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_analyses(self, engine: AnalysisEngine) -> None:
        """测试并发分析执行"""
        requests = [
            AnalysisRequest(
                analysis_id=f"concurrent_{i}",
                keywords=[f"keyword_{i}"],
                min_subscribers=1000,
                max_communities=5,
                user_id=f"user_{i}",
            )
            for i in range(5)
        ]

        # Mock pipeline执行
        with patch.object(engine, "_execute_pipeline") as mock_pipeline:
            mock_pipeline.return_value = PipelineResult(
                step_name="complete",
                status=StepStatus.COMPLETED,
                success=True,
                data={"result": "test"},
                duration=1.0,
                timestamp=datetime.utcnow(),
            )

            # 并发执行
            tasks = [engine.execute_analysis(req) for req in requests]
            results = await asyncio.gather(*tasks)

        # 验证所有分析都成功完成
        assert len(results) == 5
        assert all(r.success for r in results)
        assert mock_pipeline.call_count == 5


@pytest.mark.integration
class TestAnalysisEngineIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_full_analysis_flow(self) -> None:
        """测试完整分析流程"""
        # 创建引擎
        engine = AnalysisEngine()

        # 准备请求
        request = AnalysisRequest(
            analysis_id="integration_test_123",
            keywords=["python", "django", "fastapi"],
            min_subscribers=5000,
            max_communities=3,
            user_id="test_user",
        )

        # Mock所有外部依赖
        mock_reddit_data = {
            "communities": [
                {"name": "r/python", "subscribers": 1000000},
                {"name": "r/django", "subscribers": 100000},
                {"name": "r/fastapi", "subscribers": 50000},
            ],
            "posts": [
                {
                    "id": f"post_{i}",
                    "title": f"Test post {i}",
                    "content": f"Content about Python issue {i}",
                    "score": 100 + i * 10,
                    "num_comments": 10 + i,
                }
                for i in range(30)
            ],
        }

        with patch(
            "app.services.analysis.community_discovery_step.search_reddit",
            return_value=mock_reddit_data["communities"],
        ):
            with patch(
                "app.services.analysis.data_collection_step.fetch_posts",
                return_value=mock_reddit_data["posts"],
            ):
                # 执行分析
                response = await engine.execute_analysis(request)

        # 验证结果
        assert response.status == AnalysisStatus.COMPLETED
        assert response.success is True
        assert len(response.results) > 0
        assert response.execution_time > 0
        assert response.analysis_id == request.analysis_id

        # 验证结果包含预期的信号
        signal_types = [r.get("signal_type") for r in response.results]
        assert any(
            st in ["PAIN_POINT", "COMPETITOR", "OPPORTUNITY"] for st in signal_types
        )

    @pytest.mark.asyncio
    async def test_error_recovery(self) -> None:
        """测试错误恢复机制"""
        engine = AnalysisEngine()

        request = AnalysisRequest(
            analysis_id="error_test_123",
            keywords=["test"],
            min_subscribers=1000,
            max_communities=5,
            user_id="test_user",
        )

        # 模拟第一次失败，第二次成功
        call_count = 0

        async def mock_pipeline(data: PipelineData) -> PipelineResult:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Temporary failure")
            return PipelineResult(
                step_name="complete",
                status=StepStatus.COMPLETED,
                success=True,
                data={"result": "recovered"},
                duration=1.0,
                timestamp=datetime.utcnow(),
            )

        with patch.object(engine, "_execute_pipeline", mock_pipeline):
            with patch.object(engine, "max_retries", 2):
                response = await engine.execute_analysis(request)

        # 应该在重试后成功
        assert response.success
        assert call_count == 2
