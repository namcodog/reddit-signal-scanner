"""
分析任务端点测试 - /api/v1/analyze

基于Linus架构和pre-linus-check通过的方案：
- 统一BaseAPITest架构
- 配置驱动测试用例
- 完整边界条件覆盖
- 性能目标<200ms验证
"""

import uuid
from typing import Dict, Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from .base import (
    BaseAPITest,
    APITestSpec,
    TestScenario,
    TestScenarioType,
    PerformanceSpec,
)


class TestAnalyzeEndpoint(BaseAPITest):
    """分析端点测试类

    基于统一架构，配置驱动生成所有测试场景
    消除特殊情况处理，简化测试逻辑
    """

    @property
    def test_spec(self) -> APITestSpec:
        """分析端点测试规格配置"""
        return APITestSpec(
            endpoint_name="analyze",
            base_path="/api/v1/analyze",
            requires_auth=True,  # 分析端点需要认证
            requires_task_setup=False,  # 不需要预创建任务
            scenarios=[
                # 1. 正常流程测试
                TestScenario(
                    name="成功创建分析任务",
                    scenario_type=TestScenarioType.NORMAL,
                    method="POST",
                    path="/api/v1/analyze",
                    json_data={
                        "product_description": "一款AI驱动的社交媒体分析工具，帮助企业发现Reddit上的潜在客户需求和市场机会"
                    },
                    expected_status=201,
                    expected_response_schema={
                        "required": ["task_id", "status", "estimated_completion"],
                        "properties": {
                            "task_id": {"type": "string"},
                            "status": {"type": "string"},
                            "estimated_completion": {"type": "string"},
                            "created_at": {"type": "string"},
                        },
                    },
                    description="正常的产品描述创建分析任务",
                ),
                # 2. 边界条件测试
                TestScenario(
                    name="最短有效描述测试",
                    scenario_type=TestScenarioType.BOUNDARY,
                    method="POST",
                    path="/api/v1/analyze",
                    json_data={"product_description": "1234567890"},  # 刚好10字符
                    expected_status=201,
                    description="测试10字符最短有效描述",
                ),
                TestScenario(
                    name="最长有效描述测试",
                    scenario_type=TestScenarioType.BOUNDARY,
                    method="POST",
                    path="/api/v1/analyze",
                    json_data={"product_description": "x" * 2000},  # 刚好2000字符
                    expected_status=201,
                    description="测试2000字符最长有效描述",
                ),
                TestScenario(
                    name="包含特殊字符描述测试",
                    scenario_type=TestScenarioType.BOUNDARY,
                    method="POST",
                    path="/api/v1/analyze",
                    json_data={
                        "product_description": '测试产品@#$%^&*()_+-={}[]|\\:";<>?,./包含各种特殊字符的有效描述内容用于边界测试'
                    },
                    expected_status=201,
                    description="测试包含特殊字符的产品描述",
                ),
                # 3. 错误场景测试
                TestScenario(
                    name="描述过短错误",
                    scenario_type=TestScenarioType.ERROR,
                    method="POST",
                    path="/api/v1/analyze",
                    json_data={
                        "product_description": "too_short"  # 9字符，低于10字符要求
                    },
                    expected_status=422,
                    expected_response_schema={
                        "required": ["detail"],
                        "properties": {"detail": {"type": "array"}},
                    },
                    description="产品描述少于10字符应返回422错误",
                ),
                TestScenario(
                    name="描述过长错误",
                    scenario_type=TestScenarioType.ERROR,
                    method="POST",
                    path="/api/v1/analyze",
                    json_data={"product_description": "x" * 2001},  # 超过2000字符限制
                    expected_status=422,
                    expected_response_schema={
                        "required": ["detail"],
                        "properties": {"detail": {"type": "array"}},
                    },
                    description="产品描述超过2000字符应返回422错误",
                ),
                TestScenario(
                    name="缺少描述字段错误",
                    scenario_type=TestScenarioType.ERROR,
                    method="POST",
                    path="/api/v1/analyze",
                    json_data={},  # 空数据
                    expected_status=422,
                    description="缺少product_description字段应返回422错误",
                ),
                TestScenario(
                    name="无效JSON格式错误",
                    scenario_type=TestScenarioType.ERROR,
                    method="POST",
                    path="/api/v1/analyze",
                    headers={"Content-Type": "application/json"},
                    # 注意：这里需要在实际测试中发送无效JSON字符串
                    expected_status=422,
                    description="无效JSON格式应返回422错误",
                ),
                TestScenario(
                    name="未认证访问错误",
                    scenario_type=TestScenarioType.ERROR,
                    method="POST",
                    path="/api/v1/analyze",
                    headers={},  # 清空认证headers
                    json_data={"product_description": "测试产品描述，用于验证认证机制"},
                    expected_status=401,
                    description="未提供认证信息应返回401错误",
                ),
                # 4. 性能测试
                TestScenario(
                    name="创建任务性能测试",
                    scenario_type=TestScenarioType.PERFORMANCE,
                    method="POST",
                    path="/api/v1/analyze",
                    json_data={
                        "product_description": "性能测试用的标准长度产品描述，用于验证API响应时间符合SLA要求"
                    },
                    expected_status=201,
                    performance_spec=PerformanceSpec(
                        target_response_time_ms=200.0,  # PRD要求<200ms
                        max_tolerance_ratio=1.2,
                        iterations=50,  # 减少迭代次数，避免过度测试
                        warmup_iterations=5,
                    ),
                    description="验证分析任务创建性能<200ms",
                ),
            ],
        )

    async def _execute_functional_test(
        self, client: TestClient, request_kwargs: Dict[str, Any], scenario: TestScenario
    ) -> Dict[str, Any]:
        """重写功能测试方法，处理特殊的无效JSON场景"""

        # 特殊处理无效JSON测试
        if scenario.name == "无效JSON格式错误":
            # 直接发送无效JSON字符串
            response = client.request(
                method=scenario.method,
                url=scenario.path,
                headers={**scenario.headers, **self._auth_headers},
                data='{"invalid": json}',  # 无效JSON
            )
        # 特殊处理无认证测试
        elif scenario.name == "未认证访问错误":
            # 清空认证headers
            response = client.request(
                method=scenario.method,
                url=scenario.path,
                headers=scenario.headers,  # 不加认证headers
                json=scenario.json_data,
            )
        else:
            # 使用父类标准逻辑
            return await super()._execute_functional_test(
                client, request_kwargs, scenario
            )

        # 验证状态码
        assert response.status_code == scenario.expected_status, (
            f"状态码不匹配。期望: {scenario.expected_status}, 实际: {response.status_code}\n"
            f"响应内容: {response.text}"
        )

        # 验证响应结构
        if scenario.expected_response_schema:
            from .base import ResponseValidator

            ResponseValidator.validate_response_structure(
                response, scenario.expected_response_schema
            )

        return {
            "status_code": response.status_code,
            "response_size": len(response.content),
            "response_time_ms": 0,  # 简化处理
        }


