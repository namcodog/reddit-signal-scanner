"""
analysis_tasks.py 单元测试 - 类型安全优先
测试prd04-03 Worker任务处理逻辑的核心功能

覆盖率目标: ≥85%
类型安全: 100% mypy --strict 兼容
"""
import asyncio
import pytest
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional, Union, Any
from unittest.mock import Mock, patch, AsyncMock, MagicMock

import sys
import os

# 添加backend目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.tasks.analysis_tasks import (
    analyze_product,
    analysis_health_check,
)
from app.models.task import Task as TaskModel


class TestAnalyzeProduct:
    """测试analyze_product核心任务函数"""

    @pytest.fixture
    def mock_celery_task(self) -> Mock:
        """创建模拟的Celery任务实例"""
        mock_task = Mock()
        mock_task.request.id = str(uuid.uuid4())
        mock_task.request.retries = 0
        mock_task.retry = Mock(side_effect=Exception("重试调用"))
        return mock_task

    @pytest.fixture
    def valid_payload(self) -> Dict[str, str]:
        """有效的任务载荷"""
        return {"product_description": "一款创新的AI写作助手，帮助用户生成高质量内容"}

    @pytest.fixture
    def task_data(self) -> Dict[str, Union[str, int, datetime]]:
        """任务元数据"""
        return {
            "task_id": str(uuid.uuid4()),
            "user_id": "test_user",
            "priority": "normal",
        }

    def test_analyze_product_success(
        self,
        mock_celery_task: Mock,
        valid_payload: Dict[str, Any],
        task_data: Dict[str, Any],
    ) -> None:
        """测试成功的产品分析流程"""
        with patch("app.tasks.analysis_tasks.AnalysisEngine") as mock_engine_class:
            # 设置分析引擎mock
            mock_engine = Mock()
            mock_analysis_result = Mock()
            mock_analysis_result.model_dump = Mock(
                return_value={
                    "communities": ["r/productivity", "r/writing"],
                    "signals": ["高需求", "付费意愿强"],
                    "confidence": 0.85,
                }
            )

            mock_engine.analyze = AsyncMock(return_value=mock_analysis_result)
            mock_engine_class.return_value = mock_engine

            # Mock数据库更新函数
            with patch("app.tasks.analysis_tasks._update_task_status") as mock_update:
                # 调用待测试函数 - 使用__wrapped__绕过Celery装饰器
                result = analyze_product.__wrapped__(
                    mock_celery_task, valid_payload, task_data
                )

                # 验证结果结构
                assert isinstance(result, dict)
                assert result["status"] == "completed"
                assert result["task_id"] == task_data["task_id"]
                assert "analysis_result" in result
                assert "execution_time" in result
                assert isinstance(result["execution_time"], float)

                # 验证分析引擎调用
                mock_engine_class.assert_called_once()
                mock_engine.analyze.assert_called_once_with(
                    product_description=valid_payload["product_description"]
                )

                # 验证数据库状态更新调用
                assert mock_update.call_count >= 2  # 至少调用开始和完成状态

                # 验证第一次调用（开始状态）
                first_call = mock_update.call_args_list[0]
                assert first_call[0][0] == task_data["task_id"]
                assert first_call[0][1] == "processing"

                # 验证最后一次调用（完成状态）
                last_call = mock_update.call_args_list[-1]
                assert last_call[0][0] == task_data["task_id"]
                assert last_call[0][1] == "completed"

    def test_analyze_product_validation_error(
        self, mock_celery_task: Mock, task_data: Dict[str, Any]
    ) -> None:
        """测试参数验证错误处理"""
        invalid_payload = {"product_description": "太短"}  # 少于10个字符

        with patch("app.tasks.analysis_tasks._update_task_status") as mock_update:
            with pytest.raises(ValueError, match="产品描述不能为空且长度必须至少10个字符"):
                analyze_product(
                    self=mock_celery_task, payload=invalid_payload, task_data=task_data
                )

            # 验证错误状态更新
            mock_update.assert_called_with(
                task_data["task_id"],
                "failed",
                {
                    "error": "参数验证失败: 产品描述不能为空且长度必须至少10个字符",
                    "error_type": "validation_error",
                },
            )

    def test_analyze_product_empty_description(
        self, mock_celery_task: Mock, task_data: Dict[str, Any]
    ) -> None:
        """测试空产品描述"""
        empty_payload = {"product_description": ""}

        with patch("backend.app.tasks.analysis_tasks._update_task_status"):
            with pytest.raises(ValueError):
                analyze_product(
                    self=mock_celery_task, payload=empty_payload, task_data=task_data
                )

    def test_analyze_product_analysis_engine_error(
        self,
        mock_celery_task: Mock,
        valid_payload: Dict[str, Any],
        task_data: Dict[str, Any],
    ) -> None:
        """测试分析引擎异常处理"""
        with patch("app.tasks.analysis_tasks.AnalysisEngine") as mock_engine_class:
            # 设置分析引擎抛出异常
            mock_engine = Mock()
            mock_engine.analyze = AsyncMock(side_effect=ConnectionError("网络连接失败"))
            mock_engine_class.return_value = mock_engine

            with patch("app.tasks.analysis_tasks._update_task_status") as mock_update:
                # 测试重试机制
                with pytest.raises(Exception):  # 最终会抛出重试异常
                    analyze_product(
                        self=mock_celery_task,
                        payload=valid_payload,
                        task_data=task_data,
                    )

                # 验证重试状态更新
                retry_calls = [
                    call
                    for call in mock_update.call_args_list
                    if len(call[0]) > 1 and call[0][1] == "retrying"
                ]
                assert len(retry_calls) > 0

    def test_analyze_product_no_task_data(
        self, mock_celery_task: Mock, valid_payload: Dict[str, Any]
    ) -> None:
        """测试没有task_data的情况"""
        with patch("app.tasks.analysis_tasks.AnalysisEngine") as mock_engine_class:
            mock_engine = Mock()
            mock_analysis_result = Mock()
            mock_analysis_result.model_dump = Mock(return_value={"test": "result"})
            mock_engine.analyze = AsyncMock(return_value=mock_analysis_result)
            mock_engine_class.return_value = mock_engine

            with patch("backend.app.tasks.analysis_tasks._update_task_status"):
                result = analyze_product(
                    self=mock_celery_task, payload=valid_payload, task_data=None
                )

                # 应该使用Celery请求ID
                assert result["task_id"] == str(mock_celery_task.request.id)


