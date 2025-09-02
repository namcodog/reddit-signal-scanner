"""
JWT认证系统单元测试

Linus测试哲学：
- 测试核心逻辑，不测试框架
- 每个测试只验证一件事
- 测试失败场景比成功场景更重要
- 性能测试必须有基准数据
"""

import pytest
import time
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from app.core.jwt_handler import (
    JWTHandler,
    JWTKeys,
    TokenPayload,
    get_jwt_handler,
    create_user_tokens,
    setup_jwt_keys_if_needed,
)
from app.core.auth import (
    CurrentUser,
    AuthenticationError,
    PermissionError,
    TenantAccessError,
)
from app.core.config import Settings


class TestJWTKeys:
    """JWT密钥管理测试"""

    def test_hmac_key_default(self):
        """测试HMAC密钥默认值"""
        with patch("app.core.jwt_handler.get_settings") as mock_settings:
            mock_settings.return_value = Settings()
            keys = JWTKeys()

            assert keys.hmac_key == "dev-secret-key-change-in-production"

    def test_rsa_key_generation(self):
        """测试RSA密钥对生成"""
        keys = JWTKeys()
        private_key, public_key = keys.generate_rsa_keypair(2048)

        # 验证密钥格式
        assert private_key.startswith(b"-----BEGIN PRIVATE KEY-----")
        assert private_key.endswith(b"-----END PRIVATE KEY-----\n")
        assert public_key.startswith(b"-----BEGIN PUBLIC KEY-----")
        assert public_key.endswith(b"-----END PUBLIC KEY-----\n")

        # 验证密钥长度
        assert len(private_key) > 1000  # RSA 2048位私钥应该比较长
        assert len(public_key) > 250  # RSA 2048位公钥长度

    def test_rsa_key_loading_file_not_exists(self):
        """测试RSA密钥文件不存在时的处理"""
        with patch("app.core.jwt_handler.get_settings") as mock_settings:
            settings = Settings()
            settings.jwt_private_key_path = "/nonexistent/private.pem"
            settings.jwt_public_key_path = "/nonexistent/public.pem"
            mock_settings.return_value = settings

            keys = JWTKeys()

            # 不应该抛出异常，应该优雅降级
            assert keys.private_key is None
            assert keys.public_key is None

    def test_key_file_permissions(self, tmp_path):
        """测试密钥文件权限设置"""
        private_path = tmp_path / "private.pem"
        public_path = tmp_path / "public.pem"

        with patch("app.core.jwt_handler.get_settings") as mock_settings:
            settings = Settings()
            settings.jwt_private_key_path = str(private_path)
            settings.jwt_public_key_path = str(public_path)
            mock_settings.return_value = settings

            keys = JWTKeys()
            private_key, public_key = keys.generate_rsa_keypair()
            keys.save_keys_to_files(private_key, public_key)

            # 验证文件权限
            private_stat = private_path.stat()
            public_stat = public_path.stat()

            # 私钥：只有所有者可读写 (0o600)
            assert oct(private_stat.st_mode)[-3:] == "600"
            # 公钥：所有者可读写，其他人只读 (0o644)
            assert oct(public_stat.st_mode)[-3:] == "644"


class TestTokenPayload:
    """Token载荷测试"""

    def test_token_payload_creation(self):
        """测试Token载荷创建"""
        payload = TokenPayload(
            user_id="user-123",
            tenant_id="tenant-456",
            email="test@example.com",
            permissions=["read", "write"],
            exp=int(time.time()) + 3600,
            iat=int(time.time()),
            jti="jwt-id-789",
        )

        assert payload.user_id == "user-123"
        assert payload.tenant_id == "tenant-456"
        assert payload.email == "test@example.com"
        assert payload.permissions == ["read", "write"]
        assert payload.token_type == "access"  # 默认值
        assert payload.iss == "reddit-scanner"  # 默认值
        assert payload.aud == "api"  # 默认值

    def test_token_payload_dict_conversion(self):
        """测试Token载荷字典转换"""
        now = int(time.time())
        payload = TokenPayload(
            user_id="user-123",
            tenant_id="tenant-456",
            email="test@example.com",
            permissions=["admin"],
            exp=now + 3600,
            iat=now,
            jti="jwt-id-789",
        )

        payload_dict = payload.dict()

        # 验证所有必要字段存在
        required_fields = [
            "user_id",
            "tenant_id",
            "email",
            "permissions",
            "exp",
            "iat",
            "iss",
            "aud",
            "jti",
            "token_type",
        ]
        for field in required_fields:
            assert field in payload_dict


