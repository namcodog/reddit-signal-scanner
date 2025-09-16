"""
API测试统一架构 v2.0 - Linus原则驱动设计

核心设计哲学：
- "消除特殊情况" - 零条件分支，纯多态设计
- "数据结构优先" - 配置驱动执行，逻辑与数据分离
- "简单胜过聪明" - 单一执行路径，无复杂判断
"""

import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Type, Union
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Task
try:
    from ..conftest import DatabaseTestFactory  # type: ignore
except Exception:
    from tests.conftest import DatabaseTestFactory  # type: ignore


# ============================================================================
# 1. 核心多态架构 - 消除所有条件分支
# ============================================================================


class TestResult:
    """测试结果统一数据结构"""

    def __init__(
        self,
        status_code: int,
        success: bool,
        response_data: Optional[Dict[str, Any]] = None,
        performance_stats: Optional[Dict[str, float]] = None,
        error_message: Optional[str] = None,
    ):
        self.status_code = status_code
        self.success = success
        self.response_data = response_data or {}
        self.performance_stats = performance_stats or {}
        self.error_message = error_message
        self.timestamp = datetime.now()


@dataclass
class TestContext:
    """测试上下文 - 封装所有测试环境数据"""

    client: TestClient
    db_session: AsyncSession
    test_user: Optional[User] = None
    test_task: Optional[Task] = None
    auth_headers: Dict[str, str] = field(default_factory=dict)
    base_url: str = "/api/v1"


class TestScenarioType(Enum):
    NORMAL = "NORMAL"
    BOUNDARY = "BOUNDARY"
    ERROR = "ERROR"
    PERFORMANCE = "PERFORMANCE"


@dataclass
class PerformanceSpec:
    target_response_time_ms: float
    max_tolerance_ratio: float = 1.5
    iterations: int = 50
    warmup_iterations: int = 5


@dataclass
class TestScenario:
    name: str
    scenario_type: TestScenarioType
    method: str
    path: str
    expected_status: int = 200
    params: Dict[str, Any] | None = None
    headers: Dict[str, str] | None = None
    expected_response_schema: Dict[str, Any] | None = None
    performance_spec: PerformanceSpec | None = None
    description: str = ""

    def validate_response(self, response: httpx.Response, result: TestResult) -> None:
        assert response.status_code == self.expected_status, (
            f"状态码不匹配。期望: {self.expected_status}, 实际: {response.status_code}\n"
            f"响应内容: {response.text}"
        )


# ============================================================================
# 2. 基础场景类型 - 四种主要场景模式
# ============================================================================


class NormalScenario(TestScenario):
    """正常流程场景基类"""

    def __init__(
        self, endpoint: str, method: str = "GET", json_data: Optional[Dict] = None
    ):
        super().__init__(endpoint, f"正常场景: {method} {endpoint}")
        self.method = method
        self.json_data = json_data

    async def execute(self, context: TestContext) -> TestResult:
        """标准请求执行"""
        response = context.client.request(
            method=self.method,
            url=f"{context.base_url}{self.endpoint}",
            headers=context.auth_headers,
            json=self.json_data,
        )

        result = TestResult(
            status_code=response.status_code,
            success=response.status_code == self.get_expected_status(),
            response_data=self._safe_parse_json(response),
        )

        self.validate_response(response, result)
        return result

    def get_expected_status(self) -> int:
        return 201 if self.method == "POST" else 200

    def _safe_parse_json(self, response: httpx.Response) -> Dict[str, Any]:
        """安全JSON解析"""
        try:
            return response.json()
        except (ValueError, json.JSONDecodeError):
            return {"raw_content": response.text}


class BoundaryScenario(TestScenario):
    """边界条件场景基类"""

    def __init__(
        self,
        endpoint: str,
        method: str = "GET",
        boundary_data: Optional[Dict] = None,
        boundary_type: str = "unknown",
    ):
        super().__init__(endpoint, f"边界条件: {boundary_type}")
        self.method = method
        self.boundary_data = boundary_data
        self.boundary_type = boundary_type

    async def execute(self, context: TestContext) -> TestResult:
        """边界条件请求执行"""
        response = context.client.request(
            method=self.method,
            url=f"{context.base_url}{self.endpoint}",
            headers=context.auth_headers,
            json=self.boundary_data,
        )

        result = TestResult(
            status_code=response.status_code,
            success=response.status_code == self.get_expected_status(),
            response_data=self._safe_parse_json(response),
        )

        self.validate_response(response, result)
        return result

    def get_expected_status(self) -> int:
        return 200  # 边界条件通常应该成功

    def _safe_parse_json(self, response: httpx.Response) -> Dict[str, Any]:
        try:
            return response.json()
        except:
            return {"raw_content": response.text}


