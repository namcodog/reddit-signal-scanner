"""
Reddit Signal Scanner - 认证服务单元测试

基于Linus原则和质量门禁Agent要求：
- 边界条件优先测试策略
- 完整的异常路径覆盖
- 性能基准和统计学验证
- 多租户隔离验证
"""

import pytest
import uuid
from typing import Dict, Any
from unittest.mock import patch, Mock
from sqlalchemy.exc import IntegrityError

from app.services.auth_service import AuthService, auth_service
from app.schemas.auth import UserRegisterRequest, UserRegisterResponse
from app.models.user import User
from ..conftest import DatabaseTestFactory, assert_constraint_violation


class TestAuthService:
    """认证服务核心功能测试"""

    @pytest.fixture
    def auth_svc(self):
        """认证服务实例"""
        return AuthService()

    @pytest.fixture
    def valid_registration_data(self) -> UserRegisterRequest:
        """标准有效注册数据"""
        return UserRegisterRequest(
            email="john.doe@example.com",
            password="MySecurePassword123!",
            confirm_password="MySecurePassword123!",
        )

    @pytest.fixture
    def edge_case_registration_data(self) -> Dict[str, UserRegisterRequest]:
        """边界条件注册数据"""
        return {
            # 邮箱长度边界 (RFC 5321 - 320字符)
            "max_email_length": UserRegisterRequest(
                email="x" * 64 + "@" + "y" * 251 + ".com",  # 320字符
                password="EdgeCasePassword123!",
                confirm_password="EdgeCasePassword123!",
            ),
            # 最短有效邮箱
            "min_email_length": UserRegisterRequest(
                email="a@b.co",  # 5字符
                password="MinPassword123!",
                confirm_password="MinPassword123!",
            ),
            # 密码长度边界
            "min_password_length": UserRegisterRequest(
                email="min.pass@example.com",
                password="Aa1!5678",  # 刚好8字符
                confirm_password="Aa1!5678",
            ),
            # 复杂邮箱格式
            "complex_email": UserRegisterRequest(
                email="test.email+tag123@sub.domain-name.com",
                password="ComplexEmail123!",
                confirm_password="ComplexEmail123!",
            ),
        }

    # ============================================================================
    # 1. 用户注册核心功能测试
    # ============================================================================

    @pytest.mark.asyncio
    async def test_register_user_success_standard(
        self, auth_svc, valid_registration_data, db_session
    ):
        """标准用户注册成功流程"""
        # 执行注册
        response = await auth_svc.register_user(valid_registration_data, db_session)

        # 验证响应结构
        assert isinstance(response, UserRegisterResponse)
        assert response.email == valid_registration_data.email
        assert response.is_active is True
        assert response.email_verified is False
        assert response.token_type == "bearer"
        assert response.expires_in == 3600

        # 验证UUID格式
        assert isinstance(response.user_id, uuid.UUID)
        assert isinstance(response.tenant_id, uuid.UUID)

        # 验证JWT tokens非空
        assert response.access_token is not None
        assert response.refresh_token is not None
        assert len(response.access_token) > 50  # JWT通常很长
        assert len(response.refresh_token) > 50

        # 验证时间戳格式
        assert "T" in response.created_at  # ISO格式
        assert response.created_at.endswith("Z") or "+" in response.created_at

    @pytest.mark.asyncio
    async def test_register_user_edge_cases_success(
        self, auth_svc, edge_case_registration_data, db_session
    ):
        """边界条件注册成功"""
        for case_name, registration_data in edge_case_registration_data.items():
            # 清理之前的测试数据以避免冲突
            await db_session.rollback()

            # 执行注册
            response = await auth_svc.register_user(registration_data, db_session)

            # 验证成功
            assert response.email == registration_data.email, f"失败案例: {case_name}"
            assert response.is_active is True, f"失败案例: {case_name}"

            # 验证多租户：每个用户都有唯一的tenant_id
            assert isinstance(response.tenant_id, uuid.UUID), f"失败案例: {case_name}"

    @pytest.mark.asyncio
    async def test_register_user_duplicate_email_error(
        self, auth_svc, valid_registration_data, db_session
    ):
        """重复邮箱注册错误处理"""
        # 第一次注册成功
        await auth_svc.register_user(valid_registration_data, db_session)

        # 第二次注册相同邮箱应该失败
        with pytest.raises(ValueError) as exc_info:
            await auth_svc.register_user(valid_registration_data, db_session)

        assert "已被注册" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_register_user_database_constraint_errors(self, auth_svc, db_session):
        """数据库约束错误处理"""
        # 测试无效邮箱格式 (应该被Pydantic拦截，但我们测试数据库层)
        invalid_data = UserRegisterRequest(
            email="invalid.email",  # 故意无效格式，但会被Pydantic验证
            password="ValidPassword123!",
            confirm_password="ValidPassword123!",
        )

        # 由于Pydantic会在服务层之前验证，我们直接测试数据库层
        with patch.object(auth_svc, "_hash_password", return_value="$2b$12$validhash"):
            # 模拟绕过Pydantic的情况
            invalid_user = User(
                email="invalid-email-format",  # 无效格式
                password_hash="$2b$12$validhash",
            )

            db_session.add(invalid_user)

            with pytest.raises(IntegrityError) as exc_info:
                await db_session.commit()

            # 验证约束错误
            assert "ck_users_email_format" in str(exc_info.value)

    # ============================================================================
    # 2. 密码处理功能测试
    # ============================================================================

    def test_hash_password_bcrypt_format(self, auth_svc):
        """BCrypt密码哈希格式验证"""
        test_passwords = [
            "SimplePassword123!",
            "ComplexP@ssw0rd!@#$%^&*()",
            "中文密码123!",  # 支持Unicode
            "A1!" + "x" * 125,  # 接近最大长度
        ]

        for password in test_passwords:
            hashed = auth_svc._hash_password(password)

            # 验证BCrypt格式: $2b$rounds$salt+hash
            assert hashed.startswith("$2b$"), f"密码: {password[:10]}..."
            assert len(hashed) == 60, f"密码: {password[:10]}..."  # BCrypt固定长度

            # 验证哈希可验证
            assert auth_svc._verify_password(
                password, hashed
            ), f"密码: {password[:10]}..."

    def test_verify_password_security(self, auth_svc):
        """密码验证安全性测试"""
        original_password = "CorrectPassword123!"
        hashed = auth_svc._hash_password(original_password)

        # 正确密码验证成功
        assert auth_svc._verify_password(original_password, hashed)

        # 错误密码验证失败
        wrong_passwords = [
            "WrongPassword123!",
            "correctpassword123!",  # 大小写敏感
            original_password + " ",  # 尾随空格
            " " + original_password,  # 前导空格
            original_password[:-1],  # 缺少最后一个字符
            "",  # 空密码
        ]

        for wrong_pass in wrong_passwords:
            assert not auth_svc._verify_password(
                wrong_pass, hashed
            ), f"错误密码应该失败: {wrong_pass}"

    def test_password_strength_validation_comprehensive(self, auth_svc):
        """密码强度验证全面测试"""
        # 强密码 - 应该通过
        strong_passwords = [
            "StrongPassword123!",
            "MyS3cur3P@ssw0rd",
            "P@ssW0rd!2023",
            "Aa1!5678",  # 最短有效强密码
        ]

        for password in strong_passwords:
            is_valid, errors = auth_svc.validate_password_strength(password)
            assert is_valid, f"强密码应该通过: {password}, 错误: {errors}"
            assert len(errors) == 0, f"强密码不应有错误: {password}, 错误: {errors}"

        # 弱密码 - 应该失败
        weak_passwords_and_expected_errors = [
            ("short1!", ["密码长度至少8个字符"]),
            ("nouppercase123!", ["密码必须包含至少一个大写字母"]),
            ("NOLOWERCASE123!", ["密码必须包含至少一个小写字母"]),
            ("NoNumbers!", ["密码必须包含至少一个数字"]),
            ("NoSpecialChar123", ["密码必须包含至少一个特殊字符"]),
            ("Password123456", ["密码不能包含常见弱密码模式"]),  # 包含123456
            ("password123!", ["密码不能包含常见弱密码模式"]),  # 包含password
        ]

        for password, expected_error_keywords in weak_passwords_and_expected_errors:
            is_valid, errors = auth_svc.validate_password_strength(password)
            assert not is_valid, f"弱密码应该失败: {password}"
            assert len(errors) > 0, f"弱密码应该有错误: {password}"

            # 验证包含预期的错误信息
            error_text = " ".join(errors)
            for keyword in expected_error_keywords:
                assert (
                    keyword in error_text
                ), f"密码 {password} 应该包含错误: {keyword}, 实际错误: {errors}"

    # ============================================================================
    # 3. 用户查询功能测试
    # ============================================================================

    @pytest.mark.asyncio
    async def test_get_user_by_email_success(
        self, auth_svc, valid_registration_data, db_session
    ):
        """根据邮箱查询用户成功"""
        # 注册用户
        reg_response = await auth_svc.register_user(valid_registration_data, db_session)

        # 查询用户
        user = await auth_svc.get_user_by_email(
            valid_registration_data.email, db_session
        )

        # 验证结果
        assert user is not None
        assert user.email == valid_registration_data.email
        assert user.id == reg_response.user_id
        assert user.tenant_id == reg_response.tenant_id
        assert user.is_active is True

    @pytest.mark.asyncio
    async def test_get_user_by_email_not_found(self, auth_svc, db_session):
        """查询不存在的邮箱"""
        user = await auth_svc.get_user_by_email("nonexistent@example.com", db_session)
        assert user is None

    @pytest.mark.asyncio
    async def test_get_user_by_email_case_insensitive(
        self, auth_svc, valid_registration_data, db_session
    ):
        """邮箱查询大小写不敏感"""
        # 注册用户
        await auth_svc.register_user(valid_registration_data, db_session)

        # 不同大小写查询应该都能找到
        email_variants = [
            valid_registration_data.email.upper(),
            valid_registration_data.email.lower(),
            valid_registration_data.email.title(),
        ]

        for email_variant in email_variants:
            user = await auth_svc.get_user_by_email(email_variant, db_session)
            assert user is not None, f"邮箱变体应该能找到用户: {email_variant}"
            assert user.email == valid_registration_data.email.lower()

    @pytest.mark.asyncio
    async def test_get_user_by_id_success(
        self, auth_svc, valid_registration_data, db_session
    ):
        """根据ID查询用户成功"""
        # 注册用户
        reg_response = await auth_svc.register_user(valid_registration_data, db_session)

        # 查询用户
        user = await auth_svc.get_user_by_id(reg_response.user_id, db_session)

        # 验证结果
        assert user is not None
        assert user.id == reg_response.user_id
        assert user.email == valid_registration_data.email

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, auth_svc, db_session):
        """查询不存在的用户ID"""
        random_uuid = uuid.uuid4()
        user = await auth_svc.get_user_by_id(random_uuid, db_session)
        assert user is None

    # ============================================================================
    # 4. 用户认证功能测试（预留给登录功能）
    # ============================================================================

    @pytest.mark.asyncio
    async def test_authenticate_user_success(
        self, auth_svc, valid_registration_data, db_session
    ):
        """用户认证成功（预留给登录功能）"""
        # 注册用户
        await auth_svc.register_user(valid_registration_data, db_session)

        # 认证用户
        user = await auth_svc.authenticate_user(
            valid_registration_data.email, valid_registration_data.password, db_session
        )

        # 验证认证成功
        assert user is not None
        assert user.email == valid_registration_data.email
        assert user.is_active is True

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(
        self, auth_svc, valid_registration_data, db_session
    ):
        """认证错误密码失败"""
        # 注册用户
        await auth_svc.register_user(valid_registration_data, db_session)

        # 错误密码认证
        user = await auth_svc.authenticate_user(
            valid_registration_data.email, "WrongPassword123!", db_session
        )

        # 验证认证失败
        assert user is None

    @pytest.mark.asyncio
    async def test_authenticate_user_nonexistent_email(self, auth_svc, db_session):
        """认证不存在的邮箱失败"""
        user = await auth_svc.authenticate_user(
            "nonexistent@example.com", "AnyPassword123!", db_session
        )
        assert user is None

    # ============================================================================
    # 5. 多租户隔离测试
    # ============================================================================

    @pytest.mark.asyncio
    async def test_multi_tenant_email_isolation(self, auth_svc, db_session):
        """多租户邮箱隔离 - 不同租户可以使用相同邮箱"""
        # 注意：当前实现个人用户都生成唯一tenant_id，
        # 所以同邮箱会被唯一约束阻止，这是正确的行为

        email = "same@example.com"
        password = "SamePassword123!"

        # 第一个用户注册成功
        first_registration = UserRegisterRequest(
            email=email, password=password, confirm_password=password
        )
        first_response = await auth_svc.register_user(first_registration, db_session)

        # 第二个用户使用相同邮箱注册应该失败（因为约束是tenant+email唯一）
        second_registration = UserRegisterRequest(
            email=email, password=password, confirm_password=password
        )

        with pytest.raises(ValueError) as exc_info:
            await auth_svc.register_user(second_registration, db_session)

        assert "已被注册" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_tenant_id_generation_uniqueness(self, auth_svc, db_session):
        """租户ID生成唯一性验证"""
        tenant_ids = set()

        # 创建多个用户，验证tenant_id都不同
        for i in range(10):
            registration_data = UserRegisterRequest(
                email=f"user{i}@example.com",
                password="TestPassword123!",
                confirm_password="TestPassword123!",
            )

            response = await auth_svc.register_user(registration_data, db_session)

            # 验证tenant_id唯一性
            assert (
                response.tenant_id not in tenant_ids
            ), f"Tenant ID重复: {response.tenant_id}"
            tenant_ids.add(response.tenant_id)

    # ============================================================================
    # 6. 错误处理和异常情况测试
    # ============================================================================

    @pytest.mark.asyncio
    async def test_register_user_jwt_generation_failure(
        self, auth_svc, valid_registration_data, db_session
    ):
        """JWT生成失败的错误处理"""
        # Mock JWT handler失败
        with patch.object(
            auth_svc.jwt_handler,
            "create_access_token",
            side_effect=Exception("JWT generation failed"),
        ):
            with pytest.raises(Exception) as exc_info:
                await auth_svc.register_user(valid_registration_data, db_session)

            assert "JWT generation failed" in str(exc_info.value)

            # 验证数据库已回滚（用户未创建）
            user = await auth_svc.get_user_by_email(
                valid_registration_data.email, db_session
            )
            assert user is None, "JWT失败时用户不应该被创建"

    @pytest.mark.asyncio
    async def test_database_session_exception_handling(
        self, auth_svc, valid_registration_data, db_session
    ):
        """数据库会话异常处理"""
        # Mock数据库操作失败
        with patch.object(
            db_session, "commit", side_effect=Exception("Database error")
        ):
            with pytest.raises(Exception) as exc_info:
                await auth_svc.register_user(valid_registration_data, db_session)

            assert "Database error" in str(exc_info.value)

    def test_verify_password_exception_handling(self, auth_svc):
        """密码验证异常处理"""
        # 测试异常输入
        assert not auth_svc._verify_password("test", "invalid_hash")
        assert not auth_svc._verify_password("test", None)
        assert not auth_svc._verify_password("test", "")

        # 测试Unicode处理
        unicode_password = "测试密码123!"
        hashed = auth_svc._hash_password(unicode_password)
        assert auth_svc._verify_password(unicode_password, hashed)

    # ============================================================================
    # 7. 性能基准测试
    # ============================================================================

    def test_password_hashing_performance(self, auth_svc, performance_timer):
        """密码哈希性能基准测试"""
        test_password = "PerformanceTestPassword123!"

        # 测量密码哈希性能
        performance_timer.measure_operation(
            lambda: auth_svc._hash_password(test_password),
            iterations=50,  # BCrypt计算成本高，减少迭代次数
        )

        stats = performance_timer.get_stats()

        # BCrypt哈希应该在合理时间内完成（< 500ms）
        # 这是安全性和用户体验的平衡
        assert stats["mean"] < 500, f"密码哈希平均时间过长: {stats}"
        assert stats["max"] < 1000, f"密码哈希最大时间过长: {stats}"

    def test_password_verification_performance(self, auth_svc, performance_timer):
        """密码验证性能基准测试"""
        test_password = "PerformanceTestPassword123!"
        hashed = auth_svc._hash_password(test_password)

        # 测量密码验证性能
        performance_timer.measure_operation(
            lambda: auth_svc._verify_password(test_password, hashed), iterations=100
        )

        stats = performance_timer.get_stats()

        # 密码验证应该快于哈希（< 100ms）
        assert stats["mean"] < 100, f"密码验证平均时间过长: {stats}"
        assert stats["p95"] < 200, f"密码验证P95时间过长: {stats}"


