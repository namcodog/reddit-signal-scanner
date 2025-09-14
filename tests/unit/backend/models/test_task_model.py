"""
任务模型单元测试

测试Task模型、TaskStatus枚举、FailureCategory枚举和TaskUpdate数据类
遵循项目的类型安全和简洁性原则
"""

import json
import uuid
from datetime import datetime
from typing import Optional
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.task import Task, TaskStatus, FailureCategory, TaskUpdate
from backend.app.models.user import User
from tests.fixtures.base_fixtures import TestIsolation
from tests.unit.backend.models.conftest import ModelTestHelpers, performance_test


class TestTaskStatus:
    """任务状态枚举测试"""
    
    @TestIsolation.unit_test
    def test_task_status_values(self):
        """测试任务状态枚举值"""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.PROCESSING.value == "processing"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.DEAD_LETTER.value == "dead_letter"
    
    @TestIsolation.unit_test
    def test_task_status_members(self):
        """测试任务状态枚举成员"""
        expected_statuses = {
            TaskStatus.PENDING,
            TaskStatus.PROCESSING,
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.DEAD_LETTER,
        }
        assert set(TaskStatus) == expected_statuses
    
    @TestIsolation.unit_test
    def test_task_status_string_conversion(self):
        """测试任务状态字符串转换"""
        assert str(TaskStatus.PENDING) == "TaskStatus.PENDING"
        assert TaskStatus.PENDING.value == "pending"


class TestFailureCategory:
    """失败类型枚举测试"""
    
    @TestIsolation.unit_test
    def test_failure_category_values(self):
        """测试失败类型枚举值"""
        assert FailureCategory.NETWORK_ERROR.value == "network_error"
        assert FailureCategory.PROCESSING_ERROR.value == "processing_error"
        assert FailureCategory.DATA_VALIDATION_ERROR.value == "data_validation_error"
        assert FailureCategory.SYSTEM_ERROR.value == "system_error"
    
    @TestIsolation.unit_test
    def test_failure_category_members(self):
        """测试失败类型枚举成员"""
        expected_categories = {
            FailureCategory.NETWORK_ERROR,
            FailureCategory.PROCESSING_ERROR,
            FailureCategory.DATA_VALIDATION_ERROR,
            FailureCategory.SYSTEM_ERROR,
        }
        assert set(FailureCategory) == expected_categories


class TestTaskUpdate:
    """任务更新数据类测试"""
    
    @TestIsolation.unit_test
    def test_task_update_creation(self):
        """测试任务更新数据类创建"""
        timestamp = datetime.now()
        update = TaskUpdate(
            task_id="test-task-id",
            status=TaskStatus.PROCESSING,
            progress=50,
            message="正在分析Reddit数据...",
            timestamp=timestamp,
        )
        
        assert update.task_id == "test-task-id"
        assert update.status == TaskStatus.PROCESSING
        assert update.progress == 50
        assert update.message == "正在分析Reddit数据..."
        assert update.timestamp == timestamp
    
    @TestIsolation.unit_test
    def test_task_update_to_json(self):
        """测试任务更新转JSON"""
        timestamp = datetime.now()
        update = TaskUpdate(
            task_id="test-task-id",
            status=TaskStatus.COMPLETED,
            progress=100,
            message="分析完成",
            timestamp=timestamp,
        )
        
        json_str = update.to_json()
        data = json.loads(json_str)
        
        assert data["task_id"] == "test-task-id"
        assert data["status"] == "completed"
        assert data["progress"] == 100
        assert data["message"] == "分析完成"
        assert data["timestamp"] == timestamp.isoformat()
    
    @TestIsolation.unit_test
    def test_task_update_to_sse_format(self):
        """测试任务更新转SSE格式"""
        update = TaskUpdate(
            task_id="test-task-id",
            status=TaskStatus.FAILED,
            progress=0,
            message="分析失败",
            timestamp=datetime.now(),
        )
        
        sse_format = update.to_sse_format()
        
        assert sse_format.startswith("data: ")
        assert sse_format.endswith("\n\n")
        assert "test-task-id" in sse_format
        assert "failed" in sse_format


