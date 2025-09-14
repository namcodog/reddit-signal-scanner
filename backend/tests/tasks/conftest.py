"""
Context7标准pytest-celery集成测试配置
严格遵循pytest-celery最佳实践和类型安全

基于Context7文档：
- 使用CeleryTestSetup进行环境矩阵测试
- 真实的Redis容器环境
- 动态任务注入机制
- 100%类型安全
"""
from typing import Any, Dict, Optional, Set
import pytest

# 添加backend到Python路径
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.tasks.analysis_tasks import (
    analyze_product_task,
    batch_analyze_products,
    analysis_health_check,
)

# 注册本地worker夹具（用于CONTEXT7_USE_LOCAL_WORKER=1时）
try:
    from ._local_worker import celery_app_instance, local_celery_worker  # noqa: F401
except Exception:
    pass


@pytest.fixture
def default_worker_tasks(default_worker_tasks: Set[Any]) -> Set[Any]:
    """
    Context7标准：动态注入我们的任务到worker

    这是pytest-celery的标准模式，用于将应用特定的任务
    注入到测试worker中，确保集成测试的完整性。

    Args:
        default_worker_tasks: pytest-celery提供的默认任务集合

    Returns:
        Set[Any]: 包含我们任务的集合
    """
    # 导入我们的任务模块
    from app.tasks import analysis_tasks

    # Context7模式：添加整个模块而不是单个任务
    default_worker_tasks.add(analysis_tasks)
    return default_worker_tasks


@pytest.fixture
def default_worker_signals(default_worker_signals: Set[Any]) -> Set[Any]:
    """
    Context7标准：动态注入信号处理器

    Args:
        default_worker_signals: pytest-celery提供的默认信号集合

    Returns:
        Set[Any]: 包含我们信号的集合
    """
    # 如果有自定义信号处理器，在这里添加
    # 目前我们使用默认信号
    return default_worker_signals


@pytest.fixture(scope="session")
def celery_config() -> Dict[str, Any]:
    """
    Context7标准：Celery配置

    提供与生产环境一致的配置，但适配测试环境

    Returns:
        Dict[str, Any]: Celery配置字典
    """
    return {
        # Context7推荐：使用Redis作为broker和backend
        "broker_url": "redis://localhost:6379/1",  # 测试数据库
        "result_backend": "redis://localhost:6379/1",
        # 测试优化配置
        "task_always_eager": False,  # 重要：集成测试需要真实异步
        "task_eager_propagates": True,
        "worker_hijack_root_logger": False,
        # 结果配置
        "result_expires": 300,  # 5分钟过期
        "result_persistent": True,
        # 连接配置
        "broker_connection_retry_on_startup": True,
        "broker_connection_max_retries": 3,
        # 任务路由（与生产保持一致）
        "task_routes": {
            "app.tasks.analysis_tasks.analyze_product": {"queue": "analysis"},
            "app.tasks.analysis_tasks.batch_analyze_products": {
                "queue": "batch_analysis"
            },
        },
        # 队列配置
        "task_default_queue": "default",
        "task_create_missing_queues": True,
    }


@pytest.fixture(scope="session")
def celery_worker_parameters() -> Dict[str, Any]:
    """
    Context7标准：Worker参数配置

    Returns:
        Dict[str, Any]: Worker启动参数
    """
    return {
        "without_heartbeat": False,
        "loglevel": "INFO",
        "concurrency": 2,  # 测试环境使用较少并发
        "queues": ["default", "analysis", "batch_analysis"],
    }


# Context7推荐：测试特定的数据类型定义
class TaskTestData:
    """任务测试数据类型定义"""

    def __init__(
        self,
        product_description: str,
        expected_status: str = "SUCCESS",
        timeout_seconds: int = 30,
    ) -> None:
        self.product_description = product_description
        self.expected_status = expected_status
        self.timeout_seconds = timeout_seconds


@pytest.fixture
def sample_task_data() -> TaskTestData:
    """
    提供标准的任务测试数据

    Returns:
        TaskTestData: 测试数据实例
    """
    return TaskTestData(
        product_description="AI写作助手，帮助用户生成高质量内容",
        expected_status="SUCCESS",
        timeout_seconds=30,
    )


@pytest.fixture
def batch_task_data() -> list[TaskTestData]:
    """
    提供批量任务测试数据

    Returns:
        list[TaskTestData]: 批量测试数据
    """
    return [
        TaskTestData("AI写作助手"),
        TaskTestData("智能客服机器人"),
        TaskTestData("数据分析平台"),
        TaskTestData("在线教育系统"),
        TaskTestData("电商推荐引擎"),
    ]


# Context7模式：环境矩阵会自动测试多种配置组合
# CeleryTestSetup会自动为我们提供：
# - RedisTestBroker + RedisTestBackend 组合
# - 真实的容器环境
# - 自动清理和隔离
# - 并行测试支持
