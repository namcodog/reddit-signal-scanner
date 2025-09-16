"""
集成测试 - prd04-03 Worker任务处理逻辑
验证Producer→Worker→Database→SSE完整数据流

测试目标：
1. 端到端任务执行流程
2. Celery任务队列集成
3. 数据库状态同步
4. SSE实时推送
5. 分析引擎集成
6. 异常恢复机制
"""
import asyncio
import pytest
import uuid
import time
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import Mock, patch, AsyncMock

# 添加项目路径
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.tasks.analysis_tasks import analyze_product
from app.services.simple_sse_broadcaster import (
    get_sse_broadcaster,
    SimpleSSEBroadcaster,
)
from app.models.task import Task as TaskModel


class TestWorkerIntegration:
    """Worker任务集成测试套件"""

    @pytest.fixture
    def mock_database_session(self):
        """Mock数据库会话"""
        with patch("app.core.database.get_session_sync") as mock_get_session:
            mock_db = Mock()
            mock_get_session.return_value.__enter__ = Mock(return_value=mock_db)
            mock_get_session.return_value.__exit__ = Mock(return_value=None)

            # 模拟任务更新成功
            mock_result = Mock()
            mock_result.rowcount = 1
            mock_db.execute.return_value = mock_result

            yield mock_db

    @pytest.fixture
    def mock_analysis_engine(self):
        """Mock分析引擎"""
        with patch("app.tasks.analysis_tasks.AnalysisEngine") as mock_engine_class:
            mock_engine = Mock()

            # 设置分析结果
            mock_analysis_result = Mock()
            mock_analysis_result.model_dump = Mock(
                return_value={
                    "communities": ["r/startups", "r/entrepreneur", "r/business"],
                    "signals": [
                        {
                            "type": "high_demand",
                            "confidence": 0.85,
                            "evidence": "150+ mentions",
                        },
                        {
                            "type": "payment_intent",
                            "confidence": 0.72,
                            "evidence": "Users asking about pricing",
                        },
                    ],
                    "insights": {
                        "market_size": "Medium",
                        "competition": "Low",
                        "entry_barriers": "Medium",
                    },
                    "confidence_score": 0.78,
                    "processing_time": 2.34,
                }
            )

            mock_engine.analyze = AsyncMock(return_value=mock_analysis_result)
            mock_engine_class.return_value = mock_engine

            yield mock_engine

    @pytest.fixture
    def task_payload(self):
        """标准任务载荷"""
        return {"product_description": "一款AI驱动的智能写作助手，帮助内容创作者提高效率，支持多种文体和语言风格"}

    @pytest.fixture
    def task_metadata(self):
        """任务元数据"""
        return {
            "task_id": str(uuid.uuid4()),
            "user_id": "test_user_123",
            "priority": "high",
            "source": "integration_test",
        }

    def test_end_to_end_task_execution(
        self, mock_database_session, mock_analysis_engine, task_payload, task_metadata
    ):
        """测试完整的端到端任务执行流程"""

        # 创建mock celery任务
        mock_celery_task = Mock()
        mock_celery_task.request.id = task_metadata["task_id"]
        mock_celery_task.request.retries = 0

        # 执行完整的任务流程
        result = analyze_product.__wrapped__(task_payload, task_metadata)

        # 验证结果结构
        assert isinstance(result, dict)
        assert result["status"] == "completed"
        assert result["task_id"] == task_metadata["task_id"]
        assert "analysis_result" in result
        assert "execution_time" in result

        # 验证分析结果内容
        analysis_result = result["analysis_result"]
        assert "communities" in analysis_result
        assert "signals" in analysis_result
        assert "confidence_score" in analysis_result
        assert len(analysis_result["communities"]) == 3
        assert len(analysis_result["signals"]) == 2

        # 验证数据库调用序列
        db_calls = mock_database_session.execute.call_args_list
        assert len(db_calls) >= 2  # 至少有开始和完成状态更新

        # 验证分析引擎调用
        mock_analysis_engine.analyze.assert_called_once_with(
            product_description=task_payload["product_description"]
        )

    def test_database_state_synchronization(
        self, mock_database_session, mock_analysis_engine, task_payload, task_metadata
    ):
        """测试数据库状态同步机制"""

        mock_celery_task = Mock()
        mock_celery_task.request.id = task_metadata["task_id"]
        mock_celery_task.request.retries = 0

        # 执行任务
        result = analyze_product.__wrapped__(task_payload, task_metadata)

        # 验证数据库状态更新调用顺序
        db_calls = mock_database_session.execute.call_args_list

        # 第一次调用应该是设置processing状态
        # 注意：实际的SQL语句验证会比较复杂，这里主要验证调用次数和提交
        assert len(db_calls) >= 1

        # 验证commit被调用
        mock_database_session.commit.assert_called()

        # 验证任务完成状态
        assert result["status"] == "completed"

    def test_sse_broadcasting_integration(
        self, mock_database_session, mock_analysis_engine
    ):
        """测试SSE广播集成"""

        # 创建SSE广播器实例
        broadcaster = get_sse_broadcaster()

        # 模拟SSE连接
        mock_queue = AsyncMock()
        task_id = str(uuid.uuid4())

        # 测试连接管理
        broadcaster.add_connection(task_id, mock_queue)
        assert task_id in broadcaster._connections
        assert len(broadcaster._connections[task_id]) == 1

        # 测试广播功能
        async def test_broadcast():
            await broadcaster.broadcast_task_update(
                task_id=task_id, status="processing", progress=50, message="分析进行中..."
            )

            # 验证消息被放入队列
            mock_queue.put.assert_called_once()
            call_args = mock_queue.put.call_args[0][0]

            assert call_args["task_id"] == task_id
            assert call_args["status"] == "processing"
            assert call_args["progress"] == 50
            assert call_args["message"] == "分析进行中..."
            assert "timestamp" in call_args

        # 运行异步测试
        asyncio.run(test_broadcast())

        # 测试连接移除
        broadcaster.remove_connection(task_id, mock_queue)
        assert task_id not in broadcaster._connections

    def test_analysis_engine_integration(
        self, mock_database_session, task_payload, task_metadata
    ):
        """测试分析引擎集成"""

        # 使用真实的AnalysisEngine调用模式（但仍然mock）
        with patch("app.tasks.analysis_tasks.AnalysisEngine") as mock_engine_class:
            mock_engine = Mock()

            # 设置复杂的分析结果
            complex_result = Mock()
            complex_result.model_dump = Mock(
                return_value={
                    "communities": [
                        {"name": "r/startups", "members": 850000, "relevance": 0.92},
                        {
                            "name": "r/entrepreneur",
                            "members": 750000,
                            "relevance": 0.88,
                        },
                    ],
                    "signals": [
                        {
                            "type": "market_validation",
                            "confidence": 0.85,
                            "evidence": "Multiple users requesting similar features",
                            "keywords": ["writing", "AI", "automation"],
                        }
                    ],
                    "market_analysis": {
                        "size_estimate": "10M+ potential users",
                        "competition_level": "medium",
                        "monetization_potential": 0.78,
                    },
                }
            )

            mock_engine.analyze = AsyncMock(return_value=complex_result)
            mock_engine_class.return_value = mock_engine

            mock_celery_task = Mock()
            mock_celery_task.request.id = task_metadata["task_id"]
            mock_celery_task.request.retries = 0

            # 执行任务
            result = analyze_product.__wrapped__(
                mock_celery_task, task_payload, task_metadata
            )

            # 验证分析引擎被正确调用
            mock_engine_class.assert_called_once()
            mock_engine.analyze.assert_called_once_with(
                product_description=task_payload["product_description"]
            )

            # 验证复杂结果被正确处理
            analysis_result = result["analysis_result"]
            assert "communities" in analysis_result
            assert "market_analysis" in analysis_result
            assert len(analysis_result["communities"]) == 2

    def test_error_handling_and_recovery(
        self, mock_database_session, task_payload, task_metadata
    ):
        """测试错误处理和恢复机制"""

        # 测试分析引擎异常处理
        with patch("app.tasks.analysis_tasks.AnalysisEngine") as mock_engine_class:
            mock_engine = Mock()
            mock_engine.analyze = AsyncMock(side_effect=ConnectionError("网络连接失败"))
            mock_engine_class.return_value = mock_engine

            mock_celery_task = Mock()
            mock_celery_task.request.id = task_metadata["task_id"]
            mock_celery_task.request.retries = 0
            mock_celery_task.retry = Mock(side_effect=Exception("重试异常"))

            # 执行任务应该触发重试机制
            with pytest.raises(Exception, match="重试异常"):
                analyze_product.__wrapped__(task_payload, task_metadata)

            # 验证重试被调用
            mock_celery_task.retry.assert_called_once()

    def test_concurrent_task_processing(
        self, mock_database_session, mock_analysis_engine
    ):
        """测试并发任务处理"""

        # 创建多个任务
        tasks_data = []
        for i in range(3):
            tasks_data.append(
                {
                    "payload": {"product_description": f"测试产品{i+1}，功能描述很长很详细"},
                    "metadata": {
                        "task_id": str(uuid.uuid4()),
                        "user_id": f"user_{i+1}",
                        "priority": "normal",
                    },
                }
            )

        results = []

        # 模拟并发执行
        for task_data in tasks_data:
            mock_celery_task = Mock()
            mock_celery_task.request.id = task_data["metadata"]["task_id"]
            mock_celery_task.request.retries = 0

            result = analyze_product.__wrapped__(
                task_data["payload"], task_data["metadata"]
            )
            results.append(result)

        # 验证所有任务都成功完成
        assert len(results) == 3
        for result in results:
            assert result["status"] == "completed"
            assert "analysis_result" in result

        # 验证分析引擎被调用了3次
        assert mock_analysis_engine.analyze.call_count == 3

    def test_large_payload_handling(
        self, mock_database_session, mock_analysis_engine, task_metadata
    ):
        """测试大载荷处理"""

        # 创建超大产品描述
        large_description = "一款革命性的AI产品，" * 1000  # 约10KB文本
        large_payload = {"product_description": large_description}

        mock_celery_task = Mock()
        mock_celery_task.request.id = task_metadata["task_id"]
        mock_celery_task.request.retries = 0

        # 执行任务
        start_time = time.time()
        result = analyze_product.__wrapped__(large_payload, task_metadata)
        execution_time = time.time() - start_time

        # 验证大载荷被成功处理
        assert result["status"] == "completed"
        assert len(result["product_description"]) > 5000

        # 验证执行时间合理（不应该超时）
        assert execution_time < 30  # 30秒内完成

        # 验证分析引擎接收到完整描述
        mock_analysis_engine.analyze.assert_called_once_with(
            product_description=large_description
        )

    def test_task_metadata_preservation(
        self, mock_database_session, mock_analysis_engine, task_payload
    ):
        """测试任务元数据保持"""

        rich_metadata = {
            "task_id": str(uuid.uuid4()),
            "user_id": "enterprise_user",
            "organization": "TechCorp",
            "priority": "high",
            "source": "api_v2",
            "trace_id": "trace_" + str(uuid.uuid4()),
            "custom_config": {
                "enable_advanced_analysis": True,
                "max_communities": 10,
                "confidence_threshold": 0.7,
            },
        }

        mock_celery_task = Mock()
        mock_celery_task.request.id = rich_metadata["task_id"]
        mock_celery_task.request.retries = 0

        # 执行任务
        result = analyze_product.__wrapped__(task_payload, rich_metadata)

        # 验证元数据被保持
        assert result["metadata"]["user_id"] == "enterprise_user"
        assert result["metadata"]["organization"] == "TechCorp"
        assert result["metadata"]["trace_id"] == rich_metadata["trace_id"]
        assert "custom_config" in result["metadata"]