class TestTaskModel:
    """任务模型单元测试类"""
    
    @TestIsolation.unit_test
    async def test_task_model_creation(
        self, 
        async_session: AsyncSession, 
        model_helpers: ModelTestHelpers
    ):
        """测试任务模型创建"""
        # 先创建用户
        user = model_helpers.create_test_user(async_session)
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        # 创建任务
        task = model_helpers.create_test_task(user)
        async_session.add(task)
        await async_session.commit()
        await async_session.refresh(task)
        
        # 验证任务
        model_helpers.assert_task_valid(task)
        assert task.user_id == user.id
        assert task.tenant_id == user.tenant_id
    
    @TestIsolation.unit_test
    async def test_task_model_field_types(self, async_session: AsyncSession):
        """测试任务模型字段类型"""
        # 创建用户
        user = User(
            email="task_types@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        # 创建任务
        task = Task(
            product_description="Field types test",
            status=TaskStatus.PENDING,
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
        async_session.add(task)
        await async_session.commit()
        await async_session.refresh(task)
        
        # 验证字段类型
        assert isinstance(task.id, uuid.UUID)
        assert isinstance(task.user_id, uuid.UUID)
        assert isinstance(task.tenant_id, uuid.UUID)
        assert isinstance(task.product_description, str)
        assert isinstance(task.status, TaskStatus)
        assert isinstance(task.created_at, datetime)
        assert task.updated_at is None or isinstance(task.updated_at, datetime)
        assert task.completed_at is None or isinstance(task.completed_at, datetime)
    
    @TestIsolation.unit_test
    async def test_task_model_defaults(self, async_session: AsyncSession):
        """测试任务模型默认值"""
        user = User(
            email="task_defaults@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        # 创建任务（只设置必需字段）
        task = Task(
            product_description="Defaults test",
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
        async_session.add(task)
        await async_session.commit()
        await async_session.refresh(task)
        
        # 验证默认值
        assert task.id is not None  # UUID自动生成
        assert task.status == TaskStatus.PENDING  # 默认状态
        assert task.created_at is not None  # 自动设置
        assert task.updated_at is None  # 初始为空
        assert task.completed_at is None  # 初始为空
        assert task.error_message is None  # 初始为空
        assert task.error_code is None  # 初始为空
        assert task.retry_count == 0  # 默认重试次数
    
    @TestIsolation.unit_test
    async def test_task_status_transitions(self, async_session: AsyncSession):
        """测试任务状态转换"""
        user = User(
            email="status_transitions@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LearRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        task = Task(
            product_description="Status transitions test",
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
        async_session.add(task)
        await async_session.commit()
        
        # PENDING -> PROCESSING
        task.status = TaskStatus.PROCESSING
        await async_session.commit()
        assert task.status == TaskStatus.PROCESSING
        
        # PROCESSING -> COMPLETED
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now()
        await async_session.commit()
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None
    
    @TestIsolation.unit_test
    async def test_task_failure_handling(self, async_session: AsyncSession):
        """测试任务失败处理"""
        user = User(
            email="failure_handling@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LwwRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        task = Task(
            product_description="Failure handling test",
            status=TaskStatus.PROCESSING,
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
        async_session.add(task)
        await async_session.commit()
        
        # 设置失败状态
        task.status = TaskStatus.FAILED
        task.error_message = "Test error message"
        task.error_code = "TEST_ERROR"
        task.failure_category = FailureCategory.PROCESSING_ERROR
        task.retry_count = 1
        await async_session.commit()
        
        assert task.status == TaskStatus.FAILED
        assert task.error_message == "Test error message"
        assert task.error_code == "TEST_ERROR"
        assert task.failure_category == FailureCategory.PROCESSING_ERROR
        assert task.retry_count == 1
    
    @TestIsolation.unit_test
    async def test_task_user_relationship(self, async_session: AsyncSession):
        """测试任务与用户的关系"""
        user = User(
            email="relationship_test@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        # 创建多个任务
        tasks = []
        for i in range(3):
            task = Task(
                product_description=f"Relationship test {i}",
                user_id=user.id,
                tenant_id=user.tenant_id,
            )
            tasks.append(task)
        
        async_session.add_all(tasks)
        await async_session.commit()
        
        # 查询用户的任务
        result = await async_session.execute(
            select(Task).where(Task.user_id == user.id)
        )
        user_tasks = result.scalars().all()
        
        assert len(user_tasks) == 3
        for task in user_tasks:
            assert task.user_id == user.id
            assert task.tenant_id == user.tenant_id
    
    @TestIsolation.unit_test
    async def test_task_not_null_constraints(self, async_session: AsyncSession):
        """测试非空约束"""
        user = User(
            email="not_null_test@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        
        # 测试product_description非空
        with pytest.raises(IntegrityError):
            task = Task(
                user_id=user.id,
                tenant_id=user.tenant_id,
                # product_description缺失
            )
            async_session.add(task)
            await async_session.commit()
        
        await async_session.rollback()
        
        # 测试user_id非空
        with pytest.raises(IntegrityError):
            task = Task(
                product_description="No user test",
                tenant_id=user.tenant_id,
                # user_id缺失
            )
            async_session.add(task)
            await async_session.commit()
    
    @TestIsolation.unit_test
    async def test_task_foreign_key_constraint(self, async_session: AsyncSession):
        """测试外键约束"""
        # 尝试创建引用不存在用户的任务
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
    
    @TestIsolation.unit_test
    async def test_task_multi_tenant_isolation(self, async_session: AsyncSession):
        """测试多租户数据隔离"""
        # 创建两个租户的用户
        user1 = User(
            email="tenant1_tasks@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        user2 = User(
            email="tenant2_tasks@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        
        async_session.add_all([user1, user2])
        await async_session.commit()
        await async_session.refresh(user1)
        await async_session.refresh(user2)
        
        # 为每个租户创建任务
        task1 = Task(
            product_description="Tenant 1 task",
            user_id=user1.id,
            tenant_id=user1.tenant_id,
        )
        task2 = Task(
            product_description="Tenant 2 task",
            user_id=user2.id,
            tenant_id=user2.tenant_id,
        )
        
        async_session.add_all([task1, task2])
        await async_session.commit()
        
        # 查询租户1的任务
        result = await async_session.execute(
            select(Task).where(Task.tenant_id == user1.tenant_id)
        )
        tenant1_tasks = result.scalars().all()
        
        assert len(tenant1_tasks) == 1
        assert tenant1_tasks[0].product_description == "Tenant 1 task"
        
        # 查询租户2的任务
        result = await async_session.execute(
            select(Task).where(Task.tenant_id == user2.tenant_id)
        )
        tenant2_tasks = result.scalars().all()
        
        assert len(tenant2_tasks) == 1
        assert tenant2_tasks[0].product_description == "Tenant 2 task"
    
    @TestIsolation.unit_test
    @performance_test(max_duration=0.1)
    async def test_task_query_performance(self, async_session: AsyncSession):
        """测试任务查询性能"""
        # 创建用户
        user = User(
            email="performance_tasks@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        # 批量创建任务
        tasks = []
        for i in range(100):
            task = Task(
                product_description=f"Performance task {i}",
                user_id=user.id,
                tenant_id=user.tenant_id,
                status=TaskStatus.COMPLETED if i % 2 == 0 else TaskStatus.PENDING,
            )
            tasks.append(task)
        
        async_session.add_all(tasks)
        await async_session.commit()
        
        # 性能测试：查询已完成任务
        result = await async_session.execute(
            select(Task).where(
                Task.tenant_id == user.tenant_id,
                Task.status == TaskStatus.COMPLETED
            )
        )
        completed_tasks = result.scalars().all()
        
        assert len(completed_tasks) == 50