"""
API测试基类 - 统一架构设计

基于Linus原则和task-analyzer建议：
- 统一的测试数据结构
- 消除特殊情况处理
- 配置驱动的测试执行
- 完整的性能和功能验证
"""

import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union, AsyncIterator
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Task
from tests.conftest import DatabaseTestFactory


class TestScenarioType(Enum):
    """测试场景类型枚举"""

    NORMAL = "normal"  # 正常流程
    BOUNDARY = "boundary"  # 边界条件
    ERROR = "error"  # 错误场景
    PERFORMANCE = "performance"  # 性能测试


@dataclass
class PerformanceSpec:
    """统一的性能规格定义"""

    target_response_time_ms: float
    max_tolerance_ratio: float = 1.2  # 最大容忍倍数
    iterations: int = 100  # 测试迭代次数
    warmup_iterations: int = 10  # 预热迭代


@dataclass
class TestScenario:
    """统一的测试场景定义

    消除了不同端点的特殊处理逻辑
    通过配置驱动生成所有测试用例
    """

    name: str
    scenario_type: TestScenarioType
    method: str
    path: str
    headers: Dict[str, str] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    json_data: Optional[Dict[str, Any]] = None
    expected_status: int = 200
    expected_response_schema: Optional[Dict[str, Any]] = None
    performance_spec: Optional[PerformanceSpec] = None
    description: str = ""

    def __post_init__(self):
        """自动生成描述"""
        if not self.description:
            self.description = (
                f"{self.scenario_type.value}场景: {self.method} {self.path}"
            )


@dataclass
class APITestSpec:
    """API端点测试规格 - 统一数据结构

    基于Linus"数据结构优先"原则设计
    一个结构承载所有API测试需求
    """

    endpoint_name: str
    base_path: str
    scenarios: List[TestScenario] = field(default_factory=list)
    requires_auth: bool = False
    requires_task_setup: bool = False

    @property
    def normal_scenarios(self) -> List[TestScenario]:
        """正常流程场景"""
        return [s for s in self.scenarios if s.scenario_type == TestScenarioType.NORMAL]

    @property
    def boundary_scenarios(self) -> List[TestScenario]:
        """边界条件场景"""
        return [
            s for s in self.scenarios if s.scenario_type == TestScenarioType.BOUNDARY
        ]

    @property
    def error_scenarios(self) -> List[TestScenario]:
        """错误场景"""
        return [s for s in self.scenarios if s.scenario_type == TestScenarioType.ERROR]

    @property
    def performance_scenarios(self) -> List[TestScenario]:
        """性能测试场景"""
        return [
            s for s in self.scenarios if s.scenario_type == TestScenarioType.PERFORMANCE
        ]


class ResponseValidator:
    """统一的响应验证器 - 消除不同端点的验证逻辑差异"""

    @staticmethod
    def validate_response_structure(
        response: httpx.Response, expected_schema: Optional[Dict[str, Any]] = None
    ) -> None:
        """验证响应结构"""
        if not expected_schema:
            return

        try:
            response_data = response.json()
        except json.JSONDecodeError:
            pytest.fail(f"响应不是有效的JSON格式: {response.text}")

        # 验证必需字段
        required_fields = expected_schema.get("required", [])
        for field in required_fields:
            assert field in response_data, f"缺少必需字段: {field}"

        # 验证字段类型
        properties = expected_schema.get("properties", {})
        for field_name, field_spec in properties.items():
            if field_name in response_data:
                ResponseValidator._validate_field_type(
                    response_data[field_name], field_spec, field_name
                )

    @staticmethod
    def _validate_field_type(value: Any, spec: Dict[str, Any], field_name: str) -> None:
        """验证字段类型"""
        expected_type = spec.get("type")
        if expected_type == "string":
            assert isinstance(
                value, str
            ), f"字段{field_name}应为字符串，实际: {type(value)}"
        elif expected_type == "integer":
            assert isinstance(
                value, int
            ), f"字段{field_name}应为整数，实际: {type(value)}"
        elif expected_type == "number":
            assert isinstance(
                value, (int, float, Decimal)
            ), f"字段{field_name}应为数字，实际: {type(value)}"
        elif expected_type == "boolean":
            assert isinstance(
                value, bool
            ), f"字段{field_name}应为布尔值，实际: {type(value)}"
        elif expected_type == "array":
            assert isinstance(
                value, list
            ), f"字段{field_name}应为数组，实际: {type(value)}"
        elif expected_type == "object":
            assert isinstance(
                value, dict
            ), f"字段{field_name}应为对象，实际: {type(value)}"