class ErrorScenario(TestScenario):
    """错误场景基类"""

    def __init__(
        self,
        endpoint: str,
        method: str = "GET",
        error_data: Optional[Dict] = None,
        error_headers: Optional[Dict] = None,
        expected_status: int = 400,
        error_type: str = "client_error",
    ):
        super().__init__(endpoint, f"错误场景: {error_type}")
        self.method = method
        self.error_data = error_data
        self.error_headers = error_headers or {}
        self.expected_status = expected_status
        self.error_type = error_type

    async def execute(self, context: TestContext) -> TestResult:
        """错误场景请求执行"""
        headers = {**context.auth_headers, **self.error_headers}

        response = context.client.request(
            method=self.method,
            url=f"{context.base_url}{self.endpoint}",
            headers=headers,
            json=self.error_data,
        )

        result = TestResult(
            status_code=response.status_code,
            success=response.status_code == self.expected_status,
            response_data=self._safe_parse_json(response),
            error_message=self._extract_error_message(response),
        )

        self.validate_response(response, result)
        return result

    def get_expected_status(self) -> int:
        return self.expected_status

    def _safe_parse_json(self, response: httpx.Response) -> Dict[str, Any]:
        try:
            return response.json()
        except:
            return {"raw_content": response.text}

    def _extract_error_message(self, response: httpx.Response) -> Optional[str]:
        """提取错误消息"""
        try:
            data = response.json()
            return data.get("detail", response.text)
        except:
            return response.text


class PerformanceScenario(TestScenario):
    """性能测试场景基类"""

    def __init__(
        self,
        endpoint: str,
        method: str = "GET",
        test_data: Optional[Dict] = None,
        target_ms: float = 100.0,
        iterations: int = 50,
        warmup: int = 5,
    ):
        super().__init__(endpoint, f"性能测试: 目标{target_ms}ms")
        self.method = method
        self.test_data = test_data
        self.target_ms = target_ms
        self.iterations = iterations
        self.warmup = warmup

    async def execute(self, context: TestContext) -> TestResult:
        """性能测试执行"""
        # 预热
        for _ in range(self.warmup):
            context.client.request(
                method=self.method,
                url=f"{context.base_url}{self.endpoint}",
                headers=context.auth_headers,
                json=self.test_data,
            )

        # 实际测量
        measurements = []
        for _ in range(self.iterations):
            start_time = datetime.now()
            response = context.client.request(
                method=self.method,
                url=f"{context.base_url}{self.endpoint}",
                headers=context.auth_headers,
                json=self.test_data,
            )
            end_time = datetime.now()

            duration_ms = (end_time - start_time).total_seconds() * 1000
            measurements.append(duration_ms)

        # 统计分析
        avg_ms = sum(measurements) / len(measurements)
        max_ms = max(measurements)
        min_ms = min(measurements)

        performance_stats = {
            "average_ms": avg_ms,
            "min_ms": min_ms,
            "max_ms": max_ms,
            "target_ms": self.target_ms,
            "measurements_count": len(measurements),
            "passed": avg_ms <= self.target_ms,
        }

        result = TestResult(
            status_code=response.status_code,
            success=avg_ms <= self.target_ms
            and response.status_code == self.get_expected_status(),
            response_data=self._safe_parse_json(response),
            performance_stats=performance_stats,
        )

        # 性能断言
        assert (
            avg_ms <= self.target_ms
        ), f"性能未达标: 平均{avg_ms:.2f}ms > 目标{self.target_ms}ms"

        self.validate_response(response, result)
        return result

    def get_expected_status(self) -> int:
        return 200

    def _safe_parse_json(self, response: httpx.Response) -> Dict[str, Any]:
        try:
            return response.json()
        except:
            return {"raw_content": response.text}


# 统一的API测试基类，供具体端点用例继承
class BaseAPITest(ABC):
    @property
    @abstractmethod
    def test_spec(self) -> Any:
        ...

    async def setup_test_environment(self, db_session: AsyncSession) -> None:
        pass

    async def execute_test_suite(
        self,
        client: TestClient,
        db_session: AsyncSession,
        scenario_type: Optional[Type[TestScenario]] = None,
    ) -> Dict[str, Any]:
        await self.setup_test_environment(db_session)

        # 构建上下文
        context = await TestEnvironmentBuilder.build_context(
            client=client,
            db_session=db_session,
            requires_auth=getattr(self.test_spec, "requires_auth", True),
            requires_task=getattr(self.test_spec, "requires_task_setup", True),
        )

        # 选择场景
        scenarios = self.test_spec.scenarios
        if scenario_type is not None:
            scenarios = [s for s in scenarios if s.scenario_type == scenario_type]

        executor = UnifiedTestExecutor()
        return await executor.execute_scenarios(scenarios, context)


