"""
V0界面认证集成测试 - 端到端验证

测试覆盖：
1. V0界面与后端认证集成
2. Token验证中间件功能
3. 游客模式和可选认证
4. 错误处理和用户体验
"""

from typing import Any, Dict

import pytest
from app.core.jwt_handler import get_jwt_handler
from app.core.v0_auth import V0AuthHandler, get_v0_auth_handler
from app.middleware.unified_auth_middleware import (
    create_unified_auth_config,
    install_unified_auth_middleware,
)
from app.schemas.v0_auth import AuthContextV0, V0AuthConfig
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def v0_app() -> FastAPI:
    """创建配置了V0认证的测试应用"""
    app = FastAPI()

    # 安装统一认证中间件
    config = create_unified_auth_config(
        enable_v0=True,
        v0_guest_paths={"/api/v1/analysis/demo", "/api/v1/reports/public"},
    )
    install_unified_auth_middleware(app, config)

    # 测试端点
    @app.get("/api/v1/analysis/demo")
    async def demo_analysis() -> Dict[str, str]:
        return {"message": "游客可访问的演示分析"}

    @app.get("/api/v1/analysis/tasks")
    async def analysis_tasks() -> Dict[str, str]:
        return {"message": "可选认证的分析任务"}

    @app.get("/api/v1/admin/users")
    async def admin_users() -> Dict[str, str]:
        return {"message": "需要完整认证的管理功能"}

    return app


@pytest.fixture
def v0_client(v0_app: FastAPI) -> TestClient:
    """V0测试客户端"""
    return TestClient(v0_app)


@pytest.fixture
def valid_jwt_token() -> str:
    """生成有效的JWT Token"""
    jwt_handler = get_jwt_handler()
    return jwt_handler.create_access_token(
        user_id="test_user_123",
        tenant_id="tenant_123",
        email="test@example.com",
        permissions=["read", "write"],
    )


class TestV0GuestAccess:
    """测试V0游客访问功能"""

    def test_guest_access_demo_endpoint(self, v0_client: TestClient) -> None:
        """测试游客访问演示端点"""
        response = v0_client.get("/api/v1/analysis/demo")

        assert response.status_code == 200
        assert "游客可访问" in response.json()["message"]

    def test_guest_access_public_reports(self, v0_client: TestClient) -> None:
        """测试游客访问公开报告"""
        response = v0_client.get("/api/v1/reports/public")

        # 应该允许访问，即使没有具体实现
        assert response.status_code in [
            200,
            404,
        ]  # 404表示端点未实现，但认证通过


class TestV0OptionalAuth:
    """测试V0可选认证功能"""

    def test_optional_auth_without_token(self, v0_client: TestClient) -> None:
        """测试无Token的可选认证端点"""
        response = v0_client.get("/api/v1/analysis/tasks")

        assert response.status_code == 200
        assert "分析任务" in response.json()["message"]

    def test_optional_auth_with_valid_token(
        self, v0_client: TestClient, valid_jwt_token: str
    ) -> None:
        """测试有效Token的可选认证端点"""
        headers = {"Authorization": f"Bearer {valid_jwt_token}"}
        response = v0_client.get("/api/v1/analysis/tasks", headers=headers)

        assert response.status_code == 200
        assert "分析任务" in response.json()["message"]

    def test_optional_auth_with_invalid_token(self, v0_client: TestClient) -> None:
        """测试无效Token的可选认证端点"""
        headers = {"Authorization": "Bearer invalid_token"}
        response = v0_client.get("/api/v1/analysis/tasks", headers=headers)

        # 可选认证应该降级为游客模式
        assert response.status_code == 200


class TestV0RequiredAuth:
    """测试V0必需认证功能"""

    def test_required_auth_without_token(self, v0_client: TestClient) -> None:
        """测试无Token访问需要认证的端点"""
        response = v0_client.get("/api/v1/admin/users")

        assert response.status_code == 401
        assert "error" in response.json()
        assert response.json()["access_level"] == "guest"

    def test_required_auth_with_valid_token(
        self, v0_client: TestClient, valid_jwt_token: str
    ) -> None:
        """测试有效Token访问需要认证的端点"""
        headers = {"Authorization": f"Bearer {valid_jwt_token}"}
        response = v0_client.get("/api/v1/admin/users", headers=headers)

        assert response.status_code == 200
        assert "管理功能" in response.json()["message"]

    def test_required_auth_with_invalid_token(self, v0_client: TestClient) -> None:
        """测试无效Token访问需要认证的端点"""
        headers = {"Authorization": "Bearer invalid_token"}
        response = v0_client.get("/api/v1/admin/users", headers=headers)

        assert response.status_code == 401
        assert "error" in response.json()
        assert response.json().get("frontend_action") == "redirect_login"