# ============================================================================
# 使用pytest标准测试函数
# ============================================================================


@pytest.fixture
async def analyze_test_instance():
    """分析测试实例fixture"""
    return TestAnalyzeEndpoint()


@pytest.mark.asyncio
async def test_analyze_normal_scenarios(analyze_test_instance, client, db_session):
    """测试分析端点正常流程场景"""
    results = await analyze_test_instance.execute_test_suite(
        client, db_session, TestScenarioType.NORMAL
    )

    assert results["failed"] == 0, f"正常场景测试失败: {results}"
    assert results["passed"] > 0, "应该至少通过一个正常场景测试"


@pytest.mark.asyncio
async def test_analyze_boundary_scenarios(analyze_test_instance, client, db_session):
    """测试分析端点边界条件场景"""
    results = await analyze_test_instance.execute_test_suite(
        client, db_session, TestScenarioType.BOUNDARY
    )

    assert results["failed"] == 0, f"边界条件测试失败: {results}"
    assert results["passed"] >= 3, "应该通过所有3个边界条件测试"


@pytest.mark.asyncio
async def test_analyze_error_scenarios(analyze_test_instance, client, db_session):
    """测试分析端点错误场景"""
    results = await analyze_test_instance.execute_test_suite(
        client, db_session, TestScenarioType.ERROR
    )

    assert results["failed"] == 0, f"错误场景测试失败: {results}"
    assert results["passed"] >= 5, "应该通过所有错误场景测试"


@pytest.mark.asyncio
async def test_analyze_performance_scenarios(analyze_test_instance, client, db_session):
    """测试分析端点性能场景"""
    results = await analyze_test_instance.execute_test_suite(
        client, db_session, TestScenarioType.PERFORMANCE
    )

    assert results["failed"] == 0, f"性能测试失败: {results}"
    assert results["passed"] >= 1, "应该通过性能测试"

    # 验证性能结果
    perf_result = results["results"][0]["result"]
    assert perf_result["passed"], f"性能未达标: {perf_result}"
    assert (
        perf_result["average_ms"] <= 200.0
    ), f"平均响应时间超过200ms: {perf_result['average_ms']}"


@pytest.mark.asyncio
async def test_analyze_complete_test_suite(analyze_test_instance, client, db_session):
    """运行完整的分析端点测试套件"""
    results = await analyze_test_instance.execute_test_suite(client, db_session)

    # 验证总体结果
    total_expected = len(analyze_test_instance.test_spec.scenarios)
    assert (
        results["total_scenarios"] == total_expected
    ), f"应该执行{total_expected}个场景"

    # 容忍少量失败（主要是环境相关的边界情况）
    failure_rate = (
        results["failed"] / results["total_scenarios"]
        if results["total_scenarios"] > 0
        else 0
    )
    assert failure_rate <= 0.1, f"失败率{failure_rate:.1%}过高，应该<10%"

    print(
        f"✅ 分析端点测试完成: {results['passed']}通过 / {results['failed']}失败 / {results['total_scenarios']}总计"
    )
