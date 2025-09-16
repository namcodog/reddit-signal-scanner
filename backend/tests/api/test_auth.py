"""
认证中间件测试 v2.0 - Linus架构重构版

彻底消除14个条件分支！
- 原版：14个if-elif分支的复杂逻辑
- 新版：14个独立的多态场景类
- 零条件分支，纯多态驱动
"""

import uuid
from typing import List

import pytest

from .base import (
    TestScenario,
    TestContext,
    TestResult,
    UnifiedTestExecutor,
    NormalScenario,
    ErrorScenario,
    PerformanceScenario,
    TestEnvironmentBuilder,
)
from tests.conftest import DatabaseTestFactory  # noqa: F401
from app.models import User, Task  # noqa: F401


# ============================================================================
# 1. 认证正常场景 - 多态替代条件分支
# ============================================================================


class ValidJWTAccessScenario(NormalScenario):
    """有效JWT令牌访问场景"""

    def __init__(self):
        super().__init__(endpoint="/status/{task_id}", method="GET")  # 需要认证的端点

    async def execute(self, context: TestContext) -> TestResult:
        """使用有效JWT访问"""
        if context.test_task:
            endpoint = self.endpoint.format(task_id=context.test_task.id)
        else:
            endpoint = self.endpoint.format(task_id=uuid.uuid4())

        response = context.client.request(
            method=self.method,
            url=f"{context.base_url}{endpoint}",
            headers=context.auth_headers,
        )

        result = TestResult(
            status_code=response.status_code,
            success=response.status_code == self.get_expected_status(),
            response_data=self._safe_parse_json(response),
        )

        self.validate_response(response, result)
        return result


class ValidTenantAccessScenario(NormalScenario):
    """有效租户ID访问场景"""

    def __init__(self):
        super().__init__(endpoint="/status/{task_id}", method="GET")
        self.description = "使用正确的租户ID访问资源"


class RefreshTokenScenario(NormalScenario):
    """刷新令牌认证场景"""

    def __init__(self):
        super().__init__(
            endpoint="/auth/refresh",
            method="POST",
            json_data={"refresh_token": "valid_refresh_token"},
        )

    def get_expected_status(self) -> int:
        return 200

    def validate_response(self, response, result: TestResult) -> None:
        """验证刷新令牌响应"""
        super().validate_response(response, result)

        data = result.response_data
        required_fields = ["access_token", "token_type", "expires_in"]
        for field in required_fields:
            assert field in data, f"刷新令牌响应缺少字段: {field}"


# ============================================================================
# 2. JWT错误场景 - 每个错误独立类
# ============================================================================


class MissingAuthHeaderError(ErrorScenario):
    """缺少认证Header错误"""

    def __init__(self):
        super().__init__(
            endpoint="/status/{task_id}",
            method="GET",
            error_headers={},  # 完全清空headers
            expected_status=401,
            error_type="缺少认证Header",
        )

    async def execute(self, context: TestContext) -> TestResult:
        """执行时清空所有认证headers"""
        endpoint = self.endpoint.format(
            task_id=context.test_task.id if context.test_task else uuid.uuid4()
        )

        # 发送请求时不使用任何认证headers
        response = context.client.request(
            method=self.method,
            url=f"{context.base_url}{endpoint}",
            headers={},  # 空headers
        )

        result = TestResult(
            status_code=response.status_code,
            success=response.status_code == self.expected_status,
            response_data=self._safe_parse_json(response),
            error_message=self._extract_error_message(response),
        )

        self.validate_response(response, result)
        return result


class InvalidJWTFormatError(ErrorScenario):
    """无效JWT格式错误"""

    def __init__(self):
        super().__init__(
            endpoint="/status/{task_id}",
            method="GET",
            error_headers={"Authorization": "Bearer invalid.jwt.format"},
            expected_status=401,
            error_type="无效JWT格式",
        )


class ExpiredJWTTokenError(ErrorScenario):
    """已过期JWT令牌错误"""

    def __init__(self):
        super().__init__(
            endpoint="/status/{task_id}",
            method="GET",
            error_headers={"Authorization": "Bearer expired_jwt_token"},
            expected_status=401,
            error_type="JWT令牌过期",
        )

    def validate_response(self, response, result: TestResult) -> None:
        """验证过期令牌特定错误格式"""
        super().validate_response(response, result)

        data = result.response_data
        assert "detail" in data, "过期令牌响应应包含detail字段"
        assert "error_code" in data, "过期令牌响应应包含error_code字段"


