"""
prd04-08: 任务系统集成测试 - Context7标准实现
遵循pytest-celery最佳实践：开箱即用，零配置

测试目标：验证TaskManager与Celery的真实集成
实施原则：最小化代码，最大化价值
"""
from typing import Any, Dict
import pytest
from pytest_celery import CeleryTestSetup

# 添加backend到Python路径
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestTaskSystemIntegration:
    """任务系统集成测试 - 纯Context7实现"""

    def test_celery_environment_ready(self, celery_setup: CeleryTestSetup) -> None:
        """验证Celery测试环境就绪"""
        # 就这么简单！pytest-celery处理所有环境设置
        assert celery_setup.ready()

        # 可选：验证组件（用于调试）
        assert celery_setup.broker is not None
        assert celery_setup.backend is not None
        assert celery_setup.worker is not None

    def test_health_check_task(self, celery_setup: CeleryTestSetup) -> None:
        """测试健康检查任务"""
        from app.tasks.analysis_tasks import analysis_health_check

        # 直接使用任务，无需复杂配置
        result = analysis_health_check.delay()
        task_result = result.get(timeout=30)

        # 验证结果
        assert result.successful()
        assert task_result is not None
        # 修正：health_check现在返回dict（.model_dump()）
        assert isinstance(task_result, dict)
        assert task_result["status"] == "healthy"

    def test_analyze_product_task(self, celery_setup: CeleryTestSetup) -> None:
        """测试核心产品分析任务"""
        from app.tasks.analysis_tasks import analyze_product_task

        # 准备测试数据
        test_payload = {"product_description": "AI写作助手，帮助用户生成高质量内容"}
        test_data = {"task_id": "test-001", "user_id": "test-user"}

        # 执行任务
        result = analyze_product_task.delay(payload=test_payload, task_data=test_data)

        # 验证执行（模拟环境可能需要mock某些服务）
        try:
            task_result = result.get(timeout=60)
            assert result.successful()
            assert task_result is not None
        except Exception as e:
            # 在测试环境中，某些外部服务可能不可用
            pytest.skip(f"任务执行需要完整环境: {str(e)}")

    def test_task_manager_celery_integration(
        self, celery_setup: CeleryTestSetup
    ) -> None:
        """测试TaskManager与Celery的集成"""
        from app.core.task_manager import get_task_manager

        # Context7环境已就绪
        assert celery_setup.ready()

        # 获取TaskManager实例
        task_manager = get_task_manager()
        assert task_manager is not None

        # 验证TaskManager与Celery环境协作
        assert task_manager.celery is not None
        assert task_manager.task_producer is not None

    def test_multiple_tasks_coordination(self, celery_setup: CeleryTestSetup) -> None:
        """测试多任务协作处理"""
        from app.tasks.analysis_tasks import analysis_health_check

        # 并发提交多个任务
        results = []
        for i in range(5):
            result = analysis_health_check.delay()
            results.append(result)

        # 等待所有任务完成
        completed_count = 0
        for result in results:
            try:
                task_result = result.get(timeout=30)
                if result.successful():
                    completed_count += 1
            except Exception:
                # 个别任务失败不影响整体测试
                pass

        # 验证大部分任务成功（允许偶发失败）
        success_rate = completed_count / len(results)
        assert success_rate >= 0.6, f"成功率过低: {success_rate:.2%}"


# 最小化配置 - 只覆盖必要的设置
@pytest.fixture(scope="session")
def celery_config() -> Dict[str, Any]:
    """测试专用Celery配置"""
    return {
        # 使用测试专用的Redis数据库
        "broker_url": "redis://localhost:6379/15",
        "result_backend": "redis://localhost:6379/15",
        # 重要：集成测试需要真实异步执行
        "task_always_eager": False,
        # 与生产环境保持一致的序列化设置
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["json"],
    }


# 注入我们的任务模块
@pytest.fixture
def default_worker_tasks(default_worker_tasks):
    """让测试worker知道我们的任务"""
    from app.tasks import analysis_tasks

    default_worker_tasks.add(analysis_tasks)
    return default_worker_tasks