class TestAuthServiceUtils:
    """认证服务工具函数测试"""

    def test_email_format_validation_comprehensive(self):
        """邮箱格式验证全面测试"""
        from app.services.auth_service import auth_service

        # 有效邮箱格式
        valid_emails = [
            "test@example.com",
            "user.name@domain.co.uk",
            "user+tag@example.org",
            "user_name@sub.domain.com",
            "123@numbers.com",
            "a@b.co",  # 最短有效邮箱
            "x" * 64 + "@" + "y" * 250 + ".com",  # 接近最长有效邮箱
        ]

        for email in valid_emails:
            is_valid, error_msg = auth_service.validate_email_format(email)
            assert is_valid, f"有效邮箱应该通过验证: {email}, 错误: {error_msg}"
            assert error_msg == "", f"有效邮箱不应该有错误: {email}, 错误: {error_msg}"

        # 无效邮箱格式
        invalid_emails = [
            "invalid-email",
            "@domain.com",
            "user@",
            "user@domain",
            "user..name@domain.com",
            ".user@domain.com",
            "user.@domain.com",
            "",
            "user@",
            "user@@domain.com",
            "user@domain..com",
        ]

        for email in invalid_emails:
            is_valid, error_msg = auth_service.validate_email_format(email)
            assert not is_valid, f"无效邮箱应该验证失败: {email}"
            assert "无效" in error_msg, f"无效邮箱应该有错误信息: {email}, 错误: {error_msg}"