class TestJWTHandler:
    """JWT处理器测试"""

    @pytest.fixture
    def jwt_handler(self):
        """JWT处理器fixture"""
        with patch("app.core.jwt_handler.get_settings") as mock_settings:
            settings = Settings()
            settings.jwt_secret_key = "test-secret-key-very-long-for-security"
            settings.jwt_algorithm = "HS256"
            settings.jwt_algorithms = "HS256,RS256"
            settings.jwt_access_token_expire_minutes = 60
            settings.jwt_refresh_token_expire_days = 7
            mock_settings.return_value = settings

            return JWTHandler()

    def test_create_access_token(self, jwt_handler):
        """测试访问令牌创建"""
        token = jwt_handler.create_access_token(
            user_id="user-123",
            tenant_id="tenant-456",
            email="test@example.com",
            permissions=["read", "write"],
        )

        assert isinstance(token, str)
        assert len(token) > 100  # JWT token应该比较长

        # 验证token结构（不验证签名）
        payload = jwt.decode(token, options={"verify_signature": False})
        assert payload["user_id"] == "user-123"
        assert payload["tenant_id"] == "tenant-456"
        assert payload["email"] == "test@example.com"
        assert payload["permissions"] == ["read", "write"]
        assert payload["token_type"] == "access"

    def test_create_refresh_token(self, jwt_handler):
        """测试刷新令牌创建"""
        token = jwt_handler.create_refresh_token(
            user_id="user-123", tenant_id="tenant-456", email="test@example.com"
        )

        assert isinstance(token, str)

        # 验证token结构
        payload = jwt.decode(token, options={"verify_signature": False})
        assert payload["user_id"] == "user-123"
        assert payload["tenant_id"] == "tenant-456"
        assert payload["email"] == "test@example.com"
        assert payload["permissions"] == []  # 刷新令牌不包含权限
        assert payload["token_type"] == "refresh"

    def test_verify_token_success(self, jwt_handler):
        """测试Token验证成功"""
        # 创建token
        token = jwt_handler.create_access_token(
            user_id="user-123",
            tenant_id="tenant-456",
            email="test@example.com",
            permissions=["admin"],
        )

        # 验证token
        payload = jwt_handler.verify_token(token)

        assert isinstance(payload, TokenPayload)
        assert payload.user_id == "user-123"
        assert payload.tenant_id == "tenant-456"
        assert payload.email == "test@example.com"
        assert payload.permissions == ["admin"]
        assert payload.token_type == "access"

    def test_verify_token_expired(self, jwt_handler):
        """测试过期Token验证"""
        # 创建立即过期的token
        now = int(time.time())
        payload = {
            "user_id": "user-123",
            "tenant_id": "tenant-456",
            "email": "test@example.com",
            "permissions": [],
            "token_type": "access",
            "exp": now - 1,  # 已过期
            "iat": now - 3600,
            "iss": "reddit-scanner",
            "aud": "api",
            "jti": "test-jti",
        }

        expired_token = jwt.encode(
            payload, jwt_handler.keys.hmac_key, algorithm="HS256"
        )

        with pytest.raises(ExpiredSignatureError):
            jwt_handler.verify_token(expired_token)

    def test_verify_token_invalid_signature(self, jwt_handler):
        """测试无效签名Token验证"""
        # 使用错误密钥签名
        payload = {
            "user_id": "user-123",
            "tenant_id": "tenant-456",
            "email": "test@example.com",
            "permissions": [],
            "token_type": "access",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "iss": "reddit-scanner",
            "aud": "api",
            "jti": "test-jti",
        }

        invalid_token = jwt.encode(payload, "wrong-secret-key", algorithm="HS256")

        with pytest.raises(InvalidTokenError):
            jwt_handler.verify_token(invalid_token)

    def test_verify_access_token_wrong_type(self, jwt_handler):
        """测试验证错误类型的访问令牌"""
        # 创建刷新令牌
        refresh_token = jwt_handler.create_refresh_token(
            user_id="user-123", tenant_id="tenant-456", email="test@example.com"
        )

        # 尝试作为访问令牌验证应该失败
        with pytest.raises(InvalidTokenError, match="无效的访问令牌类型"):
            jwt_handler.verify_access_token(refresh_token)

    def test_refresh_access_token(self, jwt_handler):
        """测试令牌刷新"""
        # 创建刷新令牌
        refresh_token = jwt_handler.create_refresh_token(
            user_id="user-123", tenant_id="tenant-456", email="test@example.com"
        )

        # 刷新获得新令牌
        new_access_token, new_refresh_token = jwt_handler.refresh_access_token(
            refresh_token
        )

        # 验证新的访问令牌
        access_payload = jwt_handler.verify_access_token(new_access_token)
        assert access_payload.user_id == "user-123"
        assert access_payload.tenant_id == "tenant-456"
        assert access_payload.token_type == "access"

        # 验证新的刷新令牌
        refresh_payload = jwt_handler.verify_refresh_token(new_refresh_token)
        assert refresh_payload.user_id == "user-123"
        assert refresh_payload.token_type == "refresh"

    def test_get_token_info_debug(self, jwt_handler):
        """测试Token信息获取（调试功能）"""
        token = jwt_handler.create_access_token(
            user_id="user-123", tenant_id="tenant-456", email="test@example.com"
        )

        token_info = jwt_handler.get_token_info(token)

        assert token_info["user_id"] == "user-123"
        assert token_info["tenant_id"] == "tenant-456"
        assert token_info["algorithm"] == "HS256"
        assert "exp" in token_info
        assert "iat" in token_info