class TestUpdateTaskStatus:
    """测试_update_task_status辅助函数"""

    def test_update_task_status_success(self) -> None:
        """测试成功的状态更新"""
        task_id = str(uuid.uuid4())
        status = "completed"
        additional_data = {"result": "test_result", "execution_time": 1.23}

        with patch("app.core.database.get_session_sync") as mock_get_session:
            # 设置mock数据库会话
            mock_db = Mock()
            mock_get_session.return_value.__enter__ = Mock(return_value=mock_db)
            mock_get_session.return_value.__exit__ = Mock(return_value=None)

            # 设置update成功
            mock_result = Mock()
            mock_result.rowcount = 1
            mock_db.execute.return_value = mock_result

            # 调用函数
            _update_task_status(task_id, status, additional_data)

            # 验证数据库调用
            assert mock_db.execute.call_count >= 1
            mock_db.commit.assert_called_once()

    def test_update_task_status_no_additional_data(self) -> None:
        """测试没有额外数据的状态更新"""
        task_id = str(uuid.uuid4())
        status = "processing"

        with patch("app.core.database.get_session_sync") as mock_get_session:
            mock_db = Mock()
            mock_get_session.return_value.__enter__ = Mock(return_value=mock_db)
            mock_get_session.return_value.__exit__ = Mock(return_value=None)

            mock_result = Mock()
            mock_result.rowcount = 1
            mock_db.execute.return_value = mock_result

            _update_task_status(task_id, status)

            # 只应该调用一次update（基础状态更新）
            assert mock_db.execute.call_count == 1
            mock_db.commit.assert_called_once()

    def test_update_task_status_task_not_found(self) -> None:
        """测试任务不存在的情况"""
        task_id = str(uuid.uuid4())
        status = "failed"

        with patch("app.core.database.get_session_sync") as mock_get_session:
            mock_db = Mock()
            mock_get_session.return_value.__enter__ = Mock(return_value=mock_db)
            mock_get_session.return_value.__exit__ = Mock(return_value=None)

            # 设置任务不存在（rowcount=0）
            mock_result = Mock()
            mock_result.rowcount = 0
            mock_db.execute.return_value = mock_result

            # 不应该抛出异常，只是记录日志
            _update_task_status(task_id, status)

            mock_db.execute.assert_called_once()
            mock_db.commit.assert_called_once()

    def test_update_task_status_database_error(self) -> None:
        """测试数据库错误处理"""
        task_id = str(uuid.uuid4())
        status = "failed"

        with patch("app.core.database.get_session_sync") as mock_get_session:
            # 设置数据库异常
            mock_get_session.side_effect = Exception("数据库连接失败")

            # 不应该抛出异常（函数内部捕获）
            _update_task_status(task_id, status)