@dataclass
class APITestSpec:
    endpoint_name: str
    base_path: str
    requires_auth: bool = True
    requires_task_setup: bool = True
    scenarios: List[TestScenario] = field(default_factory=list)


# ============================================================================
# 3. 统一测试执行器 - 零条件分支设计
# ============================================================================


class UnifiedTestExecutor:
    """统一测试执行器 - Linus架构的核心

    零条件分支，纯多态驱动
    所有特殊逻辑通过场景类封装
    """

    def __init__(self):
        self.results: List[TestResult] = []

    async def execute_scenarios(
        self, scenarios: List[TestScenario], context: TestContext
    ) -> Dict[str, Any]:
        """执行测试场景列表 - 单一执行路径"""

        results = {
            "total_scenarios": len(scenarios),
            "passed": 0,
            "failed": 0,
            "scenario_results": [],
        }

        for scenario in scenarios:
            try:
                # 纯多态调用，无条件判断
                result = await scenario.execute(context)

                if result.success:
                    results["passed"] += 1
                    status = "PASSED"
                else:
                    results["failed"] += 1
                    status = "FAILED"

                results["scenario_results"].append(
                    {
                        "scenario": scenario.__class__.__name__,
                        "description": scenario.description,
                        "status": status,
                        "result": {
                            "status_code": result.status_code,
                            "success": result.success,
                            "performance_stats": result.performance_stats,
                            "error_message": result.error_message,
                        },
                    }
                )

            except Exception as e:
                results["failed"] += 1
                results["scenario_results"].append(
                    {
                        "scenario": scenario.__class__.__name__,
                        "description": scenario.description,
                        "status": "ERROR",
                        "error": str(e),
                    }
                )

        return results

    async def filter_and_execute(
        self,
        scenarios: List[TestScenario],
        context: TestContext,
        scenario_types: Optional[List[Type[TestScenario]]] = None,
    ) -> Dict[str, Any]:
        """过滤并执行指定类型的场景"""

        if scenario_types:
            filtered_scenarios = [
                s
                for s in scenarios
                if any(isinstance(s, scenario_type) for scenario_type in scenario_types)
            ]
        else:
            filtered_scenarios = scenarios

        return await self.execute_scenarios(filtered_scenarios, context)


# ============================================================================
# 4. 环境设置工具 - 统一的测试环境管理
# ============================================================================


class TestEnvironmentBuilder:
    """测试环境构建器 - 统一环境设置"""

    @staticmethod
    async def build_context(
        client: TestClient,
        db_session: AsyncSession,
        requires_auth: bool = False,
        requires_task: bool = False,
    ) -> TestContext:
        """构建测试上下文"""

        context = TestContext(client=client, db_session=db_session)

        # 创建测试用户
        if requires_auth or requires_task:
            test_user = User(
                **DatabaseTestFactory.minimal_valid_user(
                    email=f"test-{uuid.uuid4()}@example.com"
                )
            )
            db_session.add(test_user)
            await db_session.commit()
            await db_session.refresh(test_user)

            context.test_user = test_user
            context.auth_headers = {
                "Authorization": f"Bearer test-token-{test_user.id}",
                "X-Tenant-ID": str(test_user.tenant_id),
            }

        # 创建测试任务
        if requires_task and context.test_user:
            test_task = Task(
                **DatabaseTestFactory.minimal_valid_task(
                    user_id=context.test_user.id,
                    product_description=f"测试任务 - {uuid.uuid4()}",
                )
            )
            db_session.add(test_task)
            await db_session.commit()
            await db_session.refresh(test_task)

            context.test_task = test_task

        return context


# ============================================================================
# 5. 导出接口 - 统一API
# ============================================================================

__all__ = [
    # 核心多态类
    "TestScenario",
    "TestResult",
    "TestContext",
    "APITestSpec",
    "TestScenarioType",
    "PerformanceSpec",
    # 场景基类
    "NormalScenario",
    "BoundaryScenario",
    "ErrorScenario",
    "PerformanceScenario",
    # 执行器
    "UnifiedTestExecutor",
    # 环境工具
    "TestEnvironmentBuilder",
]