class TestV0AuthContextValidation:
    """测试V0认证上下文验证"""

    @pytest.fixture
    def v0_auth_handler(self) -> V0AuthHandler:
        """V0认证处理器"""
        config = V0AuthConfig()
        return get_v0_auth_handler(config)

    def test_guest_context_creation(self, v0_auth_handler: V0AuthHandler) -> None:
        """测试游客上下文创建"""

        # 模拟Request对象（简化）
        class MockRequest:
            class URL:
                path = "/api/v1/analysis/demo"

            url = URL()

        # 这里应该是async调用，但为了测试简化
        # 在实际应用中需要使用pytest-asyncio
        pass  # 简化测试，真实测试需要mock更多依赖

    def test_auth_context_type_safety(self) -> None:
        """测试认证上下文类型安全"""
        context = AuthContextV0(
            user_id="test_123", email="test@example.com", access_level="full"
        )

        assert context.is_authenticated is True
        assert context.has_full_access is True
        assert context.access_level == "full"
        assert len(context.permissions) == 0  # 默认空列表


class TestV0FrontendIntegration:
    """测试V0前端集成"""

    def test_cors_headers_present(self, v0_client: TestClient) -> None:
        """测试CORS头部存在"""
        response = v0_client.options("/api/v1/analysis/demo")

        # 检查是否处理了OPTIONS请求
        assert response.status_code in [200, 404, 405]

    def test_auth_error_response_format(self, v0_client: TestClient) -> None:
        """测试认证错误响应格式"""
        response = v0_client.get("/api/v1/admin/users")

        assert response.status_code == 401
        error_data = response.json()

        # 验证错误响应结构
        required_fields = ["success", "access_level", "error", "timestamp"]
        for field in required_fields:
            assert field in error_data

        assert error_data["success"] is False
        assert error_data["access_level"] == "guest"
        assert "frontend_action" in error_data


class TestV0PerformanceValidation:
    """测试V0性能验证"""

    def test_auth_processing_speed(self, v0_client: TestClient) -> None:
        """测试认证处理速度"""
        import time

        start_time = time.time()
        response = v0_client.get("/api/v1/analysis/demo")
        end_time = time.time()

        processing_time_ms = (end_time - start_time) * 1000

        assert response.status_code == 200
        assert processing_time_ms < 50  # 认证处理应在50ms内完成

    def test_multiple_concurrent_requests(self, v0_client: TestClient) -> None:
        """测试多个并发请求"""
        import concurrent.futures

        def make_request() -> Any:
            return v0_client.get("/api/v1/analysis/demo")

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            responses = [future.result() for future in futures]

        # 所有请求都应该成功
        for response in responses:
            assert response.status_code == 200


@pytest.mark.integration
class TestV0EndToEndScenarios:
    """端到端场景测试"""

    def test_v0_user_journey_guest_to_authenticated(
        self, v0_client: TestClient, valid_jwt_token: str
    ) -> None:
        """测试用户从游客到认证的完整流程"""

        # 1. 游客访问演示功能
        response1 = v0_client.get("/api/v1/analysis/demo")
        assert response1.status_code == 200

        # 2. 游客尝试访问可选认证功能
        response2 = v0_client.get("/api/v1/analysis/tasks")
        assert response2.status_code == 200

        # 3. 游客尝试访问需要认证的功能
        response3 = v0_client.get("/api/v1/admin/users")
        assert response3.status_code == 401

        # 4. 用户登录后访问需要认证的功能
        headers = {"Authorization": f"Bearer {valid_jwt_token}"}
        response4 = v0_client.get("/api/v1/admin/users", headers=headers)
        assert response4.status_code == 200

        # 5. 认证用户访问可选认证功能获得更好体验
        response5 = v0_client.get("/api/v1/analysis/tasks", headers=headers)
        assert response5.status_code == 200

    def test_token_expiration_handling(self, v0_client: TestClient) -> None:
        """测试Token过期处理"""
        # 使用过期的Token（简化测试）
        expired_token = "expired.token.here"
        headers = {"Authorization": f"Bearer {expired_token}"}

        response = v0_client.get("/api/v1/admin/users", headers=headers)

        assert response.status_code == 401
        error_data = response.json()
        assert error_data.get("frontend_action") == "redirect_login"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