class TestAnalysisHealthCheck:
    """测试analysis_health_check健康检查函数"""

    def test_health_check_success(self) -> None:
        """测试成功的健康检查"""
        with patch("app.tasks.analysis_tasks.AnalysisEngine") as mock_engine_class:
            # 设置健康引擎
            mock_engine = Mock()
            mock_engine.health_check = AsyncMock(
                return_value={
                    "status": "healthy",
                    "components": {"database": "ok", "redis": "ok"},
                }
            )
            mock_engine_class.return_value = mock_engine

            result = analysis_health_check()

            # 验证结果结构
            assert isinstance(result, dict)
            assert "status" in result
            assert "timestamp" in result
            assert "analysis_engine" in result

            # 验证引擎健康检查调用
            mock_engine.health_check.assert_called_once()

    def test_health_check_engine_error(self) -> None:
        """测试分析引擎健康检查失败"""
        with patch("app.tasks.analysis_tasks.AnalysisEngine") as mock_engine_class:
            # 设置引擎异常
            mock_engine = Mock()
            mock_engine.health_check = AsyncMock(side_effect=Exception("引擎故障"))
            mock_engine_class.return_value = mock_engine

            result = analysis_health_check()

            # 健康检查应该返回错误状态而不抛出异常
            assert isinstance(result, dict)
            assert result["status"] != "healthy"


# 性能测试和边界测试
class TestAnalysisTasksEdgeCases:
    """边界情况和性能测试"""

    def test_analyze_product_unicode_description(
        self, mock_celery_task: Mock, task_data: Dict[str, Any]
    ) -> None:
        """测试Unicode字符的产品描述"""
        unicode_payload = {"product_description": "一款智能的人工智能助手🤖，支持多语言交流💬，提供专业的技术支持🔧"}

        with patch("app.tasks.analysis_tasks.AnalysisEngine") as mock_engine_class:
            mock_engine = Mock()
            mock_analysis_result = Mock()
            mock_analysis_result.model_dump = Mock(return_value={"unicode_test": "通过"})
            mock_engine.analyze = AsyncMock(return_value=mock_analysis_result)
            mock_engine_class.return_value = mock_engine

            with patch("backend.app.tasks.analysis_tasks._update_task_status"):
                result = analyze_product(
                    self=mock_celery_task, payload=unicode_payload, task_data=task_data
                )

                assert result["status"] == "completed"

    def test_analyze_product_very_long_description(
        self, mock_celery_task: Mock, task_data: Dict[str, Any]
    ) -> None:
        """测试超长产品描述"""
        long_description = "一款创新产品，" * 1000  # 创建很长的描述
        long_payload = {"product_description": long_description}

        with patch("app.tasks.analysis_tasks.AnalysisEngine") as mock_engine_class:
            mock_engine = Mock()
            mock_analysis_result = Mock()
            mock_analysis_result.model_dump = Mock(return_value={"length_test": "通过"})
            mock_engine.analyze = AsyncMock(return_value=mock_analysis_result)
            mock_engine_class.return_value = mock_engine

            with patch("backend.app.tasks.analysis_tasks._update_task_status"):
                result = analyze_product(
                    self=mock_celery_task, payload=long_payload, task_data=task_data
                )

                assert result["status"] == "completed"


# pytest fixtures和配置
@pytest.fixture
def mock_celery_task() -> Mock:
    """全局Mock Celery任务"""
    mock_task = Mock()
    mock_task.request.id = str(uuid.uuid4())
    mock_task.request.retries = 0
    mock_task.retry = Mock()
    return mock_task
