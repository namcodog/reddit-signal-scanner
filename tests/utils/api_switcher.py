"""API切换器 - 实现Mock/Real API的动态切换

支持四层测试金字塔的不同需求：
- 单元测试：始终Mock
- 集成测试：可选切换
- 系统测试：优先Real
- 验收测试：必须Real
"""

import os
from typing import Any, Callable, Dict, Optional, TypeVar, Union
from unittest.mock import MagicMock, patch

import httpx
import pytest

from tests.fixtures.mock_services import MockServiceFactory


T = TypeVar('T')


class ApiSwitcher:
    """API切换器 - 管理Mock和Real API之间的切换"""
    
    def __init__(self):
        self.original_mode = os.getenv("TEST_USE_MOCK_API", "true").lower() == "true"
        self.current_mode = self.original_mode
        self._mock_patches = []
        self._health_check_cache = {}
        
    @property
    def is_mock_mode(self) -> bool:
        """当前是否为Mock模式"""
        return self.current_mode
    
    def switch_to_mock(self):
        """切换到Mock模式"""
        self.current_mode = True
        os.environ["TEST_USE_MOCK_API"] = "true"
        self._apply_mock_patches()
        
    def switch_to_real(self, health_check_url: Optional[str] = None):
        """切换到真实模式"""
        # 可选的健康检查
        if health_check_url and not self._check_api_health(health_check_url):
            raise pytest.skip(f"真实API不可用: {health_check_url}")
            
        self.current_mode = False
        os.environ["TEST_USE_MOCK_API"] = "false"
        self._remove_mock_patches()
        
    def auto_switch(self, test_layer: str):
        """根据测试层级自动切换"""
        layer_configs = {
            "unit": {"use_mock": True, "force": True},
            "integration": {"use_mock": True, "force": False},
            "system": {"use_mock": False, "force": False},
            "acceptance": {"use_mock": False, "force": True}
        }
        
        config = layer_configs.get(test_layer, {"use_mock": True, "force": False})
        
        if config["use_mock"]:
            self.switch_to_mock()
        else:
            # 对于非强制Real的情况，如果Real API不可用则回退到Mock
            try:
                self.switch_to_real()
            except pytest.skip.Exception:
                if not config["force"]:
                    self.switch_to_mock()
                else:
                    raise
                    
    def restore(self):
        """恢复原始模式"""
        if self.original_mode:
            self.switch_to_mock()
        else:
            self.switch_to_real()
            
    def _check_api_health(self, url: str) -> bool:
        """检查API健康状态（带缓存）"""
        if url in self._health_check_cache:
            return self._health_check_cache[url]
            
        try:
            response = httpx.get(url, timeout=5)
            is_healthy = response.status_code == 200
            self._health_check_cache[url] = is_healthy
            return is_healthy
        except Exception:
            self._health_check_cache[url] = False
            return False
            
    def _apply_mock_patches(self):
        """应用Mock补丁"""
        # 这里可以添加具体的Mock补丁
        # 例如：patch('app.services.reddit_client.RedditClient', MockRedditClient)
        pass
        
    def _remove_mock_patches(self):
        """移除Mock补丁"""
        for p in self._mock_patches:
            p.stop()
        self._mock_patches.clear()


class ServiceSwitcher:
    """服务级别的切换器 - 更细粒度的控制"""
    
    def __init__(self, api_switcher: ApiSwitcher):
        self.api_switcher = api_switcher
        self._service_overrides: Dict[str, Any] = {}
        
    def override_service(self, service_name: str, mock_instance: Any):
        """覆盖特定服务的实现"""
        self._service_overrides[service_name] = mock_instance
        
    def get_service(self, service_name: str, real_factory: Callable[[], T], mock_factory: Callable[[], T]) -> T:
        """获取服务实例（根据当前模式）"""
        # 检查是否有覆盖
        if service_name in self._service_overrides:
            return self._service_overrides[service_name]
            
        # 根据模式返回相应的实例
        if self.api_switcher.is_mock_mode:
            return mock_factory()
        else:
            return real_factory()
            
    def clear_overrides(self):
        """清除所有服务覆盖"""
        self._service_overrides.clear()