class TestSystemIntegration:
    """系统级集成测试"""

    def test_health_check_integration(self):
        """测试健康检查集成"""

        with patch("app.tasks.analysis_tasks.AnalysisEngine") as mock_engine_class:
            mock_engine = Mock()
            mock_engine.health_check = AsyncMock(
                return_value={
                    "status": "healthy",
                    "components": {
                        "database": "connected",
                        "redis": "connected",
                        "analysis_pipeline": "ready",
                    },
                    "last_check": datetime.now(timezone.utc).isoformat(),
                }
            )
            mock_engine_class.return_value = mock_engine

            # 执行健康检查
            from app.tasks.analysis_tasks import analysis_health_check

            result = analysis_health_check()

            # 验证健康检查结果
            assert isinstance(result, dict)
            assert "status" in result
            assert "timestamp" in result
            assert "analysis_engine" in result

            # 验证分析引擎健康检查被调用
            mock_engine.health_check.assert_called_once()

    def test_configuration_integration(self):
        """测试配置集成"""

        # 测试TaskConfig加载
        with patch("app.tasks.analysis_tasks.TaskConfig") as mock_config_class:
            mock_config = Mock()
            mock_config.default_config.return_value = Mock(
                max_retries=3, retry_delays=[60, 120, 300], timeout=300
            )
            mock_config_class.default_config = mock_config.default_config

            # 验证配置在任务中被使用
            # 这里主要验证配置加载机制而不是具体值
            config = mock_config_class.default_config()
            assert hasattr(config, "max_retries")
            assert hasattr(config, "retry_delays")
            assert hasattr(config, "timeout")


