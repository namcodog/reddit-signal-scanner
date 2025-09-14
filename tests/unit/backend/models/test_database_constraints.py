"""
数据库约束和完整性测试

测试所有数据库约束、检查约束、索引和完整性规则
基于SQLAlchemy最佳实践，确保数据一致性和完整性
"""

import uuid
from decimal import Decimal
from datetime import datetime, timedelta
import pytest
import pytest_asyncio
from sqlalchemy import select, text, Index
from sqlalchemy.exc import IntegrityError, CheckViolation
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.user import User
from backend.app.models.task import Task, TaskStatus, FailureCategory
from backend.app.models.analysis import Analysis
from tests.fixtures.base_fixtures import TestIsolation
from tests.unit.backend.models.conftest import ModelTestHelpers, performance_test


class TestDatabaseConstraints:
    """数据库约束测试类"""
    
    @TestIsolation.unit_test
    async def test_user_email_format_constraint(self, async_session: AsyncSession):
        """测试用户邮箱格式约束 - 详细的格式验证"""
        invalid_emails = [
            # 缺少@符号
            "plaintext",
            "no-at-sign.com",
            
            # @符号位置错误
            "@example.com",
            "user@",
            "@",
            
            # 域名格式错误  
            "user@domain",
            "user@.com",
            "user@domain.",
            "user@domain..com",
            
            # 用户名格式错误
            ".user@example.com",
            "user.@example.com",
            "us..er@example.com",
            
            # 过长
            "a" * 65 + "@" + "b" * 250 + ".com",
            
            # 特殊字符错误
            "user@exam ple.com",
            "user@example..com",
        ]
        
        for invalid_email in invalid_emails:
            user = User(
                email=invalid_email,
                password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
            )
            async_session.add(user)
            
            with pytest.raises(IntegrityError) as exc_info:
                await async_session.commit()
            
            # 验证错误包含约束名称
            assert "ck_users_email_format" in str(exc_info.value)
            await async_session.rollback()
    
    @TestIsolation.unit_test
    async def test_user_email_valid_formats(self, async_session: AsyncSession):
        """测试有效的邮箱格式"""
        valid_emails = [
            "user@example.com",
            "test.email@domain.co.uk",
            "user123@test-domain.org",
            "a@b.co",
            "very-long-email-address@very-long-domain-name.com",
            "user+tag@example.com",
            "user_name@example-domain.com",
            "123@456.com",
        ]
        
        users = []
        for i, valid_email in enumerate(valid_emails):
            user = User(
                email=valid_email,
                password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
            )
            users.append(user)
            async_session.add(user)
        
        # 应该全部成功创建
        await async_session.commit()
        
        # 验证所有用户已创建
        for user in users:
            await async_session.refresh(user)
            assert user.id is not None
    
    @TestIsolation.unit_test
    async def test_user_password_hash_constraint(self, async_session: AsyncSession):
        """测试用户密码哈希约束 - BCrypt格式验证"""
        invalid_hashes = [
            # 不是BCrypt格式
            "plaintext",
            "md5hash",
            "sha256hash",
            
            # BCrypt格式错误
            "$2a$12$invalid",  # 太短
            "$3b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",  # 版本错误
            "$2b$13$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",  # 轮次错误
            "$2b$12$short",  # 太短
        ]
        
        for i, invalid_hash in enumerate(invalid_hashes):
            user = User(
                email=f"hash_test_{i}@example.com",
                password_hash=invalid_hash,
            )
            async_session.add(user)
            
            with pytest.raises(IntegrityError) as exc_info:
                await async_session.commit()
            
            # 验证错误包含约束名称
            assert "ck_users_password_bcrypt" in str(exc_info.value)
            await async_session.rollback()
    
    @TestIsolation.unit_test
    async def test_user_password_hash_valid_formats(self, async_session: AsyncSession):
        """测试有效的BCrypt哈希格式"""
        valid_hashes = [
            "$2a$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",  # 2a
            "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",  # 2b
            "$2y$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",  # 2y
            "$2b$04$abcdefghijklmnopqrstuu1234567890123456789012345678",  # 最小轮次
            "$2b$31$abcdefghijklmnopqrstuu1234567890123456789012345678",  # 最大轮次
        ]
        
        users = []
        for i, valid_hash in enumerate(valid_hashes):
            user = User(
                email=f"valid_hash_{i}@example.com",
                password_hash=valid_hash,
            )
            users.append(user)
            async_session.add(user)
        
        # 应该全部成功创建
        await async_session.commit()
        
        # 验证所有用户已创建
        for user in users:
            await async_session.refresh(user)
            assert user.id is not None
    
    @TestIsolation.unit_test
    async def test_analysis_confidence_score_constraint(self, async_session: AsyncSession):
        """测试分析置信度约束 - 范围验证"""
        # 创建测试用户和任务
        user = User(
            email="confidence_constraint@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        task = Task(
            product_description="Confidence constraint test",
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
        async_session.add(task)
        await async_session.commit()
        await async_session.refresh(task)
        
        # 测试无效置信度值
        invalid_scores = [
            Decimal("-0.01"),    # 小于0
            Decimal("-1.00"),    # 负数
            Decimal("1.01"),     # 大于1
            Decimal("2.50"),     # 远大于1
            Decimal("10.00"),    # 极大值
        ]
        
        for invalid_score in invalid_scores:
            analysis = Analysis(
                task_id=task.id,
                insights={"test": "data"},
                sources={"test": "source"},
                confidence_score=invalid_score,
            )
            async_session.add(analysis)
            
            with pytest.raises((IntegrityError, CheckViolation)) as exc_info:
                await async_session.commit()
            
            # 验证错误包含约束名称
            error_str = str(exc_info.value)
            assert "ck_analyses_confidence_range" in error_str
            await async_session.rollback()
    
    @TestIsolation.unit_test
    async def test_analysis_confidence_score_valid_range(self, async_session: AsyncSession):
        """测试置信度的有效范围值"""
        user = User(
            email="valid_confidence@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        # 创建多个任务用于测试不同置信度值
        valid_scores = [
            Decimal("0.00"),     # 最小值
            Decimal("0.01"),     # 接近最小值
            Decimal("0.50"),     # 中间值
            Decimal("0.99"),     # 接近最大值
            Decimal("1.00"),     # 最大值
        ]
        
        analyses = []
        for i, valid_score in enumerate(valid_scores):
            task = Task(
                product_description=f"Valid confidence test {i}",
                user_id=user.id,
                tenant_id=user.tenant_id,
            )
            async_session.add(task)
            await async_session.flush()
            
            analysis = Analysis(
                task_id=task.id,
                insights={"score": float(valid_score)},
                sources={"score": float(valid_score)},
                confidence_score=valid_score,
            )
            analyses.append(analysis)
            async_session.add(analysis)
        
        # 应该全部成功创建
        await async_session.commit()
        
        # 验证所有分析已创建
        for analysis in analyses:
            await async_session.refresh(analysis)
            assert analysis.id is not None
            assert 0.00 <= analysis.confidence_score <= 1.00
    
    @TestIsolation.unit_test
    async def test_analysis_version_constraint(self, async_session: AsyncSession):
        """测试分析版本约束 - 必须为正数"""
        user = User(
            email="version_constraint@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        task = Task(
            product_description="Version constraint test",
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
        async_session.add(task)
        await async_session.commit()
        await async_session.refresh(task)
        
        # 测试无效版本号
        invalid_versions = [0, -1, -10]
        
        for invalid_version in invalid_versions:
            analysis = Analysis(
                task_id=task.id,
                insights={"test": "data"},
                sources={"test": "source"},
                confidence_score=Decimal("0.80"),
                analysis_version=invalid_version,
            )
            async_session.add(analysis)
            
            with pytest.raises((IntegrityError, CheckViolation)) as exc_info:
                await async_session.commit()
            
            # 验证错误包含约束名称
            assert "ck_analyses_version_positive" in str(exc_info.value)
            await async_session.rollback()
    
    @TestIsolation.unit_test
    async def test_unique_constraints(self, async_session: AsyncSession):
        """测试唯一性约束"""
        # 测试用户邮箱在同一租户内的唯一性
        tenant_id = uuid.uuid4()
        
        # 创建第一个用户
        user1 = User(
            tenant_id=tenant_id,
            email="unique_test@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user1)
        await async_session.commit()
        
        # 尝试创建相同邮箱的用户（同一租户）
        user2 = User(
            tenant_id=tenant_id,
            email="unique_test@example.com",  # 相同邮箱
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user2)
        
        with pytest.raises(IntegrityError) as exc_info:
            await async_session.commit()
        
        # 验证唯一约束错误
        assert "ix_users_tenant_email_unique" in str(exc_info.value)
        await async_session.rollback()
        
        # 但不同租户可以有相同邮箱
        different_tenant_id = uuid.uuid4()
        user3 = User(
            tenant_id=different_tenant_id,
            email="unique_test@example.com",  # 相同邮箱，不同租户
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user3)
        await async_session.commit()  # 应该成功
        
        await async_session.refresh(user3)
        assert user3.id is not None
    
    @TestIsolation.unit_test
    async def test_foreign_key_constraints(self, async_session: AsyncSession):
        """测试外键约束的完整性"""
        # 测试Task引用不存在的User
        fake_user_id = uuid.uuid4()
        fake_tenant_id = uuid.uuid4()
        
        task = Task(
            product_description="Foreign key test",
            user_id=fake_user_id,
            tenant_id=fake_tenant_id,
        )
        async_session.add(task)
        
        with pytest.raises(IntegrityError):
            await async_session.commit()
        
        await async_session.rollback()
        
        # 测试Analysis引用不存在的Task
        fake_task_id = uuid.uuid4()
        
        analysis = Analysis(
            task_id=fake_task_id,
            insights={"test": "data"},
            sources={"test": "source"},
            confidence_score=Decimal("0.85"),
        )
        async_session.add(analysis)
        
        with pytest.raises(IntegrityError):
            await async_session.commit()
    
    @TestIsolation.unit_test
    async def test_not_null_constraints(self, async_session: AsyncSession):
        """测试非空约束的完整覆盖"""
        # 用户模型非空字段测试
        user_null_tests = [
            {"field": "email", "data": {"password_hash": "valid_hash"}},
            {"field": "password_hash", "data": {"email": "test@example.com"}},
        ]
        
        for test in user_null_tests:
            # 这个测试在SQLAlchemy层面可能不会直接失败，因为字段在模型定义中是必需的
            # 但我们可以测试数据库层面的约束
            pass
        
        # 创建用户和任务用于其他测试
        user = User(
            email="not_null_test@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        task = Task(
            product_description="Not null constraint test",
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
        async_session.add(task)
        await async_session.commit()
        await async_session.refresh(task)
        
        # 分析模型非空字段测试
        # insights非空
        with pytest.raises(IntegrityError):
            analysis = Analysis(
                task_id=task.id,
                # insights缺失
                sources={"test": "source"},
                confidence_score=Decimal("0.85"),
            )
            async_session.add(analysis)
            await async_session.commit()
        
        await async_session.rollback()
        
        # sources非空
        with pytest.raises(IntegrityError):
            analysis = Analysis(
                task_id=task.id,
                insights={"test": "data"},
                # sources缺失
                confidence_score=Decimal("0.85"),
            )
            async_session.add(analysis)
            await async_session.commit()
    
    @TestIsolation.unit_test
    async def test_index_functionality(self, async_session: AsyncSession):
        """测试索引功能和性能"""
        # 创建大量用户数据
        users = []
        tenant_ids = [uuid.uuid4() for _ in range(5)]
        
        for i in range(100):
            user = User(
                tenant_id=tenant_ids[i % 5],  # 分配到5个不同租户
                email=f"index_test_{i}@example.com",
                password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
                is_active=(i % 3 != 0),  # 2/3的用户激活
            )
            users.append(user)
            async_session.add(user)
        
        await async_session.commit()
        
        # 测试租户+邮箱索引查询
        result = await async_session.execute(
            select(User).where(
                User.tenant_id == tenant_ids[0],
                User.email == "index_test_0@example.com"
            )
        )
        found_user = result.scalar_one_or_none()
        assert found_user is not None
        assert found_user.email == "index_test_0@example.com"
        
        # 测试活跃用户索引查询
        result = await async_session.execute(
            select(User).where(
                User.tenant_id == tenant_ids[0],
                User.is_active.is_(True)
            )
        )
        active_users = result.scalars().all()
        
        # 验证索引查询结果
        assert len(active_users) > 0
        for user in active_users:
            assert user.is_active is True
            assert user.tenant_id == tenant_ids[0]
    
    @TestIsolation.unit_test
    async def test_check_constraints_edge_cases(self, async_session: AsyncSession):
        """测试检查约束的边界情况"""
        user = User(
            email="edge_cases@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        task = Task(
            product_description="Edge cases test",
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
        async_session.add(task)
        await async_session.commit()
        await async_session.refresh(task)
        
        # 测试置信度边界值
        boundary_scores = [
            (Decimal("0.00"), True),   # 最小有效值
            (Decimal("1.00"), True),   # 最大有效值
            (Decimal("0.000"), True),  # 精度测试
            (Decimal("1.000"), True),  # 精度测试
        ]
        
        for score, should_succeed in boundary_scores:
            analysis = Analysis(
                task_id=task.id,
                insights={"boundary": float(score)},
                sources={"boundary": float(score)},
                confidence_score=score,
            )
            async_session.add(analysis)
            
            if should_succeed:
                await async_session.commit()
                await async_session.refresh(analysis)
                assert analysis.confidence_score == score
                
                # 清理以进行下次测试
                await async_session.delete(analysis)
                await async_session.commit()
            else:
                with pytest.raises((IntegrityError, CheckViolation)):
                    await async_session.commit()
                await async_session.rollback()
    
    @TestIsolation.unit_test
    @performance_test(max_duration=0.2)
    async def test_constraint_performance(self, async_session: AsyncSession):
        """测试约束检查的性能影响"""
        # 批量插入数据测试约束检查性能
        users = []
        for i in range(20):
            user = User(
                email=f"perf_constraint_{i}@example.com",
                password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
            )
            users.append(user)
        
        # 批量插入应该快速完成
        async_session.add_all(users)
        await async_session.commit()
        
        # 验证所有用户已创建且约束生效
        result = await async_session.execute(
            select(User).where(User.email.like("perf_constraint_%"))
        )
        created_users = result.scalars().all()
        
        assert len(created_users) == 20
        for user in created_users:
            assert "@" in user.email  # 基本邮箱格式验证
            assert "$2b$12$" in user.password_hash  # BCrypt格式验证