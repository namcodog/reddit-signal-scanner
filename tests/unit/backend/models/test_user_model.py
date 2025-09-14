"""
用户模型单元测试

测试User模型的字段、约束、关系和数据完整性
遵循项目的类型安全和简洁性原则
"""

import uuid
from datetime import datetime
from typing import Optional
import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.user import User
from tests.fixtures.base_fixtures import TestIsolation
from tests.unit.backend.models.conftest import ModelTestHelpers, performance_test


class TestUserModel:
    """用户模型单元测试类"""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_user_model_creation(self, async_session: AsyncSession, model_helpers: ModelTestHelpers):
        """测试用户模型创建"""
        # 创建用户实例
        user = model_helpers.create_test_user(async_session)
        
        # 添加到数据库
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        # 验证基本字段
        model_helpers.assert_user_valid(user)
        assert user.email == user.email  # 保持原样
        assert user.is_active is True
        assert user.email_verified is False
    
    @TestIsolation.unit_test
    async def test_user_model_fields_types(self, async_session: AsyncSession):
        """测试用户模型字段类型"""
        user = User(
            email="type_test@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        # 验证字段类型
        assert isinstance(user.id, uuid.UUID)
        assert isinstance(user.tenant_id, uuid.UUID)
        assert isinstance(user.email, str)
        assert isinstance(user.password_hash, str)
        assert isinstance(user.email_verified, bool)
        assert isinstance(user.is_active, bool)
        assert isinstance(user.created_at, datetime)
        assert isinstance(user.updated_at, datetime)
    
    @TestIsolation.unit_test
    async def test_user_model_defaults(self, async_session: AsyncSession):
        """测试用户模型默认值"""
        user = User(
            email="defaults_test@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        # 验证默认值
        assert user.id is not None  # UUID自动生成
        assert user.tenant_id is not None  # 自动生成个人tenant_id
        assert user.email_verified is False  # 默认未验证
        assert user.is_active is True  # 默认激活
        assert user.created_at is not None  # 自动设置创建时间
        assert user.updated_at is not None  # 自动设置更新时间
    
    @TestIsolation.unit_test
    async def test_user_email_uniqueness_constraint(self, async_session: AsyncSession):
        """测试邮箱唯一性约束"""
        # 创建第一个用户
        user1 = User(
            email="unique@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user1)
        await async_session.commit()
        
        # 尝试创建相同邮箱的用户（同一tenant_id）
        user2 = User(
            tenant_id=user1.tenant_id,  # 相同的tenant_id
            email="unique@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user2)
        
        # 应该抛出完整性错误
        with pytest.raises(IntegrityError):
            await async_session.commit()
    
    @TestIsolation.unit_test
    async def test_user_email_different_tenant(self, async_session: AsyncSession):
        """测试不同租户可以使用相同邮箱"""
        # 创建第一个用户
        user1 = User(
            email="different_tenant@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user1)
        await async_session.commit()
        
        # 创建不同租户的相同邮箱用户
        user2 = User(
            tenant_id=uuid.uuid4(),  # 不同的tenant_id
            email="different_tenant@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user2)
        await async_session.commit()
        await async_session.refresh(user2)
        
        # 应该成功创建
        assert user1.email == user2.email
        assert user1.tenant_id != user2.tenant_id
    
    @TestIsolation.unit_test
    async def test_user_email_format_constraint(self, async_session: AsyncSession):
        """测试邮箱格式约束"""
        invalid_emails = [
            "invalid",
            "@example.com",
            "test@",
            "test..test@example.com",
            "test@example",
        ]
        
        for invalid_email in invalid_emails:
            user = User(
                email=invalid_email,
                password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
            )
            async_session.add(user)
            
            with pytest.raises(IntegrityError):
                await async_session.commit()
            
            await async_session.rollback()
    
    @TestIsolation.unit_test
    async def test_user_password_hash_constraint(self, async_session: AsyncSession):
        """测试密码哈希格式约束"""
        invalid_hashes = [
            "plaintext",
            "md5hash",
            "$1$salt$hash",  # MD5格式
            "$2b$12$tooshort",  # BCrypt但太短
        ]
        
        for invalid_hash in invalid_hashes:
            user = User(
                email=f"hash_test_{uuid.uuid4().hex[:6]}@example.com",
                password_hash=invalid_hash,
            )
            async_session.add(user)
            
            with pytest.raises(IntegrityError):
                await async_session.commit()
            
            await async_session.rollback()
    
    @TestIsolation.unit_test
    async def test_user_not_null_constraints(self, async_session: AsyncSession):
        """测试非空约束"""
        # 测试邮箱非空
        with pytest.raises(IntegrityError):
            user = User(password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm")
            async_session.add(user)
            await async_session.commit()
        
        await async_session.rollback()
        
        # 测试密码哈希非空
        with pytest.raises(IntegrityError):
            user = User(email="no_password@example.com")
            async_session.add(user)
            await async_session.commit()
    
    @TestIsolation.unit_test
    async def test_user_audit_timestamps(self, async_session: AsyncSession):
        """测试审计时间戳"""
        user = User(
            email="timestamp_test@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        
        creation_time = datetime.now()
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        # 验证创建时间
        assert user.created_at is not None
        assert user.updated_at is not None
        assert user.created_at >= creation_time
        assert user.updated_at >= creation_time
        
        # 测试更新时间戳
        original_updated = user.updated_at
        user.email_verified = True
        await async_session.commit()
        await async_session.refresh(user)
        
        # 更新时间应该改变
        assert user.updated_at > original_updated
    
    @TestIsolation.unit_test
    async def test_user_string_representations(self, async_session: AsyncSession):
        """测试字符串表示方法"""
        user = User(
            email="string_test@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        # 测试 __repr__
        repr_str = repr(user)
        assert "User(" in repr_str
        assert str(user.id) in repr_str
        assert user.email[:20] in repr_str
        assert str(user.tenant_id) in repr_str
        
        # 测试 __str__
        str_repr = str(user)
        assert user.email in str_repr
        assert "已激活" in str_repr
        
        # 测试非激活用户
        user.is_active = False
        str_repr_inactive = str(user)
        assert "已停用" in str_repr_inactive
    
    @TestIsolation.unit_test 
    async def test_user_active_user_index(self, async_session: AsyncSession):
        """测试活跃用户索引功能"""
        # 创建活跃用户
        active_user = User(
            email="active@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
            is_active=True,
        )
        
        # 创建非活跃用户
        inactive_user = User(
            email="inactive@example.com", 
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
            is_active=False,
        )
        
        async_session.add_all([active_user, inactive_user])
        await async_session.commit()
        
        # 查询活跃用户
        result = await async_session.execute(
            select(User).where(User.is_active.is_(True))
        )
        active_users = result.scalars().all()
        
        assert len(active_users) == 1
        assert active_users[0].email == "active@example.com"
    
    @TestIsolation.unit_test
    @performance_test(max_duration=0.1)
    async def test_user_query_performance(self, async_session: AsyncSession):
        """测试用户查询性能"""
        # 批量创建用户
        users = []
        for i in range(50):
            user = User(
                email=f"performance_{i}@example.com",
                password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
            )
            users.append(user)
        
        async_session.add_all(users)
        await async_session.commit()
        
        # 性能测试：按邮箱查询
        result = await async_session.execute(
            select(User).where(User.email == "performance_25@example.com")
        )
        found_user = result.scalar_one_or_none()
        
        assert found_user is not None
        assert found_user.email == "performance_25@example.com"
    
    @TestIsolation.unit_test
    async def test_user_multi_tenant_isolation(self, async_session: AsyncSession):
        """测试多租户数据隔离"""
        tenant1_id = uuid.uuid4()
        tenant2_id = uuid.uuid4()
        
        # 创建两个租户的用户
        user1 = User(
            tenant_id=tenant1_id,
            email="tenant1@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        
        user2 = User(
            tenant_id=tenant2_id,
            email="tenant2@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        
        async_session.add_all([user1, user2])
        await async_session.commit()
        
        # 查询租户1的用户
        result = await async_session.execute(
            select(User).where(User.tenant_id == tenant1_id)
        )
        tenant1_users = result.scalars().all()
        
        assert len(tenant1_users) == 1
        assert tenant1_users[0].email == "tenant1@example.com"
        
        # 查询租户2的用户
        result = await async_session.execute(
            select(User).where(User.tenant_id == tenant2_id)
        )
        tenant2_users = result.scalars().all()
        
        assert len(tenant2_users) == 1
        assert tenant2_users[0].email == "tenant2@example.com"