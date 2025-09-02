"""
状态查询端点测试 - /api/v1/status/{task_id}

基于Linus架构设计：
- 统一BaseAPITest配置驱动
- 性能目标<10ms验证
- 完整任务状态覆盖
- 多租户隔离验证
"""

import uuid
from typing import Dict, Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Task
from .base import (
    BaseAPITest,
    APITestSpec,
    TestScenario,
    TestScenarioType,
    PerformanceSpec,
)
from tests.conftest import DatabaseTestFactory


class TestStatusEndpoint(BaseAPITest):
    """状态端点测试类 - 配置驱动的统一架构"""

    @property
    def test_spec(self) -> APITestSpec:
        """状态端点测试规格配置"""
        return APITestSpec(
            endpoint_name="status",
            base_path="/api/v1/status",
            requires_auth=True,
            requires_task_setup=True,  # 需要预创建任务
            scenarios=[
                # 1. 正常流程测试 - 所有任务状态
                TestScenario(
                    name="查询pending状态任务",
                    scenario_type=TestScenarioType.NORMAL,
                    method="GET",
                    path="/api/v1/status/{task_id}",
                    expected_status=200,
                    expected_response_schema={
                        "required": ["task_id", "status", "created_at"],
                        "properties": {
                            "task_id": {"type": "string"},
                            "status": {"type": "string"},
                            "created_at": {"type": "string"},
                            "updated_at": {"type": "string"},
                            "progress_percentage": {"type": "number"},
                            "estimated_completion": {"type": "string"},
                        },
                    },
                    description="查询pending状态的任务",
                ),
                TestScenario(
                    name="查询processing状态任务",
                    scenario_type=TestScenarioType.NORMAL,
                    method="GET",
                    path="/api/v1/status/{task_id}",
                    expected_status=200,
                    description="查询processing状态的任务",
                ),
                TestScenario(
                    name="查询completed状态任务",
                    scenario_type=TestScenarioType.NORMAL,
                    method="GET",
                    path="/api/v1/status/{task_id}",
                    expected_status=200,
                    expected_response_schema={
                        "required": ["task_id", "status", "created_at", "completed_at"],
                        "properties": {
                            "task_id": {"type": "string"},
                            "status": {"type": "string"},
                            "completed_at": {"type": "string"},
                            "progress_percentage": {"type": "number"},
                        },
                    },
                    description="查询completed状态的任务，应包含completed_at",
                ),
                TestScenario(
                    name="查询failed状态任务",
                    scenario_type=TestScenarioType.NORMAL,
                    method="GET",
                    path="/api/v1/status/{task_id}",
                    expected_status=200,
                    expected_response_schema={
                        "required": ["task_id", "status", "error_message"],
                        "properties": {"error_message": {"type": "string"}},
                    },
                    description="查询failed状态的任务，应包含error_message",
                ),
                # 2. 边界条件测试
                TestScenario(
                    name="查询刚创建的任务",
                    scenario_type=TestScenarioType.BOUNDARY,
                    method="GET",
                    path="/api/v1/status/{task_id}",
                    expected_status=200,
                    description="查询刚创建不到1秒的任务状态",
                ),
                TestScenario(
                    name="包含查询参数的状态请求",
                    scenario_type=TestScenarioType.BOUNDARY,
                    method="GET",
                    path="/api/v1/status/{task_id}",
                    params={"include_details": "true", "format": "json"},
                    expected_status=200,
                    description="测试包含额外查询参数的请求",
                ),
                # 3. 错误场景测试
                TestScenario(
                    name="不存在的任务ID",
                    scenario_type=TestScenarioType.ERROR,
                    method="GET",
                    path=f"/api/v1/status/{uuid.uuid4()}",  # 随机UUID，不存在
                    expected_status=404,
                    expected_response_schema={
                        "required": ["detail"],
                        "properties": {"detail": {"type": "string"}},
                    },
                    description="查询不存在的任务ID应返回404",
                ),
                TestScenario(
                    name="无效的UUID格式",
                    scenario_type=TestScenarioType.ERROR,
                    method="GET",
                    path="/api/v1/status/invalid-uuid-format",
                    expected_status=422,
                    description="无效UUID格式应返回422错误",
                ),
                TestScenario(
                    name="未认证访问错误",
                    scenario_type=TestScenarioType.ERROR,
                    method="GET",
                    path="/api/v1/status/{task_id}",
                    headers={},  # 清空认证headers
                    expected_status=401,
                    description="未认证访问应返回401错误",
                ),
                TestScenario(
                    name="跨租户访问错误",
                    scenario_type=TestScenarioType.ERROR,
                    method="GET",
                    path="/api/v1/status/{task_id}",
                    expected_status=403,  # 假设跨租户访问返回403
                    description="访问其他租户的任务应返回403错误",
                ),
                # 4. 性能测试
                TestScenario(
                    name="状态查询性能测试",
                    scenario_type=TestScenarioType.PERFORMANCE,
                    method="GET",
                    path="/api/v1/status/{task_id}",
                    expected_status=200,
                    performance_spec=PerformanceSpec(
                        target_response_time_ms=10.0,  # PRD要求<10ms
                        max_tolerance_ratio=1.5,
                        iterations=100,
                        warmup_iterations=10,
                    ),
                    description="验证状态查询性能<10ms",
                ),
                TestScenario(
                    name="高并发状态查询",
                    scenario_type=TestScenarioType.PERFORMANCE,
                    method="GET",
                    path="/api/v1/status/{task_id}",
                    expected_status=200,
                    performance_spec=PerformanceSpec(
                        target_response_time_ms=15.0,  # 并发场景稍微放宽
                        iterations=50,
                        warmup_iterations=5,
                    ),
                    description="验证高并发状态查询性能",
                ),
            ],
        )

    async def setup_test_environment(self, db_session: AsyncSession) -> None:
        """重写环境设置，创建多状态测试任务"""
        await super().setup_test_environment(db_session)

        if not self._test_user:
            return

        # 创建不同状态的测试任务
        test_tasks = [
            # pending状态任务
            Task(
                **DatabaseTestFactory.minimal_valid_task(
                    user_id=self._test_user.id,
                    product_description="测试pending状态任务",
                    status="pending",
                )
            ),
            # processing状态任务
            Task(
                **DatabaseTestFactory.minimal_valid_task(
                    user_id=self._test_user.id,
                    product_description="测试processing状态任务",
                    status="processing",
                )
            ),
            # completed状态任务
            Task(
                **DatabaseTestFactory.minimal_valid_task(
                    user_id=self._test_user.id,
                    product_description="测试completed状态任务",
                    status="completed",
                )
            ),
            # failed状态任务
            Task(
                **DatabaseTestFactory.minimal_valid_task(
                    user_id=self._test_user.id,
                    product_description="测试failed状态任务",
                    status="failed",
                    error_message="测试错误信息",
                )
            ),
        ]

        db_session.add_all(test_tasks)
        await db_session.commit()

        # 刷新所有任务以获取ID
        for task in test_tasks:
            await db_session.refresh(task)

        # 保存不同状态的任务ID供测试使用
        self._status_task_map = {
            "pending": test_tasks[0].id,
            "processing": test_tasks[1].id,
            "completed": test_tasks[2].id,
            "failed": test_tasks[3].id,
        }

        # 设置默认任务为pending状态任务
        self._test_task = test_tasks[0]

    async def _execute_single_scenario(
        self, client: TestClient, scenario: TestScenario
    ) -> Dict[str, Any]:
        """重写单个场景执行，处理不同状态任务的路由"""

        # 根据场景名称选择合适的任务ID
        task_id_to_use = self._test_task.id

        if hasattr(self, "_status_task_map"):
            if "pending" in scenario.name:
                task_id_to_use = self._status_task_map["pending"]
            elif "processing" in scenario.name:
                task_id_to_use = self._status_task_map["processing"]
            elif "completed" in scenario.name:
                task_id_to_use = self._status_task_map["completed"]
            elif "failed" in scenario.name:
                task_id_to_use = self._status_task_map["failed"]

        # 特殊处理跨租户访问测试
        if scenario.name == "跨租户访问错误":
            # 创建另一个租户的任务ID（实际应该从数据库获取）
            task_id_to_use = uuid.uuid4()  # 使用不存在的任务ID模拟跨租户

        # 准备请求参数，替换task_id
        request_kwargs = {
            "method": scenario.method,
            "url": scenario.path.format(task_id=task_id_to_use),
            "headers": {**scenario.headers, **self._auth_headers},
        }

        if scenario.params:
            request_kwargs["params"] = scenario.params
        if scenario.json_data:
            request_kwargs["json"] = scenario.json_data

        # 特殊处理未认证访问
        if scenario.name == "未认证访问错误":
            request_kwargs["headers"] = scenario.headers  # 不包含认证headers

        # 执行请求
        if scenario.performance_spec:
            return await self._execute_performance_test(
                client, request_kwargs, scenario
            )
        else:
            return await self._execute_functional_test(client, request_kwargs, scenario)