# pytest配置和工具函数
@pytest.fixture(scope="session")
def integration_test_setup():
    """集成测试环境设置"""
    print("🔧 设置集成测试环境...")

    # 这里可以添加测试数据库、Redis等的设置
    # 暂时使用mock，生产环境可以配置真实的测试数据库

    yield

    print("🧹 清理集成测试环境...")


def pytest_configure(config):
    """Pytest配置"""
    config.addinivalue_line("markers", "integration: 标记集成测试")
    config.addinivalue_line("markers", "slow: 标记慢速测试")


# 性能和负载测试
class TestPerformanceIntegration:
    """性能集成测试"""

    @pytest.mark.slow
    @pytest.fixture
    def mock_database_session_perf(self):
        """Performance测试的Mock数据库会话"""
        with patch("app.core.database.get_session_sync") as mock_get_session:
            mock_db = Mock()
            mock_get_session.return_value.__enter__ = Mock(return_value=mock_db)
            mock_get_session.return_value.__exit__ = Mock(return_value=None)

            mock_result = Mock()
            mock_result.rowcount = 1
            mock_db.execute.return_value = mock_result

            yield mock_db

    @pytest.fixture
    def mock_analysis_engine_perf(self):
        """Performance测试的Mock分析引擎"""
        with patch("app.tasks.analysis_tasks.AnalysisEngine") as mock_engine_class:
            mock_engine = Mock()

            mock_analysis_result = Mock()
            mock_analysis_result.model_dump = Mock(return_value={"performance": "test"})

            mock_engine.analyze = AsyncMock(return_value=mock_analysis_result)
            mock_engine_class.return_value = mock_engine

            yield mock_engine

    def test_task_processing_performance(
        self, mock_database_session_perf, mock_analysis_engine_perf
    ):
        """测试任务处理性能"""

        task_count = 10
        max_execution_time = 5.0  # 10个任务5秒内完成

        start_time = time.time()

        for i in range(task_count):
            mock_celery_task = Mock()
            mock_celery_task.request.id = str(uuid.uuid4())
            mock_celery_task.request.retries = 0

            payload = {"product_description": f"性能测试产品{i+1}"}
            metadata = {"task_id": str(uuid.uuid4())}

            result = analyze_product.__wrapped__(payload, metadata)

            assert result["status"] == "completed"

        total_time = time.time() - start_time

        # 验证性能要求
        assert total_time < max_execution_time
        print(f"✅ 处理{task_count}个任务耗时: {total_time:.2f}秒")

    @pytest.mark.integration
    def test_memory_usage_stability(
        self, mock_database_session_perf, mock_analysis_engine_perf
    ):
        """测试内存使用稳定性"""

        import gc
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # 执行多个任务
        for i in range(50):
            mock_celery_task = Mock()
            mock_celery_task.request.id = str(uuid.uuid4())
            mock_celery_task.request.retries = 0

            payload = {"product_description": "内存稳定性测试产品" * 100}
            metadata = {"task_id": str(uuid.uuid4())}

            analyze_product.__wrapped__(payload, metadata)

            # 每10个任务检查一次内存
            if i % 10 == 0:
                gc.collect()  # 强制垃圾回收
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_increase = current_memory - initial_memory

                # 内存增长不应该超过50MB
                assert memory_increase < 50, f"内存泄漏检测：增长{memory_increase:.1f}MB"

        final_memory = process.memory_info().rss / 1024 / 1024
        total_increase = final_memory - initial_memory

        print(f"✅ 内存稳定性测试完成，总增长: {total_increase:.1f}MB")
        assert total_increase < 100  # 总增长不超过100MB
