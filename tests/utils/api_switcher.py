"""API切换器 - 实现Mock/Real API的动态切换。

支持四层测试金字塔的不同需求：
- 单元测试：始终Mock
- 集成测试：可选切换
- 系统测试：优先Real
- 验收测试：必须Real
"""

from __future__ import annotations

import asyncio
import functools
import os
from typing import Any, Awaitable, Callable, Dict, Iterator, List, Optional, TypeVar, cast

import httpx
import pytest


T = TypeVar("T")
R = TypeVar("R")


class ApiSwitcher:
    """API切换器 - 管理Mock和Real API之间的切换"""

    def __init__(self) -> None:
        self.original_mode = os.getenv("TEST_USE_MOCK_API", "true").lower() == "true"
        self.current_mode = self.original_mode
        self._mock_patches: List[Any] = []
        self._health_check_cache: Dict[str, bool] = {}

    @property
    def is_mock_mode(self) -> bool:
        """当前是否为Mock模式"""
        return self.current_mode

    def switch_to_mock(self) -> None:
        """切换到Mock模式"""
        self.current_mode = True
        os.environ["TEST_USE_MOCK_API"] = "true"
        self._apply_mock_patches()

    def switch_to_real(self, health_check_url: Optional[str] = None) -> None:
        """切换到真实模式"""
        if health_check_url and not self._check_api_health(health_check_url):
            raise pytest.skip(f"真实API不可用: {health_check_url}")

        self.current_mode = False
        os.environ["TEST_USE_MOCK_API"] = "false"
        self._remove_mock_patches()

    def auto_switch(self, test_layer: str) -> None:
        """根据测试层级自动切换"""
        layer_configs = {
            "unit": {"use_mock": True, "force": True},
            "integration": {"use_mock": True, "force": False},
            "system": {"use_mock": False, "force": False},
            "acceptance": {"use_mock": False, "force": True},
        }

        config = layer_configs.get(test_layer, {"use_mock": True, "force": False})

        if config["use_mock"]:
            self.switch_to_mock()
        else:
            try:
                self.switch_to_real()
            except pytest.skip.Exception:
                if not config["force"]:
                    self.switch_to_mock()
                else:
                    raise

    def restore(self) -> None:
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

    def _apply_mock_patches(self) -> None:
        """应用Mock补丁（占位，后续可扩展具体逻辑）。"""
        if not self._mock_patches:
            return
        for patcher in self._mock_patches:
            patcher.start()

    def _remove_mock_patches(self) -> None:
        """移除Mock补丁"""
        for patcher in self._mock_patches:
            patcher.stop()
        self._mock_patches.clear()


class ServiceSwitcher:
    """服务级别的切换器 - 更细粒度的控制"""

    def __init__(self, api_switcher: ApiSwitcher) -> None:
        self.api_switcher = api_switcher
        self._service_overrides: Dict[str, Any] = {}

    def override_service(self, service_name: str, mock_instance: Any) -> None:
        """覆盖特定服务的实现"""
        self._service_overrides[service_name] = mock_instance

    def get_service(
        self,
        service_name: str,
        real_factory: Callable[[], T],
        mock_factory: Callable[[], T],
    ) -> T:
        """根据当前模式返回真实或 Mock 服务"""
        if service_name in self._service_overrides:
            return cast(T, self._service_overrides[service_name])

        if self.api_switcher.is_mock_mode:
            return mock_factory()
        return real_factory()

    def clear_overrides(self) -> None:
        """清除所有服务覆盖"""
        self._service_overrides.clear()


def with_api_mode(
    mode: str = "auto", layer: Optional[str] = None
) -> Callable[[Callable[..., R]], Callable[..., R]]:
    """测试装饰器 - 自动管理API模式"""

    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> R:
                switcher = ApiSwitcher()
                try:
                    if mode == "mock":
                        switcher.switch_to_mock()
                    elif mode == "real":
                        switcher.switch_to_real()
                    elif mode == "auto" and layer:
                        switcher.auto_switch(layer)

                    async_func = cast(Callable[..., Awaitable[R]], func)
                    return await async_func(*args, **kwargs)
                finally:
                    switcher.restore()

            return cast(Callable[..., R], async_wrapper)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> R:
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

        return sync_wrapper

    return decorator