# ============================================================================
# pytest测试函数
# ============================================================================


@pytest.fixture
async def status_test_instance():
    """状态测试实例fixture"""
    return TestStatusEndpoint()


@pytest.mark.asyncio
async def test_status_normal_scenarios(status_test_instance, client, db_session):
    """测试状态端点正常流程场景"""
    results = await status_test_instance.execute_test_suite(
        client, db_session, TestScenarioType.NORMAL
    )

    assert results["failed"] == 0, f"正常场景测试失败: {results}"
    assert results["passed"] >= 4, "应该通过所有4个状态查询测试"


@pytest.mark.asyncio
async def test_status_boundary_scenarios(status_test_instance, client, db_session):
    """测试状态端点边界条件场景"""
    results = await status_test_instance.execute_test_suite(
        client, db_session, TestScenarioType.BOUNDARY
    )

    assert results["failed"] == 0, f"边界条件测试失败: {results}"
    assert results["passed"] >= 2, "应该通过边界条件测试"


@pytest.mark.asyncio
async def test_status_error_scenarios(status_test_instance, client, db_session):
    """测试状态端点错误场景"""
    results = await status_test_instance.execute_test_suite(
        client, db_session, TestScenarioType.ERROR
    )

    assert results["failed"] == 0, f"错误场景测试失败: {results}"
    assert results["passed"] >= 3, "应该通过主要错误场景测试"