class BaseAPITest(ABC):
    """API测试基类 - 统一执行引擎

    基于Linus原则的统一设计：
    - 无特殊情况分支处理
    - 配置驱动的测试执行
    - 统一的断言和验证逻辑
    """

    def __init__(self):
        self._test_spec: Optional[APITestSpec] = None
        self._test_user: Optional[User] = None
        self._test_task: Optional[Task] = None
        self._auth_headers: Dict[str, str] = {}

    @property
    @abstractmethod
    def test_spec(self) -> APITestSpec:
        """返回测试规格配置 - 子类必须实现"""
        pass

    async def setup_test_environment(self, db_session: AsyncSession) -> None:
        """设置测试环境 - 统一的环境准备逻辑"""
        # 创建测试用户
        if self.test_spec.requires_auth or self.test_spec.requires_task_setup:
            self._test_user = User(
                **DatabaseTestFactory.minimal_valid_user(
                    email=f"test-{uuid.uuid4()}@example.com"
                )
            )
            db_session.add(self._test_user)
            await db_session.commit()
            await db_session.refresh(self._test_user)

        # 创建测试任务
        if self.test_spec.requires_task_setup and self._test_user:
            self._test_task = Task(
                **DatabaseTestFactory.minimal_valid_task(
                    user_id=self._test_user.id,
                    product_description=f"测试产品描述 - {uuid.uuid4()}",
                )
            )
            db_session.add(self._test_task)
            await db_session.commit()
            await db_session.refresh(self._test_task)

        # 生成认证Headers
        if self.test_spec.requires_auth and self._test_user:
            self._auth_headers = await self._generate_auth_headers()

    async def _generate_auth_headers(self) -> Dict[str, str]:
        """生成认证Headers - 简化版本，实际项目需要JWT实现"""
        return {
            "Authorization": f"Bearer test-token-{self._test_user.id}",
            "X-Tenant-ID": str(self._test_user.tenant_id),
        }

    async def execute_test_suite(
        self,
        client: TestClient,
        db_session: AsyncSession,
        scenario_filter: Optional[TestScenarioType] = None,
    ) -> Dict[str, Any]:
        """统一测试套件执行器

        Linus核心设计：一个函数处理所有场景类型
        无特殊分支，配置驱动执行
        """
        await self.setup_test_environment(db_session)

        scenarios = self.test_spec.scenarios
        if scenario_filter:
            scenarios = [s for s in scenarios if s.scenario_type == scenario_filter]

        results = {
            "total_scenarios": len(scenarios),
            "passed": 0,
            "failed": 0,
            "results": [],
        }

        for scenario in scenarios:
            try:
                result = await self._execute_single_scenario(client, scenario)
                results["results"].append(
                    {"scenario": scenario.name, "status": "PASSED", "result": result}
                )
                results["passed"] += 1
            except Exception as e:
                results["results"].append(
                    {"scenario": scenario.name, "status": "FAILED", "error": str(e)}
                )
                results["failed"] += 1
                # 不中断执行，继续其他场景

        return results

    async def _execute_single_scenario(
        self, client: TestClient, scenario: TestScenario
    ) -> Dict[str, Any]:
        """执行单个测试场景 - 统一处理逻辑"""
        # 准备请求参数
        request_kwargs = {
            "method": scenario.method,
            "url": scenario.path.format(
                task_id=self._test_task.id if self._test_task else "test-task-id"
            ),
            "headers": {**scenario.headers, **self._auth_headers},
        }

        if scenario.params:
            request_kwargs["params"] = scenario.params
        if scenario.json_data:
            request_kwargs["json"] = scenario.json_data

        # 执行请求 - 性能测试或常规测试
        if scenario.performance_spec:
            return await self._execute_performance_test(
                client, request_kwargs, scenario
            )
        else:
            return await self._execute_functional_test(client, request_kwargs, scenario)

    async def _execute_functional_test(
        self, client: TestClient, request_kwargs: Dict[str, Any], scenario: TestScenario
    ) -> Dict[str, Any]:
        """执行功能测试"""
        # 发送请求
        response = client.request(**request_kwargs)

        # 验证状态码
        assert response.status_code == scenario.expected_status, (
            f"状态码不匹配。期望: {scenario.expected_status}, 实际: {response.status_code}\n"
            f"响应内容: {response.text}"
        )

        # 验证响应结构
        if scenario.expected_response_schema:
            ResponseValidator.validate_response_structure(
                response, scenario.expected_response_schema
            )

        return {
            "status_code": response.status_code,
            "response_size": len(response.content),
            "response_time_ms": getattr(
                response, "elapsed", timedelta(0)
            ).total_seconds()
            * 1000,
        }

    async def _execute_performance_test(
        self, client: TestClient, request_kwargs: Dict[str, Any], scenario: TestScenario
    ) -> Dict[str, Any]:
        """执行性能测试"""
        perf_spec = scenario.performance_spec
        measurements = []

        # 预热
        for _ in range(perf_spec.warmup_iterations):
            client.request(**request_kwargs)

        # 实际测量
        for _ in range(perf_spec.iterations):
            start_time = datetime.now()
            response = client.request(**request_kwargs)
            end_time = datetime.now()

            duration_ms = (end_time - start_time).total_seconds() * 1000
            measurements.append(duration_ms)

            # 验证基本正确性
            assert response.status_code == scenario.expected_status

        # 统计分析
        avg_ms = sum(measurements) / len(measurements)
        max_ms = max(measurements)
        min_ms = min(measurements)

        # 性能断言
        assert (
            avg_ms <= perf_spec.target_response_time_ms
        ), f"平均响应时间{avg_ms:.2f}ms超过目标{perf_spec.target_response_time_ms}ms"

        return {
            "average_ms": avg_ms,
            "min_ms": min_ms,
            "max_ms": max_ms,
            "measurements_count": len(measurements),
            "target_ms": perf_spec.target_response_time_ms,
            "passed": avg_ms <= perf_spec.target_response_time_ms,
        }