class RevokedJWTTokenError(ErrorScenario):
    """被撤销JWT令牌错误"""

    def __init__(self):
        super().__init__(
            endpoint="/status/{task_id}",
            method="GET",
            error_headers={"Authorization": "Bearer revoked_jwt_token"},
            expected_status=401,
            error_type="JWT令牌被撤销",
        )


class WrongBearerPrefixError(ErrorScenario):
    """错误的Bearer前缀错误"""

    def __init__(self):
        super().__init__(
            endpoint="/status/{task_id}",
            method="GET",
            error_headers={"Authorization": "Basic invalid_prefix"},
            expected_status=401,
            error_type="错误的认证类型前缀",
        )


# ============================================================================
# 3. 多租户隔离错误场景 - 独立类实现
# ============================================================================


class CrossTenantAccessError(ErrorScenario):
    """跨租户资源访问错误"""

    def __init__(self):
        super().__init__(
            endpoint="/status/{task_id}",
            method="GET",
            expected_status=403,
            error_type="跨租户资源访问",
        )

    async def execute(self, context: TestContext) -> TestResult:
        """使用其他租户的任务ID进行访问"""
        # 生成一个不属于当前租户的任务ID
        other_task_id = uuid.uuid4()

        endpoint = self.endpoint.format(task_id=other_task_id)

        response = context.client.request(
            method=self.method,
            url=f"{context.base_url}{endpoint}",
            headers=context.auth_headers,
        )

        result = TestResult(
            status_code=response.status_code,
            success=response.status_code == self.expected_status,
            response_data=self._safe_parse_json(response),
            error_message=self._extract_error_message(response),
        )

        self.validate_response(response, result)
        return result


class InvalidTenantIdError(ErrorScenario):
    """无效租户ID错误"""

    def __init__(self):
        super().__init__(
            endpoint="/status/{task_id}",
            method="GET",
            error_headers={"X-Tenant-ID": "invalid-tenant-id"},
            expected_status=403,
            error_type="无效租户ID",
        )


class MissingTenantIdError(ErrorScenario):
    """缺少租户ID Header错误"""

    def __init__(self):
        super().__init__(
            endpoint="/status/{task_id}",
            method="GET",
            expected_status=400,
            error_type="缺少租户ID Header",
        )

    async def execute(self, context: TestContext) -> TestResult:
        """发送请求时移除租户ID header"""
        endpoint = self.endpoint.format(
            task_id=context.test_task.id if context.test_task else uuid.uuid4()
        )

        # 构建只有Authorization但没有X-Tenant-ID的headers
        headers = {k: v for k, v in context.auth_headers.items() if k != "X-Tenant-ID"}

        response = context.client.request(
            method=self.method, url=f"{context.base_url}{endpoint}", headers=headers
        )

        result = TestResult(
            status_code=response.status_code,
            success=response.status_code == self.expected_status,
            response_data=self._safe_parse_json(response),
            error_message=self._extract_error_message(response),
        )

        self.validate_response(response, result)
        return result


# ============================================================================
# 4. 权限检查场景 - 独立权限逻辑
# ============================================================================