class TestAuthServiceIntegration:
    """认证服务集成测试"""

    @pytest.mark.asyncio
    async def test_complete_user_registration_flow(self, db_session, test_data_factory):
        """完整用户注册流程集成测试"""
        # 创建注册数据
        registration_data = UserRegisterRequest(
            email="integration@example.com",
            password="IntegrationTest123!",
            confirm_password="IntegrationTest123!",
        )

        # 执行完整注册流程
        response = await auth_service.register_user(registration_data, db_session)

        # 验证用户已在数据库中创建
        user = await auth_service.get_user_by_email(registration_data.email, db_session)
        assert user is not None
        assert user.id == response.user_id
        assert user.tenant_id == response.tenant_id
        assert user.email == registration_data.email.lower()
        assert user.is_active is True
        assert user.email_verified is False

        # 验证密码哈希正确
        assert auth_service._verify_password(
            registration_data.password, user.password_hash
        )

        # 验证JWT tokens有效
        jwt_handler = auth_service.jwt_handler
        access_payload = jwt_handler.verify_access_token(response.access_token)
        refresh_payload = jwt_handler.verify_refresh_token(response.refresh_token)

        assert access_payload is not None
        assert refresh_payload is not None
        assert access_payload["user_id"] == str(user.id)
        assert access_payload["tenant_id"] == str(user.tenant_id)
        assert access_payload["email"] == user.email

    @pytest.mark.asyncio
    async def test_registration_followed_by_authentication(self, db_session):
        """注册后认证流程测试"""
        # 注册用户
        registration_data = UserRegisterRequest(
            email="auth.flow@example.com",
            password="AuthFlowTest123!",
            confirm_password="AuthFlowTest123!",
        )

        reg_response = await auth_service.register_user(registration_data, db_session)

        # 使用相同凭证认证
        auth_user = await auth_service.authenticate_user(
            registration_data.email, registration_data.password, db_session
        )

        # 验证认证成功
        assert auth_user is not None
        assert auth_user.id == reg_response.user_id
        assert auth_user.email == registration_data.email.lower()

        # 验证错误密码认证失败
        auth_user_wrong = await auth_service.authenticate_user(
            registration_data.email, "WrongPassword123!", db_session
        )
        assert auth_user_wrong is None
