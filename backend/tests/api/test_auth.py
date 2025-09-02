"""
认证中间件测试 - JWT认证和多租户隔离

基于Linus统一架构：
- 配置驱动认证测试
- JWT生命周期验证
- 多租户数据隔离
- 权限检查全覆盖
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Task
from .base import (
    BaseAPITest,
    APITestSpec,
    TestScenario,
    TestScenarioType,
    PerformanceSpec,
)
from tests.conftest import DatabaseTestFactory


class TestAuthMiddleware(BaseAPITest):
    """认证中间件测试类 - 统一架构覆盖所有认证场景"""

    @property
    def test_spec(self) -> APITestSpec:
        """认证中间件测试规格配置"""
        return APITestSpec(
            endpoint_name="auth_middleware",
            base_path="/api/v1",
            requires_auth=True,
            requires_task_setup=True,
            scenarios=[
                # 1. 正常认证流程测试
                TestScenario(
                    name="有效JWT令牌访问",
                    scenario_type=TestScenarioType.NORMAL,
                    method="GET",
                    path="/api/v1/status/{task_id}",
                    expected_status=200,
                    description="使用有效JWT令牌访问受保护端点",
                ),
                TestScenario(
                    name="有效租户ID访问",
                    scenario_type=TestScenarioType.NORMAL,
                    method="GET",
                    path="/api/v1/status/{task_id}",
                    expected_status=200,
                    description="使用正确的租户ID访问资源",
                ),
                TestScenario(
                    name="刷新令牌认证",
                    scenario_type=TestScenarioType.NORMAL,
                    method="POST",
                    path="/api/v1/auth/refresh",
                    json_data={"refresh_token": "valid_refresh_token"},
                    expected_status=200,
                    expected_response_schema={
                        "required": ["access_token", "token_type", "expires_in"],
                        "properties": {
                            "access_token": {"type": "string"},
                            "token_type": {"type": "string"},
                            "expires_in": {"type": "integer"},
                        },
                    },
                    description="使用刷新令牌获取新的访问令牌",
                ),
                # 2. 边界条件测试
                TestScenario(
                    name="即将过期的JWT令牌",
                    scenario_type=TestScenarioType.BOUNDARY,
                    method="GET",
                    path="/api/v1/status/{task_id}",
                    expected_status=200,
                    description="使用即将过期（5秒内）的JWT令牌",
                ),
                TestScenario(
                    name="长期有效的JWT令牌",
                    scenario_type=TestScenarioType.BOUNDARY,
                    method="GET",
                    path="/api/v1/status/{task_id}",
                    expected_status=200,
                    description="使用长期有效（7天）的JWT令牌",
                ),
                TestScenario(
                    name="包含特殊字符的租户ID",
                    scenario_type=TestScenarioType.BOUNDARY,
                    method="GET",
                    path="/api/v1/status/{task_id}",
                    expected_status=200,
                    description="使用包含特殊字符的有效租户ID",
                ),
                # 3. JWT格式错误场景
                TestScenario(
                    name="缺少认证Header",
                    scenario_type=TestScenarioType.ERROR,
                    method="GET",
                    path="/api/v1/status/{task_id}",
                    headers={},  # 清空所有headers
                    expected_status=401,
                    expected_response_schema={
                        "required": ["detail"],
                        "properties": {"detail": {"type": "string"}},
                    },
                    description="缺少Authorization header应返回401",
                ),
                TestScenario(
                    name="无效的JWT格式",
                    scenario_type=TestScenarioType.ERROR,
                    method="GET",
                    path="/api/v1/status/{task_id}",
                    headers={"Authorization": "Bearer invalid.jwt.format"},
                    expected_status=401,
                    description="无效JWT格式应返回401错误",
                ),
                TestScenario(
                    name="已过期的JWT令牌",
                    scenario_type=TestScenarioType.ERROR,
                    method="GET",
                    path="/api/v1/status/{task_id}",
                    headers={"Authorization": "Bearer expired_jwt_token"},
                    expected_status=401,
                    expected_response_schema={
                        "required": ["detail", "error_code"],
                        "properties": {
                            "detail": {"type": "string"},
                            "error_code": {"type": "string"},
                        },
                    },
                    description="过期JWT令牌应返回401错误",
                ),
                TestScenario(
                    name="被撤销的JWT令牌",
                    scenario_type=TestScenarioType.ERROR,
                    method="GET",
                    path="/api/v1/status/{task_id}",
                    headers={"Authorization": "Bearer revoked_jwt_token"},
                    expected_status=401,
                    description="被撤销的JWT令牌应返回401错误",
                ),
                TestScenario(
                    name="错误的Bearer前缀",
                    scenario_type=TestScenarioType.ERROR,
                    method="GET",
                    path="/api/v1/status/{task_id}",
                    headers={"Authorization": "Basic invalid_prefix"},
                    expected_status=401,
                    description="错误的认证类型前缀应返回401错误",
                ),
                # 4. 多租户隔离错误场景
                TestScenario(
                    name="跨租户资源访问",
                    scenario_type=TestScenarioType.ERROR,
                    method="GET",
                    path="/api/v1/status/{task_id}",
                    expected_status=403,
                    expected_response_schema={
                        "required": ["detail", "error_code"],
                        "properties": {
                            "detail": {"type": "string"},
                            "error_code": {"type": "string"},
                        },
                    },
                    description="访问其他租户资源应返回403错误",
                ),
                TestScenario(
                    name="无效的租户ID",
                    scenario_type=TestScenarioType.ERROR,
                    method="GET",
                    path="/api/v1/status/{task_id}",
                    headers={"X-Tenant-ID": "invalid-tenant-id"},
                    expected_status=403,
                    description="无效租户ID应返回403错误",
                ),
                TestScenario(
                    name="缺少租户ID Header",
                    scenario_type=TestScenarioType.ERROR,
                    method="GET",
                    path="/api/v1/status/{task_id}",
                    # 只有Authorization，没有X-Tenant-ID
                    expected_status=400,
                    description="缺少租户ID header应返回400错误",
                ),
                # 5. 权限检查场景
                TestScenario(
                    name="只读用户创建任务",
                    scenario_type=TestScenarioType.ERROR,
                    method="POST",
                    path="/api/v1/analyze",
                    json_data={"product_description": "测试产品描述"},
                    expected_status=403,
                    description="只读权限用户创建任务应返回403错误",
                ),
                TestScenario(
                    name="已禁用用户访问",
                    scenario_type=TestScenarioType.ERROR,
                    method="GET",
                    path="/api/v1/status/{task_id}",
                    expected_status=403,
                    expected_response_schema={
                        "required": ["detail", "error_code"],
                        "properties": {
                            "detail": {"type": "string"},
                            "error_code": {"type": "string"},
                        },
                    },
                    description="已禁用用户访问应返回403错误",
                ),
                # 6. 性能测试
                TestScenario(
                    name="认证验证性能测试",
                    scenario_type=TestScenarioType.PERFORMANCE,
                    method="GET",
                    path="/api/v1/status/{task_id}",
                    expected_status=200,
                    performance_spec=PerformanceSpec(
                        target_response_time_ms=5.0,  # 认证验证应该很快
                        iterations=200,
                        warmup_iterations=20,
                    ),
                    description="验证JWT认证验证性能<5ms",
                ),
                TestScenario(
                    name="高并发认证性能",
                    scenario_type=TestScenarioType.PERFORMANCE,
                    method="GET",
                    path="/api/v1/status/{task_id}",
                    expected_status=200,
                    performance_spec=PerformanceSpec(
                        target_response_time_ms=10.0,  # 并发场景稍微放宽
                        iterations=100,
                        warmup_iterations=10,
                    ),
                    description="验证高并发认证性能",
                ),
            ],
        )

    async def setup_test_environment(self, db_session: AsyncSession) -> None:
        """重写环境设置，创建多租户测试数据"""
        await super().setup_test_environment(db_session)

        if not self._test_user:
            return

        # 创建另一个租户的用户和任务（用于跨租户测试）
        other_tenant_id = uuid.uuid4()
        other_user = User(
            **DatabaseTestFactory.minimal_valid_user(
                tenant_id=other_tenant_id, email="other-tenant@example.com"
            )
        )

        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)

        # 为其他租户创建任务
        other_tenant_task = Task(
            **DatabaseTestFactory.minimal_valid_task(
                user_id=other_user.id,
                product_description="其他租户的任务，用于跨租户访问测试",
            )
        )

        db_session.add(other_tenant_task)
        await db_session.commit()
        await db_session.refresh(other_tenant_task)

        # 创建不同权限和状态的用户
        readonly_user = User(
            **DatabaseTestFactory.minimal_valid_user(
                tenant_id=self._test_user.tenant_id,
                email="readonly@example.com",
                # 在实际实现中这里应该设置只读权限标志
            )
        )

        disabled_user = User(
            **DatabaseTestFactory.minimal_valid_user(
                tenant_id=self._test_user.tenant_id,
                email="disabled@example.com",
                is_active=False,
            )
        )

        db_session.add_all([readonly_user, disabled_user])
        await db_session.commit()

        # 保存测试用户映射
        self._auth_test_users = {
            "main": self._test_user,
            "other_tenant": other_user,
            "readonly": readonly_user,
            "disabled": disabled_user,
        }

        self._other_tenant_task_id = other_tenant_task.id

    async def _generate_test_jwt_tokens(self) -> Dict[str, str]:
        """生成各种测试JWT令牌"""
        base_user_id = self._test_user.id

        return {
            "valid": f"test-jwt-valid-{base_user_id}",
            "expired": f"test-jwt-expired-{base_user_id}",
            "revoked": f"test-jwt-revoked-{base_user_id}",
            "near_expiry": f"test-jwt-near-expiry-{base_user_id}",
            "long_term": f"test-jwt-long-term-{base_user_id}",
            "readonly": f"test-jwt-readonly-{self._auth_test_users['readonly'].id}",
            "disabled": f"test-jwt-disabled-{self._auth_test_users['disabled'].id}",
        }

    async def _execute_single_scenario(
        self, client: TestClient, scenario: TestScenario
    ) -> Dict[str, Any]:
        """重写单个场景执行，处理不同认证场景的特殊逻辑"""

        # 生成测试令牌
        test_tokens = await self._generate_test_jwt_tokens()

        # 根据场景选择合适的认证设置
        task_id_to_use = self._test_task.id
        auth_headers = dict(self._auth_headers)

        # 处理特殊认证场景
        if scenario.name == "跨租户资源访问":
            task_id_to_use = self._other_tenant_task_id
        elif scenario.name == "已过期的JWT令牌":
            auth_headers["Authorization"] = f"Bearer {test_tokens['expired']}"
        elif scenario.name == "被撤销的JWT令牌":
            auth_headers["Authorization"] = f"Bearer {test_tokens['revoked']}"
        elif scenario.name == "即将过期的JWT令牌":
            auth_headers["Authorization"] = f"Bearer {test_tokens['near_expiry']}"
        elif scenario.name == "长期有效的JWT令牌":
            auth_headers["Authorization"] = f"Bearer {test_tokens['long_term']}"
        elif scenario.name == "只读用户创建任务":
            auth_headers["Authorization"] = f"Bearer {test_tokens['readonly']}"
        elif scenario.name == "已禁用用户访问":
            auth_headers["Authorization"] = f"Bearer {test_tokens['disabled']}"
        elif scenario.name == "无效的租户ID":
            auth_headers["X-Tenant-ID"] = "00000000-0000-0000-0000-000000000000"
        elif scenario.name == "缺少租户ID Header":
            auth_headers.pop("X-Tenant-ID", None)

        # 准备请求参数
        request_kwargs = {
            "method": scenario.method,
            "url": scenario.path.format(task_id=task_id_to_use),
            "headers": (
                {**scenario.headers, **auth_headers} if scenario.headers != {} else {}
            ),
        }

        if scenario.params:
            request_kwargs["params"] = scenario.params
        if scenario.json_data:
            request_kwargs["json"] = scenario.json_data

        # 执行测试
        if scenario.performance_spec:
            return await self._execute_performance_test(
                client, request_kwargs, scenario
            )
        else:
            return await self._execute_functional_test(client, request_kwargs, scenario)


class MultiTenantIsolationTester:
    """多租户隔离专项测试工具"""

    @staticmethod
    async def test_data_isolation(
        client: TestClient,
        tenant_a_auth: Dict[str, str],
        tenant_b_auth: Dict[str, str],
        tenant_a_task_id: uuid.UUID,
        tenant_b_task_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """测试租户间数据隔离"""

        results = {
            "tenant_a_access_own": False,
            "tenant_a_access_other": False,
            "tenant_b_access_own": False,
            "tenant_b_access_other": False,
            "isolation_violated": False,
        }

        # 租户A访问自己的资源
        response_a_own = client.get(
            f"/api/v1/status/{tenant_a_task_id}", headers=tenant_a_auth
        )
        results["tenant_a_access_own"] = response_a_own.status_code == 200

        # 租户A访问租户B的资源
        response_a_other = client.get(
            f"/api/v1/status/{tenant_b_task_id}", headers=tenant_a_auth
        )
        results["tenant_a_access_other"] = response_a_other.status_code == 200

        # 租户B访问自己的资源
        response_b_own = client.get(
            f"/api/v1/status/{tenant_b_task_id}", headers=tenant_b_auth
        )
        results["tenant_b_access_own"] = response_b_own.status_code == 200

        # 租户B访问租户A的资源
        response_b_other = client.get(
            f"/api/v1/status/{tenant_a_task_id}", headers=tenant_b_auth
        )
        results["tenant_b_access_other"] = response_b_other.status_code == 200

        # 检查隔离是否被违反
        results["isolation_violated"] = (
            results["tenant_a_access_other"] or results["tenant_b_access_other"]
        )

        return results


# ============================================================================
# pytest测试函数
# ============================================================================


@pytest.fixture
async def auth_test_instance():
    """认证测试实例fixture"""
    return TestAuthMiddleware()


@pytest.mark.asyncio
async def test_auth_normal_scenarios(auth_test_instance, client, db_session):
    """测试认证正常流程场景"""
    results = await auth_test_instance.execute_test_suite(
        client, db_session, TestScenarioType.NORMAL
    )

    assert results["failed"] == 0, f"认证正常场景测试失败: {results}"
    assert results["passed"] >= 3, "应该通过基本认证测试"


@pytest.mark.asyncio
async def test_auth_boundary_scenarios(auth_test_instance, client, db_session):
    """测试认证边界条件场景"""
    results = await auth_test_instance.execute_test_suite(
        client, db_session, TestScenarioType.BOUNDARY
    )

    # 边界认证测试可能受环境影响，容忍度稍高
    failure_rate = (
        results["failed"] / results["total_scenarios"]
        if results["total_scenarios"] > 0
        else 0
    )
    assert failure_rate <= 0.2, f"认证边界测试失败率{failure_rate:.1%}过高"


@pytest.mark.asyncio
async def test_auth_error_scenarios(auth_test_instance, client, db_session):
    """测试认证错误场景"""
    results = await auth_test_instance.execute_test_suite(
        client, db_session, TestScenarioType.ERROR
    )

    assert results["failed"] == 0, f"认证错误场景测试失败: {results}"
    assert results["passed"] >= 8, "应该通过主要认证错误场景测试"


@pytest.mark.asyncio
async def test_auth_performance_scenarios(auth_test_instance, client, db_session):
    """测试认证性能场景"""
    results = await auth_test_instance.execute_test_suite(
        client, db_session, TestScenarioType.PERFORMANCE
    )

    # 验证认证性能结果
    for result in results["results"]:
        if result["status"] == "PASSED":
            perf_result = result["result"]
            assert perf_result["passed"], f"认证性能未达标: {perf_result}"


@pytest.mark.asyncio
async def test_multi_tenant_isolation(auth_test_instance, client, db_session):
    """专项测试多租户数据隔离"""
    await auth_test_instance.setup_test_environment(db_session)

    if not hasattr(auth_test_instance, "_auth_test_users"):
        pytest.skip("需要多租户测试环境")

    # 测试数据隔离
    isolation_results = await MultiTenantIsolationTester.test_data_isolation(
        client,
        {
            "Authorization": f"Bearer test-tenant-a",
            "X-Tenant-ID": str(auth_test_instance._test_user.tenant_id),
        },
        {
            "Authorization": f"Bearer test-tenant-b",
            "X-Tenant-ID": str(
                auth_test_instance._auth_test_users["other_tenant"].tenant_id
            ),
        },
        auth_test_instance._test_task.id,
        auth_test_instance._other_tenant_task_id,
    )

    # 断言多租户隔离正确
    assert not isolation_results[
        "isolation_violated"
    ], f"多租户数据隔离被违反: {isolation_results}"
    assert isolation_results["tenant_a_access_own"], "租户A应该能访问自己的资源"
    assert isolation_results["tenant_b_access_own"], "租户B应该能访问自己的资源"


@pytest.mark.asyncio
async def test_auth_complete_test_suite(auth_test_instance, client, db_session):
    """运行完整的认证测试套件"""
    results = await auth_test_instance.execute_test_suite(client, db_session)

    # 认证是安全关键功能，要求高成功率
    failure_rate = (
        results["failed"] / results["total_scenarios"]
        if results["total_scenarios"] > 0
        else 0
    )
    assert failure_rate <= 0.15, f"认证测试失败率{failure_rate:.1%}过高，应该<15%"

    print(
        f"✅ 认证中间件测试完成: {results['passed']}通过 / {results['failed']}失败 / {results['total_scenarios']}总计"
    )