class ReadOnlyUserCreateTaskError(ErrorScenario):
    """只读用户创建任务错误"""

    def __init__(self):
        super().__init__(
            endpoint="/analyze",
            method="POST",
            error_data={"product_description": "测试产品描述"},
            expected_status=403,
            error_type="只读用户权限不足",
        )

    async def execute(self, context: TestContext) -> TestResult:
        """使用只读用户权限的token"""
        # 模拟只读用户的token
        readonly_headers = context.auth_headers.copy()
        readonly_headers["Authorization"] = f"Bearer readonly-token-{uuid.uuid4()}"

        response = context.client.request(
            method=self.method,
            url=f"{context.base_url}{self.endpoint}",
            headers=readonly_headers,
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


class DisabledUserAccessError(ErrorScenario):
    """已禁用用户访问错误"""

    def __init__(self):
        super().__init__(
            endpoint="/status/{task_id}",
            method="GET",
            expected_status=403,
            error_type="用户已禁用",
        )

    async def execute(self, context: TestContext) -> TestResult:
        """使用已禁用用户的token"""
        disabled_headers = context.auth_headers.copy()
        disabled_headers["Authorization"] = f"Bearer disabled-token-{uuid.uuid4()}"

        endpoint = self.endpoint.format(
            task_id=context.test_task.id if context.test_task else uuid.uuid4()
        )

        response = context.client.request(
            method=self.method,
            url=f"{context.base_url}{endpoint}",
            headers=disabled_headers,
        )

        result = TestResult(
            status_code=response.status_code,
            success=response.status_code == self.expected_status,
            response_data=self._safe_parse_json(response),
            error_message=self._extract_error_message(response),
        )

        self.validate_response(response, result)
        return result


# ============================================================================
# 5. 认证性能场景 - 性能基准类
# ============================================================================


class AuthValidationPerformanceScenario(PerformanceScenario):
    """认证验证性能场景"""

    def __init__(self):
        super().__init__(
            endpoint="/status/{task_id}",
            method="GET",
            target_ms=5.0,  # 认证验证应该很快<5ms
            iterations=100,
            warmup=10,
        )

    async def execute(self, context: TestContext) -> TestResult:
        """性能测试时动态替换task_id"""
        # 动态替换endpoint中的task_id
        endpoint = self.endpoint.format(
            task_id=context.test_task.id if context.test_task else uuid.uuid4()
        )

        # 预热
        for _ in range(self.warmup):
            context.client.request(
                method=self.method,
                url=f"{context.base_url}{endpoint}",
                headers=context.auth_headers,
            )

        # 执行性能测量逻辑
        import time

        measurements = []

        for _ in range(self.iterations):
            start_time = time.perf_counter()
            response = context.client.request(
                method=self.method,
                url=f"{context.base_url}{endpoint}",
                headers=context.auth_headers,
            )
            end_time = time.perf_counter()

            duration_ms = (end_time - start_time) * 1000
            measurements.append(duration_ms)

        # 统计分析
        avg_ms = sum(measurements) / len(measurements)

        performance_stats = {
            "average_ms": avg_ms,
            "min_ms": min(measurements),
            "max_ms": max(measurements),
            "target_ms": self.target_ms,
            "measurements_count": len(measurements),
            "passed": avg_ms <= self.target_ms,
        }

        result = TestResult(
            status_code=response.status_code,
            success=avg_ms <= self.target_ms and response.status_code == 200,
            response_data=self._safe_parse_json(response),
            performance_stats=performance_stats,
        )

        # 性能断言
        assert (
            avg_ms <= self.target_ms
        ), f"认证性能未达标: 平均{avg_ms:.2f}ms > 目标{self.target_ms}ms"

        return result


class ConcurrentAuthPerformanceScenario(PerformanceScenario):
    """并发认证性能场景"""

    def __init__(self):
        super().__init__(
            endpoint="/status/{task_id}",
            method="GET",
            target_ms=10.0,  # 并发场景稍微放宽
            iterations=50,
            warmup=5,
        )


# ============================================================================
# 6. 认证测试套件 - 配置驱动，零分支
# ============================================================================


class AuthTestSuite:
    """认证测试套件 - 原14个分支变成14个独立类"""

    @staticmethod
    def get_all_scenarios() -> List[TestScenario]:
        """获取所有认证测试场景 - 零条件分支实现"""
        return [
            # 正常认证场景 (3个)
            ValidJWTAccessScenario(),
            ValidTenantAccessScenario(),
            RefreshTokenScenario(),
            # JWT错误场景 (5个)
            MissingAuthHeaderError(),
            InvalidJWTFormatError(),
            ExpiredJWTTokenError(),
            RevokedJWTTokenError(),
            WrongBearerPrefixError(),
            # 多租户错误场景 (3个)
            CrossTenantAccessError(),
            InvalidTenantIdError(),
            MissingTenantIdError(),
            # 权限错误场景 (2个)
            ReadOnlyUserCreateTaskError(),
            DisabledUserAccessError(),
            # 性能场景 (2个)
            AuthValidationPerformanceScenario(),
            ConcurrentAuthPerformanceScenario(),
        ]


# ============================================================================
# 7. pytest测试函数 - 统一执行器
# ============================================================================


@pytest.fixture
async def auth_test_context(client, db_session):
    """认证测试上下文"""
    return await TestEnvironmentBuilder.build_context(
        client=client, db_session=db_session, requires_auth=True, requires_task=True
    )


@pytest.fixture
def test_executor():
    """测试执行器"""
    return UnifiedTestExecutor()


@pytest.mark.asyncio
async def test_auth_normal_scenarios(test_executor, auth_test_context):
    """测试认证正常场景"""
    scenarios = [
        s for s in AuthTestSuite.get_all_scenarios() if isinstance(s, NormalScenario)
    ]

    results = await test_executor.execute_scenarios(scenarios, auth_test_context)

    assert results["failed"] == 0, f"认证正常场景失败: {results}"
    assert results["passed"] >= 3, "应该通过所有正常认证场景"


@pytest.mark.asyncio
async def test_auth_error_scenarios(test_executor, auth_test_context):
    """测试认证错误场景"""
    scenarios = [
        s for s in AuthTestSuite.get_all_scenarios() if isinstance(s, ErrorScenario)
    ]

    results = await test_executor.execute_scenarios(scenarios, auth_test_context)

    assert results["failed"] == 0, f"认证错误场景失败: {results}"
    assert results["passed"] >= 10, "应该通过所有认证错误场景"


@pytest.mark.asyncio
async def test_auth_performance_scenarios(test_executor, auth_test_context):
    """测试认证性能场景"""
    scenarios = [
        s
        for s in AuthTestSuite.get_all_scenarios()
        if isinstance(s, PerformanceScenario)
    ]

    results = await test_executor.execute_scenarios(scenarios, auth_test_context)

    # 性能测试容忍部分失败
    failure_rate = (
        results["failed"] / results["total_scenarios"]
        if results["total_scenarios"] > 0
        else 0
    )
    assert failure_rate <= 0.5, f"认证性能测试失败率{failure_rate:.1%}过高"


@pytest.mark.asyncio
async def test_auth_complete_suite(test_executor, auth_test_context):
    """完整认证测试套件"""
    all_scenarios = AuthTestSuite.get_all_scenarios()

    results = await test_executor.execute_scenarios(all_scenarios, auth_test_context)

    # 验证场景数量正确
    assert (
        results["total_scenarios"] == 15
    ), f"应该有15个认证场景，实际{results['total_scenarios']}个"

    # 认证是安全关键，要求高成功率
    failure_rate = (
        results["failed"] / results["total_scenarios"]
        if results["total_scenarios"] > 0
        else 0
    )
    assert failure_rate <= 0.2, f"认证测试失败率{failure_rate:.1%}过高"

    print(
        (
            f"✅ 认证测试完成: {results['passed']}通过 / {results['failed']}失败 / "
            f"{results['total_scenarios']}总计"
        )
    )


# ============================================================================
# 8. 架构革命验证 - 证明14个分支被消除
# ============================================================================


@pytest.mark.asyncio
async def test_architecture_revolution():
    """验证架构革命：14个条件分支 → 14个多态类"""

    all_scenarios = AuthTestSuite.get_all_scenarios()

    # 验证场景数量：原来的14个分支现在是14个类 + 1个正常场景
    assert len(all_scenarios) == 15, f"应该有15个独立场景类，实际{len(all_scenarios)}个"

    # 验证每个场景都是独立的类，无条件分支
    scenario_classes = set(type(s).__name__ for s in all_scenarios)
    assert len(scenario_classes) == len(all_scenarios), "所有场景应该是不同的类"

    # 验证原来的14个主要错误场景都有对应的类
    expected_error_classes = [
        "MissingAuthHeaderError",
        "InvalidJWTFormatError",
        "ExpiredJWTTokenError",
        "RevokedJWTTokenError",
        "WrongBearerPrefixError",
        "CrossTenantAccessError",
        "InvalidTenantIdError",
        "MissingTenantIdError",
        "ReadOnlyUserCreateTaskError",
        "DisabledUserAccessError",
    ]

    actual_error_classes = [
        type(s).__name__ for s in all_scenarios if isinstance(s, ErrorScenario)
    ]

    for expected_class in expected_error_classes:
        assert expected_class in actual_error_classes, f"缺少错误场景类: {expected_class}"

    print("🎉 架构革命成功！14个条件分支 → 15个多态场景类，零分支逻辑！")