class TestCurrentUser:
    """当前用户测试"""

    @pytest.fixture
    def current_user(self):
        """当前用户fixture"""
        return CurrentUser(
            user_id="user-123",
            tenant_id="tenant-456",
            email="test@example.com",
            permissions=["read", "write", "admin"],
            auth_time=datetime.now(),
        )

    def test_has_permission(self, current_user):
        """测试权限检查"""
        assert current_user.has_permission("read") is True
        assert current_user.has_permission("write") is True
        assert current_user.has_permission("admin") is True
        assert current_user.has_permission("delete") is False

    def test_has_any_permission(self, current_user):
        """测试任一权限检查"""
        assert current_user.has_any_permission(["read", "delete"]) is True
        assert current_user.has_any_permission(["write", "super"]) is True
        assert current_user.has_any_permission(["delete", "super"]) is False

    def test_has_all_permissions(self, current_user):
        """测试所有权限检查"""
        assert current_user.has_all_permissions(["read", "write"]) is True
        assert current_user.has_all_permissions(["read", "admin"]) is True
        assert current_user.has_all_permissions(["read", "delete"]) is False
        assert current_user.has_all_permissions(["delete", "super"]) is False


class TestAuthenticationErrors:
    """认证错误测试"""

    def test_authentication_error_default(self):
        """测试默认认证错误"""
        error = AuthenticationError()
        assert error.status_code == 401
        assert error.detail == "身份验证失败"
        assert error.headers == {"WWW-Authenticate": "Bearer"}

    def test_authentication_error_custom(self):
        """测试自定义认证错误"""
        error = AuthenticationError("令牌已过期")
        assert error.status_code == 401
        assert error.detail == "令牌已过期"

    def test_permission_error(self):
        """测试权限错误"""
        error = PermissionError("需要管理员权限")
        assert error.status_code == 403
        assert error.detail == "需要管理员权限"

    def test_tenant_access_error(self):
        """测试租户访问错误"""
        error = TenantAccessError("无权访问此租户")
        assert error.status_code == 403
        assert error.detail == "无权访问此租户"


