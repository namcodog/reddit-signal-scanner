"""
Reddit Signal Scanner - 认证API集成测试

基于Linus原则和quality-gate Agent要求：
- 完整的HTTP状态码覆盖
- 边界条件和异常路径测试
- 安全漏洞验证（SQL注入、XSS等）
- 性能基准和并发测试
"""

import json  # noqa: F401
import uuid
from typing import Dict, Any
from unittest.mock import patch, Mock  # noqa: F401

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.auth import UserRegisterRequest, UserRegisterResponse  # noqa: F401
try:
    from .base import TestResult  # type: ignore  # noqa: F401
except Exception:  # 兼容在根目录运行pytest时的旧路径
    from tests.api.base import TestResult  # type: ignore  # noqa: F401


class TestAuthRegisterAPI:
    """用户注册API端点测试"""

    @pytest.fixture
    def client(self):
        """FastAPI测试客户端"""
        return TestClient(app)

    @pytest.fixture
    def valid_registration_payload(self) -> Dict[str, str]:
        """标准有效注册负载"""
        return {
            "email": "api.test@example.com",
            "password": "ApiTestPassword123!",
            "confirm_password": "ApiTestPassword123!",
        }

    @pytest.fixture
    def edge_case_payloads(self) -> Dict[str, Dict[str, str]]:
        """边界条件注册负载"""
        return {
            # 邮箱长度边界（320字符 - RFC 5321）
            "max_email_length": {
                "email": "x" * 64 + "@" + "y" * 251 + ".com",
                "password": "EdgeCasePassword123!",
                "confirm_password": "EdgeCasePassword123!",
            },
            # 最短有效邮箱
            "min_email_length": {
                "email": "a@b.co",
                "password": "MinEmailPassword123!",
                "confirm_password": "MinEmailPassword123!",
            },
            # 密码长度边界（8字符）
            "min_password_length": {
                "email": "min.pass@example.com",
                "password": "Aa1!5678",
                "confirm_password": "Aa1!5678",
            },
            # 复杂邮箱格式
            "complex_email": {
                "email": "test.email+tag123@sub.domain-name.com",
                "password": "ComplexEmailPassword123!",
                "confirm_password": "ComplexEmailPassword123!",
            },
            # 最大密码长度（128字符）
            "max_password_length": {
                "email": "max.pass@example.com",
                "password": "A1!" + "x" * 125,  # 128字符
                "confirm_password": "A1!" + "x" * 125,
            },
        }

    # ============================================================================
    # 1. 成功场景测试
    # ============================================================================

    def test_register_success_standard(self, client, valid_registration_payload):
        """标准用户注册成功"""
        response = client.post("/api/v1/auth/register", json=valid_registration_payload)

        # 验证HTTP响应
        assert response.status_code == status.HTTP_201_CREATED

        # 验证响应数据结构
        data = response.json()
        assert "user_id" in data
        assert "tenant_id" in data
        assert "email" in data
        assert "access_token" in data
        assert "refresh_token" in data

        # 验证返回数据
        assert data["email"] == valid_registration_payload["email"].lower()
        assert data["is_active"] is True
        assert data["email_verified"] is False
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 3600

        # 验证UUID格式
        assert len(data["user_id"]) == 36  # UUID格式
        assert len(data["tenant_id"]) == 36

        # 验证JWT tokens
        assert len(data["access_token"]) > 50
        assert len(data["refresh_token"]) > 50

        # 验证响应头
        assert response.headers.get("content-type") == "application/json"

    def test_register_success_edge_cases(self, client, edge_case_payloads):
        """边界条件注册成功"""
        for case_name, payload in edge_case_payloads.items():
            # 每个测试用不同的邮箱避免冲突
            payload["email"] = f"{case_name}.{payload['email']}"

            response = client.post("/api/v1/auth/register", json=payload)

            assert response.status_code == status.HTTP_201_CREATED, f"失败案例: {case_name}"

            data = response.json()
            assert data["email"] == payload["email"].lower(), f"失败案例: {case_name}"
            assert "access_token" in data, f"失败案例: {case_name}"

    def test_register_email_case_insensitive(self, client):
        """邮箱注册大小写不敏感"""
        base_payload = {
            "email": "Case.Insensitive@Example.COM",
            "password": "CaseTestPassword123!",
            "confirm_password": "CaseTestPassword123!",
        }

        response = client.post("/api/v1/auth/register", json=base_payload)
        assert response.status_code == status.HTTP_201_CREATED

        data = response.json()
        # 邮箱应该被转换为小写
        assert data["email"] == base_payload["email"].lower()

    # ============================================================================
    # 2. 验证错误测试（422 Unprocessable Entity）
    # ============================================================================

    def test_register_validation_errors_comprehensive(self, client):
        """全面的输入验证错误测试"""
        validation_test_cases = [
            # 邮箱格式错误
            {
                "name": "invalid_email_format",
                "payload": {
                    "email": "invalid-email-format",
                    "password": "ValidPassword123!",
                    "confirm_password": "ValidPassword123!",
                },
                "expected_field": "email",
            },
            # 邮箱缺少域名
            {
                "name": "email_no_domain",
                "payload": {
                    "email": "user@",
                    "password": "ValidPassword123!",
                    "confirm_password": "ValidPassword123!",
                },
                "expected_field": "email",
            },
            # 邮箱缺少@符号
            {
                "name": "email_no_at",
                "payload": {
                    "email": "userdomain.com",
                    "password": "ValidPassword123!",
                    "confirm_password": "ValidPassword123!",
                },
                "expected_field": "email",
            },
            # 密码太短
            {
                "name": "password_too_short",
                "payload": {
                    "email": "valid@example.com",
                    "password": "Short1!",  # 7字符
                    "confirm_password": "Short1!",
                },
                "expected_field": "password",
            },
            # 密码无大写字母
            {
                "name": "password_no_uppercase",
                "payload": {
                    "email": "valid@example.com",
                    "password": "nouppercase123!",
                    "confirm_password": "nouppercase123!",
                },
                "expected_field": "password",
            },
            # 密码无小写字母
            {
                "name": "password_no_lowercase",
                "payload": {
                    "email": "valid@example.com",
                    "password": "NOLOWERCASE123!",
                    "confirm_password": "NOLOWERCASE123!",
                },
                "expected_field": "password",
            },
            # 密码无数字
            {
                "name": "password_no_numbers",
                "payload": {
                    "email": "valid@example.com",
                    "password": "NoNumbersPassword!",
                    "confirm_password": "NoNumbersPassword!",
                },
                "expected_field": "password",
            },
            # 密码无特殊字符
            {
                "name": "password_no_special",
                "payload": {
                    "email": "valid@example.com",
                    "password": "NoSpecialChars123",
                    "confirm_password": "NoSpecialChars123",
                },
                "expected_field": "password",
            },
            # 密码不匹配
            {
                "name": "password_mismatch",
                "payload": {
                    "email": "valid@example.com",
                    "password": "ValidPassword123!",
                    "confirm_password": "DifferentPassword123!",
                },
                "expected_field": "confirm_password",
            },
            # 包含弱密码模式
            {
                "name": "weak_password_pattern",
                "payload": {
                    "email": "valid@example.com",
                    "password": "Password123456!",  # 包含123456
                    "confirm_password": "Password123456!",
                },
                "expected_field": "password",
            },
        ]

        for test_case in validation_test_cases:
            response = client.post("/api/v1/auth/register", json=test_case["payload"])

            # 验证HTTP状态码
            assert (
                response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
            ), f"失败案例: {test_case['name']}"

            # 验证响应结构
            data = response.json()
            assert "detail" in data, f"失败案例: {test_case['name']}"

            # 验证错误字段
            if isinstance(data["detail"], list) and len(data["detail"]) > 0:
                error_fields = [
                    error.get("loc", [])[-1] for error in data["detail"]
                ]
                assert (
                    test_case["expected_field"] in error_fields
                ), (
                    f"失败案例: {test_case['name']}, 预期字段: "
                    f"{test_case['expected_field']}, 实际错误: {data}"
                )

    def test_register_missing_required_fields(self, client):
        """缺失必填字段测试"""
        required_fields_test = [
            # 缺失邮箱
            {
                "payload": {
                    "password": "ValidPassword123!",
                    "confirm_password": "ValidPassword123!",
                },
                "missing_field": "email",
            },
            # 缺失密码
            {
                "payload": {
                    "email": "valid@example.com",
                    "confirm_password": "ValidPassword123!",
                },
                "missing_field": "password",
            },
            # 缺失确认密码
            {
                "payload": {
                    "email": "valid@example.com",
                    "password": "ValidPassword123!",
                },
                "missing_field": "confirm_password",
            },
            # 空负载
            {"payload": {}, "missing_field": "multiple"},
        ]

        for test_case in required_fields_test:
            response = client.post("/api/v1/auth/register", json=test_case["payload"])

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
            data = response.json()
            assert "detail" in data

    # ============================================================================
    # 3. 业务逻辑错误测试（409 Conflict）
    # ============================================================================

    def test_register_duplicate_email_conflict(self, client):
        """重复邮箱冲突测试"""
        payload = {
            "email": "duplicate@example.com",
            "password": "DuplicateTest123!",
            "confirm_password": "DuplicateTest123!",
        }

        # 第一次注册成功
        response1 = client.post("/api/v1/auth/register", json=payload)
        assert response1.status_code == status.HTTP_201_CREATED

        # 第二次注册相同邮箱应该失败
        response2 = client.post("/api/v1/auth/register", json=payload)
        assert response2.status_code == status.HTTP_409_CONFLICT

        data = response2.json()
        assert "detail" in data
        assert "message" in data["detail"]
        assert "已被注册" in data["detail"]["message"]
        assert data["detail"]["error"] == "email_already_exists"
        assert data["detail"]["error_code"] == 4091

    def test_register_duplicate_email_case_insensitive(self, client):
        """重复邮箱大小写不敏感冲突"""
        # 第一次用小写注册
        payload1 = {
            "email": "casetest@example.com",
            "password": "CaseTest123!",
            "confirm_password": "CaseTest123!",
        }
        response1 = client.post("/api/v1/auth/register", json=payload1)
        assert response1.status_code == status.HTTP_201_CREATED

        # 第二次用大写注册应该失败
        payload2 = {
            "email": "CASETEST@EXAMPLE.COM",
            "password": "CaseTest123!",
            "confirm_password": "CaseTest123!",
        }
        response2 = client.post("/api/v1/auth/register", json=payload2)
        assert response2.status_code == status.HTTP_409_CONFLICT

    # ============================================================================
    # 4. 服务器错误测试（500 Internal Server Error）
    # ============================================================================

    def test_register_database_error_handling(self, client):
        """数据库错误处理测试"""
        payload = {
            "email": "db.error@example.com",
            "password": "DbErrorTest123!",
            "confirm_password": "DbErrorTest123!",
        }

        # Mock数据库错误
        with patch(
            "app.services.auth_service.auth_service.register_user",
            side_effect=Exception("Database connection failed"),
        ):
            response = client.post("/api/v1/auth/register", json=payload)

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert "detail" in data
            assert data["detail"]["error"] == "internal_server_error"
            assert data["detail"]["error_code"] == 5001

    def test_register_jwt_service_error_handling(self, client):
        """JWT服务错误处理测试"""
        payload = {
            "email": "jwt.error@example.com",
            "password": "JwtErrorTest123!",
            "confirm_password": "JwtErrorTest123!",
        }

        # Mock JWT生成错误
        with patch(
            "app.core.jwt_handler.JWTHandler.create_access_token",
            side_effect=Exception("JWT generation failed"),
        ):
            response = client.post("/api/v1/auth/register", json=payload)

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert "detail" in data
            assert data["detail"]["error"] == "internal_server_error"

    # ============================================================================
    # 5. 安全测试
    # ============================================================================

    def test_register_sql_injection_prevention(self, client):
        """SQL注入攻击防护测试"""
        sql_injection_payloads = [
            {
                "email": "test@example.com'; DROP TABLE users; --",
                "password": "SqlInjectionTest123!",
                "confirm_password": "SqlInjectionTest123!",
            },
            {
                "email": "test@example.com",
                "password": "'; DELETE FROM users; --123!Aa",
                "confirm_password": "'; DELETE FROM users; --123!Aa",
            },
            {
                "email": "admin'--@example.com",
                "password": "UnionSelect123!",
                "confirm_password": "UnionSelect123!",
            },
        ]

        for payload in sql_injection_payloads:
            response = client.post("/api/v1/auth/register", json=payload)

            # SQL注入应该被Pydantic验证拦截或安全处理
            # 不应该导致500错误，应该是400/422验证错误
            assert response.status_code in [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            ], (
                f"SQL注入负载应该被安全处理: {payload['email']}"
            )

    def test_register_xss_prevention(self, client):
        """XSS攻击防护测试"""
        xss_payloads = [
            {
                "email": "<script>alert('xss')</script>@example.com",
                "password": "XssTest123!",
                "confirm_password": "XssTest123!",
            },
            {
                "email": "javascript:alert('xss')@example.com",
                "password": "XssTest123!",
                "confirm_password": "XssTest123!",
            },
            {
                "email": "test@example.com",
                "password": "<script>alert('xss')</script>123!Aa",
                "confirm_password": "<script>alert('xss')</script>123!Aa",
            },
        ]

        for payload in xss_payloads:
            response = client.post("/api/v1/auth/register", json=payload)

            # XSS攻击应该被输入验证拦截
            assert response.status_code in [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            ], f"XSS负载应该被安全处理: {payload['email']}"

    def test_register_oversized_payload_handling(self, client):
        """超大负载处理测试"""
        # 超长邮箱（超过320字符限制）
        oversized_payload = {
            "email": "x" * 300 + "@" + "y" * 300 + ".com",  # 远超320字符
            "password": "OversizedTest123!",
            "confirm_password": "OversizedTest123!",
        }

        response = client.post("/api/v1/auth/register", json=oversized_payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # 超长密码（超过128字符限制）
        oversized_password = "A1!" + "x" * 200  # 203字符
        oversized_payload2 = {
            "email": "oversized@example.com",
            "password": oversized_password,
            "confirm_password": oversized_password,
        }

        response2 = client.post("/api/v1/auth/register", json=oversized_payload2)
        assert response2.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # ============================================================================
    # 6. 内容类型和HTTP方法测试
    # ============================================================================

    def test_register_content_type_validation(self, client):
        """Content-Type验证测试"""
        payload = {
            "email": "content.type@example.com",
            "password": "ContentTypeTest123!",
            "confirm_password": "ContentTypeTest123!",
        }

        # 正确的Content-Type
        response_json = client.post("/api/v1/auth/register", json=payload)
        assert response_json.status_code == status.HTTP_201_CREATED

        # 错误的Content-Type (form data)
        response_form = client.post(
            "/api/v1/auth/register",
            data=payload,  # 使用data而不是json
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        # FastAPI应该处理这种情况，但结构可能不正确
        assert response_form.status_code in [
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_400_BAD_REQUEST,
        ]

    def test_register_http_methods(self, client):
        """HTTP方法测试"""
        payload = {
            "email": "method.test@example.com",
            "password": "MethodTest123!",
            "confirm_password": "MethodTest123!",
        }

        # POST应该成功
        response_post = client.post("/api/v1/auth/register", json=payload)
        assert response_post.status_code == status.HTTP_201_CREATED

        # 其他方法应该失败
        methods_and_expected_status = [
            ("GET", status.HTTP_405_METHOD_NOT_ALLOWED),
            ("PUT", status.HTTP_405_METHOD_NOT_ALLOWED),
            ("DELETE", status.HTTP_405_METHOD_NOT_ALLOWED),
            ("PATCH", status.HTTP_405_METHOD_NOT_ALLOWED),
        ]

        for method, expected_status in methods_and_expected_status:
            response = client.request(method, "/api/v1/auth/register", json=payload)
            assert (
                response.status_code == expected_status
            ), f"方法 {method} 应该返回 {expected_status}"

    # ============================================================================
    # 7. 性能和并发测试
    # ============================================================================

    def test_register_response_time_performance(self, client, performance_timer):
        """注册响应时间性能测试"""

        def register_operation():
            payload = {
                "email": f"perf.{uuid.uuid4()}@example.com",
                "password": "PerformanceTest123!",
                "confirm_password": "PerformanceTest123!",
            }
            response = client.post("/api/v1/auth/register", json=payload)
            assert response.status_code == status.HTTP_201_CREATED

        # 测量注册操作性能
        performance_timer.measure_operation(register_operation, iterations=10)
        stats = performance_timer.get_stats()

        # 用户注册应该在合理时间内完成（< 2000ms，包含BCrypt）
        assert stats["mean"] < 2000, f"注册平均响应时间过长: {stats}"
        assert stats["p95"] < 3000, f"注册P95响应时间过长: {stats}"

    def test_register_concurrent_requests(self, client):
        """并发注册请求测试"""
        import threading
        import queue

        results = queue.Queue()

        def register_user(user_id):
            try:
                payload = {
                    "email": f"concurrent.{user_id}@example.com",
                    "password": "ConcurrentTest123!",
                    "confirm_password": "ConcurrentTest123!",
                }
                response = client.post("/api/v1/auth/register", json=payload)
                results.put(("success", response.status_code, user_id))
            except Exception as e:
                results.put(("error", str(e), user_id))

        # 启动10个并发注册请求
        threads = []
        for i in range(10):
            thread = threading.Thread(target=register_user, args=(i,))
            threads.append(thread)
            thread.start()

        # 等待所有线程完成
        for thread in threads:
            thread.join()

        # 验证结果
        success_count = 0
        error_count = 0

        while not results.empty():
            result_type, status_or_error, user_id = results.get()
            if result_type == "success":
                success_count += 1
                assert (
                    status_or_error == status.HTTP_201_CREATED
                ), f"并发用户 {user_id} 注册失败"
            else:
                error_count += 1

        # 至少80%的并发请求应该成功
        assert success_count >= 8, f"并发注册成功率太低: {success_count}/10"


class TestAuthHealthAPI:
    """认证服务健康检查API测试"""

    @pytest.fixture
    def client(self):
        """FastAPI测试客户端"""
        return TestClient(app)

    def test_auth_health_check_success(self, client):
        """健康检查成功测试"""
        response = client.get("/api/v1/auth/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # 验证响应结构
        assert "status" in data
        assert "timestamp" in data
        assert "checks" in data

        # 验证检查项
        expected_checks = ["database", "jwt_service", "bcrypt", "schema_validation"]
        for check in expected_checks:
            assert check in data["checks"], f"缺少健康检查项: {check}"
            assert data["checks"][check]["status"] == "healthy", f"检查项不健康: {check}"

    def test_auth_health_check_database_failure(self, client):
        """数据库故障时的健康检查"""
        # Mock数据库连接失败
        with patch(
            "app.core.database.get_db", side_effect=Exception("Database unavailable")
        ):
            response = client.get("/api/v1/auth/health")

            # 健康检查应该仍然返回200，但状态为unhealthy
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "unhealthy"
            assert "error" in data


class TestAuthNotImplementedEndpoints:
    """未实现端点测试"""

    @pytest.fixture
    def client(self):
        """FastAPI测试客户端"""
        return TestClient(app)

    def test_login_not_implemented(self, client):
        """登录端点未实现测试"""
        payload = {"email": "test@example.com", "password": "TestPassword123!"}

        response = client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED

        data = response.json()
        assert data["detail"]["error"] == "not_implemented"
        assert data["detail"]["error_code"] == 5011

    def test_reset_password_not_implemented(self, client):
        """密码重置端点未实现测试"""
        payload = {"email": "test@example.com"}

        response = client.post("/api/v1/auth/reset-password", json=payload)
        assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED

        data = response.json()
        assert data["detail"]["error"] == "not_implemented"
        assert data["detail"]["error_code"] == 5012


# ============================================================================
# 性能基准测试工具
# ============================================================================


@pytest.fixture
def api_performance_tester():
    """API性能测试工具"""

    class APIPerformanceTester:
        def __init__(self, client: TestClient):
            self.client = client

        def measure_endpoint_performance(
            self,
            method: str,
            url: str,
            payload: Dict[str, Any] = None,
            iterations: int = 50,
        ) -> Dict[str, float]:
            """测量API端点性能"""
            import time
            import statistics

            measurements = []

            # 预热
            for _ in range(5):
                if method.upper() == "GET":
                    self.client.get(url)
                elif method.upper() == "POST":
                    self.client.post(url, json=payload)

            # 实际测量
            for i in range(iterations):
                # 每次使用不同的数据避免缓存和重复键错误
                if payload and "email" in payload:
                    test_payload = payload.copy()
                    test_payload["email"] = f"perf.{i}.{payload['email']}"
                else:
                    test_payload = payload

                start = time.perf_counter()
                if method.upper() == "GET":
                    self.client.get(url)
                elif method.upper() == "POST":
                    self.client.post(url, json=test_payload)
                end = time.perf_counter()

                measurements.append((end - start) * 1000)  # 转换为毫秒

            return {
                "mean": statistics.mean(measurements),
                "median": statistics.median(measurements),
                "min": min(measurements),
                "max": max(measurements),
                "p95": statistics.quantiles(measurements, n=20)[18]
                if len(measurements) >= 20
                else max(measurements),
                "p99": statistics.quantiles(measurements, n=100)[98]
                if len(measurements) >= 100
                else max(measurements),
                "std_dev": statistics.stdev(measurements)
                if len(measurements) > 1
                else 0,
            }

    return APIPerformanceTester