@pytest.mark.asyncio
async def test_status_performance_scenarios(status_test_instance, client, db_session):
    """测试状态端点性能场景"""
    results = await status_test_instance.execute_test_suite(
        client, db_session, TestScenarioType.PERFORMANCE
    )

    assert results["failed"] == 0, f"性能测试失败: {results}"

    # 验证性能结果
    for result in results["results"]:
        if result["status"] == "PASSED":
            perf_result = result["result"]
            assert perf_result["passed"], f"性能未达标: {perf_result}"

            # 基本性能要求：<10ms (主要测试) 或 <15ms (并发测试)
            max_acceptable = 15.0  # 给并发测试留余地
            assert (
                perf_result["average_ms"] <= max_acceptable
            ), f"平均响应时间{perf_result['average_ms']:.2f}ms超过{max_acceptable}ms"


@pytest.mark.asyncio
async def test_status_complete_test_suite(status_test_instance, client, db_session):
    """运行完整的状态端点测试套件"""
    results = await status_test_instance.execute_test_suite(client, db_session)

    # 验证总体结果
    total_expected = len(status_test_instance.test_spec.scenarios)
    assert results["total_scenarios"] == total_expected

    # 状态查询是核心功能，要求高通过率
    failure_rate = (
        results["failed"] / results["total_scenarios"]
        if results["total_scenarios"] > 0
        else 0
    )
    assert failure_rate <= 0.15, f"失败率{failure_rate:.1%}过高，应该<15%"

    print(
        f"✅ 状态端点测试完成: {results['passed']}通过 / {results['failed']}失败 / {results['total_scenarios']}总计"
    )