class TestIntegrationScenarios:
    """集成测试场景"""

    @pytest.fixture
    def jwt_handler(self):
        """JWT处理器fixture"""
        with patch("app.core.jwt_handler.get_settings") as mock_settings:
            settings = Settings()
            settings.jwt_secret_key = "integration-test-secret-key-very-long"
            settings.jwt_algorithm = "HS256"
            settings.jwt_access_token_expire_minutes = 60
            settings.jwt_refresh_token_expire_days = 7
            mock_settings.return_value = settings

            return JWTHandler()

    def test_complete_auth_flow(self, jwt_handler):
        """测试完整认证流程"""
        # 1. 创建用户令牌对
        user_tokens = create_user_tokens(
            user_id="user-123",
            tenant_id="tenant-456",
            email="test@example.com",
            permissions=["read", "write"],
        )

        assert "access_token" in user_tokens
        assert "refresh_token" in user_tokens
        assert user_tokens["token_type"] == "bearer"
        assert user_tokens["expires_in"] > 0

        # 2. 验证访问令牌
        access_payload = jwt_handler.verify_access_token(user_tokens["access_token"])
        assert access_payload.user_id == "user-123"
        assert access_payload.tenant_id == "tenant-456"
        assert access_payload.permissions == ["read", "write"]

        # 3. 使用刷新令牌获取新令牌
        new_access, new_refresh = jwt_handler.refresh_access_token(
            user_tokens["refresh_token"]
        )

        # 4. 验证新的访问令牌
        new_payload = jwt_handler.verify_access_token(new_access)
        assert new_payload.user_id == "user-123"
        assert new_payload.tenant_id == "tenant-456"

    def test_multi_tenant_isolation(self, jwt_handler):
        """测试多租户隔离"""
        # 创建两个不同租户的令牌
        token_tenant_a = jwt_handler.create_access_token(
            user_id="user-123",
            tenant_id="tenant-a",
            email="user@tenant-a.com",
            permissions=["read"],
        )

        token_tenant_b = jwt_handler.create_access_token(
            user_id="user-123",
            tenant_id="tenant-b",
            email="user@tenant-b.com",
            permissions=["admin"],
        )

        # 验证令牌包含正确的租户信息
        payload_a = jwt_handler.verify_token(token_tenant_a)
        payload_b = jwt_handler.verify_token(token_tenant_b)

        assert payload_a.tenant_id == "tenant-a"
        assert payload_b.tenant_id == "tenant-b"
        assert payload_a.permissions != payload_b.permissions

    def test_token_algorithm_fallback(self, jwt_handler):
        """测试算法降级机制"""
        # 模拟RS256密钥不可用，应该回退到HS256
        with patch.object(jwt_handler.keys, "private_key", None):
            token = jwt_handler.create_access_token(
                user_id="user-123", tenant_id="tenant-456", email="test@example.com"
            )

            # 应该能够使用HS256验证
            payload = jwt_handler.verify_token(token)
            assert payload.user_id == "user-123"


