"""
社区发现算法单元测试 - 基于真实代码结构
测试CommunityDiscoveryStep的完整功能
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.core.analyzer_config import StepConfig
from app.models.analysis_pipeline import PipelineData, StepStatus
from app.services.analysis.community_discovery_step import CommunityDiscoveryStep
from tests.algorithms.test_base_v3 import (
    create_test_pipeline_data,
    create_test_step_config,
)


class TestCommunityDiscoveryStep:
    """测试社区发现步骤"""

    @pytest.fixture
    def step_config(self) -> StepConfig:
        """创建步骤配置"""
        config = create_test_step_config("community_discovery", 60.0)
        return config

    @pytest.fixture
    def step_instance(self, step_config: StepConfig) -> CommunityDiscoveryStep:
        """创建步骤实例"""
        return CommunityDiscoveryStep(step_config)

    @pytest.fixture
    def pipeline_data(self) -> PipelineData:
        """创建测试管道数据"""
        data = create_test_pipeline_data(
            "Python web development framework",
            ["python", "web", "framework", "django"],
        )
        return data

    def test_init(self, step_config: StepConfig) -> None:
        """测试初始化"""
        step = CommunityDiscoveryStep(step_config)
        assert step.config == step_config
        assert step.name == "communitydiscovery"
        assert step.discovery_service is None
        assert step.step_config["default_max_communities"] == 20

    def test_validate_input_valid(
        self, step_instance: CommunityDiscoveryStep, pipeline_data: PipelineData
    ) -> None:
        """测试有效输入验证"""
        # Mock基类方法
        with patch.object(step_instance, "validate_common_input", return_value=True):
            result = step_instance.validate_input(pipeline_data)
            assert result is True

    def test_validate_input_short_description(
        self, step_instance: CommunityDiscoveryStep
    ) -> None:
        """测试短描述输入验证"""
        # 创建描述太短的数据
        short_data = create_test_pipeline_data("short", ["test"])

        # Mock基类方法和错误添加方法
        with patch.object(step_instance, "validate_common_input", return_value=True):
            with patch.object(step_instance, "add_error") as mock_add_error:
                result = step_instance.validate_input(short_data)
                assert result is False
                mock_add_error.assert_called_once()
                args = mock_add_error.call_args[0]
                assert "产品描述过短" in args[1]

    def test_validate_input_long_description(
        self, step_instance: CommunityDiscoveryStep
    ) -> None:
        """测试长描述输入验证（截取处理）"""
        # 创建描述过长的数据
        long_description = "x" * 2500
        long_data = create_test_pipeline_data(long_description, ["test"])

        with patch.object(step_instance, "validate_common_input", return_value=True):
            with patch.object(step_instance, "add_warning") as mock_add_warning:
                result = step_instance.validate_input(long_data)
                assert result is True
                mock_add_warning.assert_called_once()
                assert len(long_data.product_description) == 2000

    def test_validate_input_common_validation_fails(
        self, step_instance: CommunityDiscoveryStep, pipeline_data: PipelineData
    ) -> None:
        """测试基础验证失败"""
        with patch.object(step_instance, "validate_common_input", return_value=False):
            result = step_instance.validate_input(pipeline_data)
            assert result is False

    @pytest.mark.asyncio
    async def test_initialize_service_success(
        self, step_instance: CommunityDiscoveryStep
    ) -> None:
        """测试服务初始化成功"""
        # Mock CommunityDiscoveryService
        mock_service = Mock()
        mock_service.initialize = AsyncMock()

        with patch(
            "app.services.analysis.community_discovery_step.CommunityDiscoveryService",
            return_value=mock_service,
        ):
            await step_instance._initialize_service_if_needed()

            assert step_instance.discovery_service == mock_service
            mock_service.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_service_failure(
        self, step_instance: CommunityDiscoveryStep
    ) -> None:
        """测试服务初始化失败"""
        # Mock失败的服务初始化
        mock_service = Mock()
        mock_service.initialize = AsyncMock(side_effect=Exception("Init failed"))

        with patch(
            "app.services.analysis.community_discovery_step.CommunityDiscoveryService",
            return_value=mock_service,
        ):
            with pytest.raises(Exception, match="Init failed"):
                await step_instance._initialize_service_if_needed()

    @pytest.mark.asyncio
    async def test_process_step_success(
        self, step_instance: CommunityDiscoveryStep, pipeline_data: PipelineData
    ) -> None:
        """测试步骤处理成功"""
        # Mock服务和其响应
        mock_service = Mock()
        mock_response = Mock()
        mock_response.communities = [
            {"name": "r/python", "score": 0.9, "subscribers": 1000000},
            {"name": "r/django", "score": 0.8, "subscribers": 100000},
            {"name": "r/webdev", "score": 0.7, "subscribers": 500000},
        ]
        mock_response.metadata = {"algorithm": "test", "version": "1.0"}
        mock_response.stats = {"total_processed": 100, "execution_time": 1.5}

        mock_service.discover_communities = AsyncMock(return_value=mock_response)
        step_instance.discovery_service = mock_service

        # Mock其他方法
        with patch.object(step_instance, "validate_input", return_value=True):
            with patch.object(
                step_instance, "_initialize_service_if_needed", return_value=None
            ):
                result = await step_instance._process_step(pipeline_data)

        # 验证结果
        assert result.success is True
        assert result.status == StepStatus.COMPLETED
        assert "communities" in result.data
        assert len(result.data["communities"]) == 3
        assert result.data["communities"][0]["name"] == "r/python"
        assert "algorithm_metadata" in result.data
        assert "processing_stats" in result.data

    @pytest.mark.asyncio
    async def test_process_step_validation_failure(
        self, step_instance: CommunityDiscoveryStep, pipeline_data: PipelineData
    ) -> None:
        """测试输入验证失败"""
        with patch.object(step_instance, "validate_input", return_value=False):
            with patch.object(step_instance, "_create_error_result") as mock_error:
                mock_error.return_value = Mock(success=False, status=StepStatus.FAILED)

                result = await step_instance._process_step(pipeline_data)

                mock_error.assert_called_once()
                assert result.success is False

    @pytest.mark.asyncio
    async def test_process_step_service_error(
        self, step_instance: CommunityDiscoveryStep, pipeline_data: PipelineData
    ) -> None:
        """测试服务执行错误"""
        # Mock服务抛出异常
        mock_service = Mock()
        mock_service.discover_communities = AsyncMock(
            side_effect=Exception("Service error")
        )
        step_instance.discovery_service = mock_service

        with patch.object(step_instance, "validate_input", return_value=True):
            with patch.object(
                step_instance, "_initialize_service_if_needed", return_value=None
            ):
                with patch.object(step_instance, "_create_error_result") as mock_error:
                    mock_error.return_value = Mock(
                        success=False, status=StepStatus.FAILED
                    )

                    result = await step_instance._process_step(pipeline_data)

                    mock_error.assert_called_once()
                    assert "Service error" in mock_error.call_args[0][0]
                    assert result.success is False


class TestCommunityDiscoveryStepIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_full_step_execution(self) -> None:
        """测试完整步骤执行流程"""
        config = create_test_step_config("community_discovery")
        step = CommunityDiscoveryStep(config)
        pipeline_data = create_test_pipeline_data(
            "AI-powered task management application",
            ["ai", "productivity", "task", "management"],
        )

        # Mock完整的服务链
        mock_service = Mock()
        mock_response = Mock()
        mock_response.communities = [
            {"name": "r/productivity", "score": 0.95, "subscribers": 800000},
            {"name": "r/artificial", "score": 0.90, "subscribers": 500000},
            {"name": "r/taskmanagement", "score": 0.85, "subscribers": 50000},
        ]
        mock_response.metadata = {
            "algorithm_version": "2.1",
            "processing_mode": "semantic",
            "cache_hit_rate": 0.3,
        }
        mock_response.stats = {
            "total_processed": 1500,
            "execution_time": 2.8,
            "api_calls_used": 5,
        }

        mock_service.discover_communities = AsyncMock(return_value=mock_response)
        mock_service.initialize = AsyncMock()

        with patch(
            "app.services.analysis.community_discovery_step.CommunityDiscoveryService",
            return_value=mock_service,
        ):
            # 使用基类的process方法进行完整测试
            with patch.object(step, "validate_input", return_value=True):
                with patch.object(step, "_validate_result", return_value=True):
                    result = await step.process(pipeline_data)

        # 验证完整结果
        assert result.success is True
        assert result.status == StepStatus.COMPLETED
        assert result.duration > 0

        # 验证数据结构完整性
        assert "communities" in result.data
        assert "algorithm_metadata" in result.data
        assert "processing_stats" in result.data

        # 验证社区数据
        communities = result.data["communities"]
        assert len(communities) == 3
        assert communities[0]["score"] == 0.95
        assert all("name" in community for community in communities)

        # 验证元数据
        metadata = result.data["algorithm_metadata"]
        assert metadata["algorithm_version"] == "2.1"

        # 验证统计信息
        stats = result.data["processing_stats"]
        assert stats["total_processed"] == 1500