class ContractValidator:
    """契约验证器 - 确保Mock和Real API返回相同的数据结构"""

    def __init__(self) -> None:
        self.contracts: Dict[str, Dict[str, Any]] = {}

    def register_contract(self, endpoint: str, schema: Any) -> None:
        """注册API契约"""
        self.contracts[endpoint] = {
            "schema": schema,
            "mock_responses": [],
            "real_responses": [],
        }

    def validate_response(self, endpoint: str, response: Any, is_mock: bool = True) -> None:
        """验证响应是否符合契约"""
        if endpoint not in self.contracts:
            return

        contract = self.contracts[endpoint]
        schema = contract["schema"]

        try:
            if hasattr(schema, "model_validate"):
                schema.model_validate(response)
            elif hasattr(schema, "parse_obj"):
                schema.parse_obj(response)
        except Exception as exc:  # pragma: no cover - 调试信息
            raise AssertionError(
                f"{'Mock' if is_mock else 'Real'} API响应不符合契约: {exc}"
            ) from exc

        target_key = "mock_responses" if is_mock else "real_responses"
        contract[target_key].append(response)

    def compare_responses(self, endpoint: str) -> None:
        """比较Mock和Real API的响应结构"""
        if endpoint not in self.contracts:
            return

        contract = self.contracts[endpoint]
        mock_responses = contract["mock_responses"]
        real_responses = contract["real_responses"]

        if not mock_responses or not real_responses:
            return

        for mock, real in zip(mock_responses, real_responses):
            self._compare_structure(mock, real)

    def _compare_structure(self, mock_data: Any, real_data: Any, path: str = "") -> None:
        """递归比较数据结构"""
        if type(mock_data) is not type(real_data):
            raise AssertionError(
                f"数据类型不匹配 at {path}: Mock={type(mock_data).__name__}, "
                f"Real={type(real_data).__name__}"
            )

        if isinstance(mock_data, dict):
            mock_keys = set(mock_data.keys())
            real_keys = set(real_data.keys())

            if mock_keys != real_keys:
                missing_in_mock = real_keys - mock_keys
                missing_in_real = mock_keys - real_keys
                raise AssertionError(
                    f"字段不匹配 at {path}: Mock缺少={missing_in_mock}, "
                    f"Real缺少={missing_in_real}"
                )

            for key in mock_keys:
                next_path = f"{path}.{key}" if path else key
                self._compare_structure(mock_data[key], real_data[key], next_path)

        elif isinstance(mock_data, list) and mock_data and real_data:
            self._compare_structure(mock_data[0], real_data[0], f"{path}[0]")


@pytest.fixture
def api_switcher() -> Iterator[ApiSwitcher]:
    """API切换器fixture"""
    switcher = ApiSwitcher()
    try:
        yield switcher
    finally:
        switcher.restore()


@pytest.fixture
def service_switcher(api_switcher: ApiSwitcher) -> Iterator[ServiceSwitcher]:
    """服务切换器fixture"""
    service = ServiceSwitcher(api_switcher)
    try:
        yield service
    finally:
        service.clear_overrides()


@pytest.fixture
def contract_validator() -> ContractValidator:
    """契约验证器fixture"""
    return ContractValidator()


@pytest.fixture
def auto_api_mode(request: pytest.FixtureRequest) -> Iterator[ApiSwitcher]:
    """自动API模式fixture - 根据测试标记自动切换"""
    switcher = ApiSwitcher()

    markers = request.node.iter_markers()
    test_layer: Optional[str] = None

    for marker in markers:
        if marker.name in {"unit", "integration", "system", "acceptance"}:
            test_layer = marker.name
            break

    if not test_layer:
        test_layer = "unit"

    switcher.auto_switch(test_layer)

    try:
        yield switcher
    finally:
        switcher.restore()


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