class TestPerformanceBenchmarks:
    """性能基准测试"""

    @pytest.fixture
    def jwt_handler(self):
        with patch("app.core.jwt_handler.get_settings") as mock_settings:
            settings = Settings()
            settings.jwt_secret_key = "performance-test-key"
            settings.jwt_algorithm = "HS256"
            mock_settings.return_value = settings
            return JWTHandler()

    def test_token_creation_performance(self, jwt_handler):
        """测试Token创建性能"""
        import time

        # 基准测试：创建1000个Token应该在1秒内完成
        start_time = time.time()

        for i in range(1000):
            jwt_handler.create_access_token(
                user_id=f"user-{i}",
                tenant_id=f"tenant-{i % 10}",
                email=f"user{i}@test.com",
                permissions=["read"],
            )

        elapsed_time = time.time() - start_time

        # 性能要求：1000个Token创建时间 < 1秒
        assert elapsed_time < 1.0, f"Token创建性能不达标: {elapsed_time:.2f}秒"
        print(f"Token创建性能: {1000/elapsed_time:.0f} tokens/sec")

    def test_token_verification_performance(self, jwt_handler):
        """测试Token验证性能"""
        import time

        # 预创建一些token
        tokens = []
        for i in range(100):
            token = jwt_handler.create_access_token(
                user_id=f"user-{i}",
                tenant_id=f"tenant-{i % 5}",
                email=f"user{i}@test.com",
            )
            tokens.append(token)

        # 基准测试：验证1000次应该在1秒内完成
        start_time = time.time()

        for _ in range(1000):
            token = tokens[_ % len(tokens)]
            jwt_handler.verify_token(token)

        elapsed_time = time.time() - start_time

        # 性能要求：1000次验证 < 1秒
        assert elapsed_time < 1.0, f"Token验证性能不达标: {elapsed_time:.2f}秒"
        print(f"Token验证性能: {1000/elapsed_time:.0f} verifications/sec")


class TestSecurityScenarios:
    """安全测试场景"""

    def test_token_tampering_detection(self):
        """测试Token篡改检测"""
        with patch("app.core.jwt_handler.get_settings") as mock_settings:
            settings = Settings()
            settings.jwt_secret_key = "security-test-key"
            mock_settings.return_value = settings

            handler = JWTHandler()

            # 创建正常token
            token = handler.create_access_token(
                user_id="user-123",
                tenant_id="tenant-456",
                email="user@test.com",
                permissions=["read"],
            )

            # 篡改token（修改几个字符）
            tampered_token = token[:-10] + "tampered123"

            # 验证应该失败
            with pytest.raises(InvalidTokenError):
                handler.verify_token(tampered_token)

    def test_cross_tenant_token_abuse(self):
        """测试跨租户Token滥用防护"""
        with patch("app.core.jwt_handler.get_settings") as mock_settings:
            settings = Settings()
            settings.jwt_secret_key = "cross-tenant-test-key"
            mock_settings.return_value = settings

            handler = JWTHandler()

            # 创建租户A的token
            token_a = handler.create_access_token(
                user_id="user-123",
                tenant_id="tenant-a",
                email="user@tenant-a.com",
                permissions=["admin"],
            )

            # 验证token包含正确的租户信息
            payload = handler.verify_token(token_a)
            assert payload.tenant_id == "tenant-a"

            # 应用层应该验证租户ID匹配
            # （这个测试验证token本身包含正确的租户信息）

    def test_jwt_id_uniqueness(self):
        """测试JWT ID唯一性（防重放攻击）"""
        with patch("app.core.jwt_handler.get_settings") as mock_settings:
            settings = Settings()
            settings.jwt_secret_key = "jti-test-key"
            mock_settings.return_value = settings

            handler = JWTHandler()

            # 创建多个token
            tokens = []
            jtis = []

            for i in range(10):
                token = handler.create_access_token(
                    user_id=f"user-{i}",
                    tenant_id="tenant-test",
                    email=f"user{i}@test.com",
                )
                tokens.append(token)

                # 提取JTI
                payload = jwt.decode(token, options={"verify_signature": False})
                jtis.append(payload["jti"])

            # 验证所有JTI都不相同
            assert len(set(jtis)) == len(jtis), "JWT ID不唯一，存在重复"


if __name__ == "__main__":
    # 运行所有测试
    pytest.main([__file__, "-v", "--tb=short"])