# ==================== 装饰器 ====================
def with_api_mode(mode: str = "auto", layer: Optional[str] = None):
    """测试装饰器 - 自动管理API模式
    
    Args:
        mode: "mock", "real", 或 "auto"
        layer: 测试层级（用于auto模式）
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            switcher = ApiSwitcher()
            
            try:
                if mode == "mock":
                    switcher.switch_to_mock()
                elif mode == "real":
                    switcher.switch_to_real()
                elif mode == "auto" and layer:
                    switcher.auto_switch(layer)
                    
                return func(*args, **kwargs)
            finally:
                switcher.restore()
                
        return wrapper
    return decorator


# ==================== 契约验证 ====================
class ContractValidator:
    """契约验证器 - 确保Mock和Real API返回相同的数据结构"""
    
    def __init__(self):
        self.contracts: Dict[str, Dict[str, Any]] = {}
        
    def register_contract(self, endpoint: str, schema: Any):
        """注册API契约"""
        self.contracts[endpoint] = {
            "schema": schema,
            "mock_responses": [],
            "real_responses": []
        }
        
    def validate_response(self, endpoint: str, response: Any, is_mock: bool = True):
        """验证响应是否符合契约"""
        if endpoint not in self.contracts:
            return
            
        contract = self.contracts[endpoint]
        schema = contract["schema"]
        
        # 验证响应格式
        try:
            if hasattr(schema, 'model_validate'):  # Pydantic v2
                schema.model_validate(response)
            elif hasattr(schema, 'parse_obj'):  # Pydantic v1
                schema.parse_obj(response)
        except Exception as e:
            raise AssertionError(
                f"{'Mock' if is_mock else 'Real'} API响应不符合契约: {e}"
            )
            
        # 记录响应用于后续比较
        if is_mock:
            contract["mock_responses"].append(response)
        else:
            contract["real_responses"].append(response)
            
    def compare_responses(self, endpoint: str):
        """比较Mock和Real API的响应"""
        if endpoint not in self.contracts:
            return
            
        contract = self.contracts[endpoint]
        mock_responses = contract["mock_responses"]
        real_responses = contract["real_responses"]
        
        if not mock_responses or not real_responses:
            return
            
        # 比较响应的结构（不比较具体值）
        for mock, real in zip(mock_responses, real_responses):
            self._compare_structure(mock, real)
            
    def _compare_structure(self, mock_data: Any, real_data: Any, path: str = ""):
        """递归比较数据结构"""
        if type(mock_data) != type(real_data):
            raise AssertionError(
                f"数据类型不匹配 at {path}: "
                f"Mock={type(mock_data).__name__}, Real={type(real_data).__name__}"
            )
            
        if isinstance(mock_data, dict):
            mock_keys = set(mock_data.keys())
            real_keys = set(real_data.keys())
            
            if mock_keys != real_keys:
                missing_in_mock = real_keys - mock_keys
                missing_in_real = mock_keys - real_keys
                raise AssertionError(
                    f"字段不匹配 at {path}: "
                    f"Mock缺少={missing_in_mock}, Real缺少={missing_in_real}"
                )
                
            for key in mock_keys:
                self._compare_structure(
                    mock_data[key], 
                    real_data[key], 
                    f"{path}.{key}" if path else key
                )
                
        elif isinstance(mock_data, list) and mock_data and real_data:
            # 只比较第一个元素的结构
            self._compare_structure(
                mock_data[0], 
                real_data[0], 
                f"{path}[0]"
            )


# ==================== Pytest Fixtures ====================
@pytest.fixture
def api_switcher():
    """API切换器fixture"""
    switcher = ApiSwitcher()
    yield switcher
    switcher.restore()


@pytest.fixture
def service_switcher(api_switcher):
    """服务切换器fixture"""
    switcher = ServiceSwitcher(api_switcher)
    yield switcher
    switcher.clear_overrides()


@pytest.fixture
def contract_validator():
    """契约验证器fixture"""
    return ContractValidator()


@pytest.fixture
def auto_api_mode(request):
    """自动API模式fixture - 根据测试标记自动切换"""
    switcher = ApiSwitcher()
    
    # 检查测试标记
    markers = request.node.iter_markers()
    test_layer = None
    
    for marker in markers:
        if marker.name in ["unit", "integration", "system", "acceptance"]:
            test_layer = marker.name
            break
            
    # 如果没有标记，默认使用单元测试模式
    if not test_layer:
        test_layer = "unit"
        
    switcher.auto_switch(test_layer)
    
    yield switcher
    
    switcher.restore()


# ==================== 导出 ====================
__all__ = [
    "ApiSwitcher",
    "ServiceSwitcher",
    "ContractValidator",
    "with_api_mode",
    "api_switcher",
    "service_switcher",
    "contract_validator",
    "auto_api_mode",
]