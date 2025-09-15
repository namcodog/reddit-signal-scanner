"""基础测试Fixtures - 四层测试金字塔通用fixture

基于Linus原则：数据结构优先，消除特殊情况
"""

import asyncio
import os
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Generator, Optional

import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

# 环境变量配置
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost:5432/reddit_test"
)
TEST_USE_MOCK_API = os.getenv("TEST_USE_MOCK_API", "true").lower() == "true"
TEST_API_TIMEOUT = int(os.getenv("TEST_API_TIMEOUT", "30"))


class TestLayerMarker:
    """测试层级标记器 - 确保测试被正确分类"""
    
    UNIT = pytest.mark.unit
    INTEGRATION = pytest.mark.integration
    SYSTEM = pytest.mark.system
    ACCEPTANCE = pytest.mark.acceptance
    
    @staticmethod
    def get_layer_from_test(test_func) -> str:
        """获取测试函数的层级"""
        markers = getattr(test_func, "pytestmark", [])
        for marker in markers:
            if hasattr(marker, "name") and marker.name in ["unit", "integration", "system", "acceptance"]:
                return marker.name
        return "unknown"


# ==================== 事件循环配置 ====================
@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环 - session级别"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ==================== 测试隔离装饰器 ====================
class TestIsolation:
    """测试隔离工具类"""
    
    @staticmethod
    def unit_test(func):
        """单元测试装饰器 - 完全隔离"""
        @pytest.mark.unit
        @pytest.mark.mock_api
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    
    @staticmethod
    def integration_test(func):
        """集成测试装饰器 - 部分隔离"""
        @pytest.mark.integration
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    
    @staticmethod
    def system_test(func):
        """系统测试装饰器 - 真实环境"""
        @pytest.mark.system
        @pytest.mark.real_api
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    
    @staticmethod
    def acceptance_test(func):
        """验收测试装饰器 - 完全真实"""
        @pytest.mark.acceptance
        @pytest.mark.real_api
        @pytest.mark.slow
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper


# ==================== 性能计时器 ====================
@pytest.fixture
def performance_timer():
    """性能计时器fixture"""
    import time
    
    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
            self.duration = None
            self.checkpoints = {}
        
        def start(self):
            """开始计时"""
            self.start_time = time.time()
            return self
        
        def checkpoint(self, name: str):
            """记录检查点"""
            self.checkpoints[name] = time.time()
            
        def stop(self):
            """停止计时"""
            self.end_time = time.time()
            if self.start_time:
                self.duration = self.end_time - self.start_time
            return self.duration
        
        def get_duration(self) -> Optional[float]:
            """获取持续时间"""
            return self.duration
        
        def assert_performance(self, max_seconds: float):
            """断言性能要求"""
            if self.duration is None:
                self.stop()
            assert self.duration <= max_seconds, (
                f"性能未达标: {self.duration:.2f}s > {max_seconds}s"
            )
    
    return Timer()


# ==================== Mock/Real切换器 ====================
@pytest.fixture
def api_mode_switcher():
    """API模式切换器 - 支持Mock/Real动态切换"""
    
    class ApiModeSwitcher:
        def __init__(self):
            self.original_mode = TEST_USE_MOCK_API
            self.current_mode = self.original_mode
        
        def use_mock(self):
            """切换到Mock模式"""
            self.current_mode = True
            os.environ["TEST_USE_MOCK_API"] = "true"
            
        def use_real(self):
            """切换到真实模式"""
            # 先检查真实API是否可用
            if not self._check_real_api_health():
                pytest.skip("真实API不可用")
            self.current_mode = False
            os.environ["TEST_USE_MOCK_API"] = "false"
            
        def restore(self):
            """恢复原始模式"""
            os.environ["TEST_USE_MOCK_API"] = str(self.original_mode).lower()
            self.current_mode = self.original_mode
            
        def _check_real_api_health(self) -> bool:
            """检查真实API健康状态"""
            # TODO: 实现真实的健康检查
            return True
            
        @property
        def is_mock(self) -> bool:
            """当前是否为Mock模式"""
            return self.current_mode
    
    switcher = ApiModeSwitcher()
    yield switcher
    switcher.restore()


# ==================== 测试数据清理器 ====================
@pytest.fixture
def test_data_cleaner():
    """测试数据清理器 - 确保测试后数据清理"""
    created_ids = {
        "users": [],
        "tasks": [],
        "analyses": [],
    }
    
    class TestDataCleaner:
        def track_user(self, user_id: uuid.UUID):
            """追踪创建的用户"""
            created_ids["users"].append(user_id)
            
        def track_task(self, task_id: uuid.UUID):
            """追踪创建的任务"""
            created_ids["tasks"].append(task_id)
            
        def track_analysis(self, analysis_id: uuid.UUID):
            """追踪创建的分析"""
            created_ids["analyses"].append(analysis_id)
            
        async def cleanup(self, session: AsyncSession):
            """清理所有测试数据"""
            # 反向删除以避免外键约束
            for analysis_id in reversed(created_ids["analyses"]):
                await session.execute(
                    "DELETE FROM analyses WHERE id = :id",
                    {"id": analysis_id}
                )
            
            for task_id in reversed(created_ids["tasks"]):
                await session.execute(
                    "DELETE FROM tasks WHERE id = :id",
                    {"id": task_id}
                )
                
            for user_id in reversed(created_ids["users"]):
                await session.execute(
                    "DELETE FROM users WHERE id = :id",
                    {"id": user_id}
                )
                
            await session.commit()
    
    cleaner = TestDataCleaner()
    yield cleaner
    # 测试结束后自动清理（如果有活动的数据库会话）


# ==================== 断言辅助函数 ====================
class AssertHelpers:
    """断言辅助工具类 - 提供更清晰的断言"""
    
    @staticmethod
    def assert_api_response_ok(response, expected_status: int = 200):
        """断言API响应正常"""
        assert response.status_code == expected_status, (
            f"API响应异常: {response.status_code} != {expected_status}\n"
            f"响应内容: {response.text}"
        )
    
    @staticmethod
    def assert_error_response(response, expected_error_code: str):
        """断言错误响应"""
        assert response.status_code >= 400
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == expected_error_code
    
    @staticmethod
    def assert_performance_within(duration: float, max_seconds: float):
        """断言性能在预期范围内"""
        assert duration <= max_seconds, (
            f"性能未达标: {duration:.2f}s > {max_seconds}s"
        )
    
    @staticmethod
    def assert_data_integrity(data: Dict[str, Any], required_fields: list):
        """断言数据完整性"""
        for field in required_fields:
            assert field in data, f"缺少必需字段: {field}"
            assert data[field] is not None, f"字段不能为空: {field}"


# ==================== 测试配置管理器 ====================
@pytest.fixture(scope="session")
def test_config():
    """测试配置管理器"""
    
    class TestConfig:
        # 数据库配置
        DATABASE_URL = TEST_DATABASE_URL
        USE_REAL_DB = os.getenv("TEST_USE_REAL_DB", "false").lower() == "true"
        
        # API配置
        USE_MOCK_API = TEST_USE_MOCK_API
        API_TIMEOUT = TEST_API_TIMEOUT
        API_BASE_URL = os.getenv("TEST_API_BASE_URL", "http://localhost:8000")
        
        # 性能配置
        MAX_WORKERS = int(os.getenv("TEST_MAX_WORKERS", "4"))
        MEMORY_LIMIT = os.getenv("TEST_MEMORY_LIMIT", "1GB")
        
        # 调试配置
        LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        DEBUG_SQL = os.getenv("DEBUG_SQL", "false").lower() == "true"
        
        # 测试行为配置
        FAIL_FAST = os.getenv("TEST_FAIL_FAST", "true").lower() == "true"
        RETRY_FAILED = int(os.getenv("TEST_RETRY_FAILED", "2"))
        
        def get_layer_config(self, layer: str) -> Dict[str, Any]:
            """获取特定层级的配置"""
            configs = {
                "unit": {
                    "use_mock": True,
                    "timeout": 5,
                    "parallel": True
                },
                "integration": {
                    "use_mock": self.USE_MOCK_API,
                    "timeout": 30,
                    "parallel": False
                },
                "system": {
                    "use_mock": False,
                    "timeout": 60,
                    "parallel": False
                },
                "acceptance": {
                    "use_mock": False,
                    "timeout": 300,
                    "parallel": False
                }
            }
            return configs.get(layer, {})
    
    return TestConfig()


# ==================== 导出的fixture和工具 ====================
__all__ = [
    # Fixtures
    "event_loop",
    "performance_timer",
    "api_mode_switcher",
    "test_data_cleaner",
    "test_config",
    
    # 工具类
    "TestLayerMarker",
    "TestIsolation",
    "AssertHelpers",
]