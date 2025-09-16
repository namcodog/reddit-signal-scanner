"""
任务模型单元测试

测试Task模型、TaskStatus枚举、FailureCategory枚举和TaskUpdate数据类
遵循项目的类型安全和简洁性原则
"""

import json
import uuid
from datetime import datetime
from typing import Optional, Any, Dict, cast
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.task import Task, TaskStatus, FailureCategory, TaskUpdate
from backend.app.models.user import User
from tests.fixtures.base_fixtures import TestIsolation
from tests.unit.backend.models.conftest import ModelTestHelpers, performance_test

# SQLAlchemy 列在类型系统中被视为 InstrumentedAttribute，需要 getattr 排除 mypy 噪音
TaskTenantIdColumn = cast(Any, getattr(Task, "tenant_id"))
TaskStatusColumn = cast(Any, getattr(Task, "status"))
TaskErrorCodeColumn = cast(Any, getattr(Task, "error_code"))
TaskFailureCategoryColumn = cast(Any, getattr(Task, "failure_category"))
TaskUserIdColumn = cast(Any, getattr(Task, "user_id"))


def ensure_uuid(value: Any) -> uuid.UUID:
    assert isinstance(value, uuid.UUID)
    return value

def ensure_task_status(value: Any) -> TaskStatus:
    assert isinstance(value, TaskStatus)
    return value

def ensure_datetime(value: Any) -> datetime:
    assert isinstance(value, datetime)
    return value

def ensure_optional_datetime(value: Any) -> Optional[datetime]:
    assert value is None or isinstance(value, datetime)
    return value

def ensure_optional_failure_category(value: Any) -> Optional[FailureCategory]:
    assert value is None or isinstance(value, FailureCategory)
    return value


class TestTaskStatus:
    """任务状态枚举测试"""
    
    @TestIsolation.unit_test
    def test_task_status_values(self) -> None:
        """测试任务状态枚举值"""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.PROCESSING.value == "processing"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.DEAD_LETTER.value == "dead_letter"
    
    @TestIsolation.unit_test
    def test_task_status_members(self) -> None:
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
    def test_task_status_string_conversion(self) -> None:
        """测试任务状态字符串转换"""
        assert str(TaskStatus.PENDING) == "TaskStatus.PENDING"
        assert TaskStatus.PENDING.value == "pending"


class TestFailureCategory:
    """失败类型枚举测试"""
    
    @TestIsolation.unit_test
    def test_failure_category_values(self) -> None:
        """测试失败类型枚举值"""
        assert FailureCategory.NETWORK_ERROR.value == "network_error"
        assert FailureCategory.PROCESSING_ERROR.value == "processing_error"
        assert FailureCategory.DATA_VALIDATION_ERROR.value == "data_validation_error"
        assert FailureCategory.SYSTEM_ERROR.value == "system_error"
    
    @TestIsolation.unit_test
    def test_failure_category_members(self) -> None:
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
    def test_task_update_creation(self) -> None:
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
    def test_task_update_to_json(self) -> None:
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
    def test_task_update_to_sse_format(self) -> None:
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
    ) -> None:
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
        task_any = cast(Any, task)
        assert ensure_uuid(task_any.user_id) == user.id
        assert ensure_uuid(task_any.tenant_id) == user.tenant_id
    
    @TestIsolation.unit_test
    async def test_task_model_field_types(self, async_session: AsyncSession) -> None:
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
        task_any = cast(Any, task)
        ensure_uuid(task_any.id)
        ensure_uuid(task_any.user_id)
        ensure_uuid(task_any.tenant_id)
        assert isinstance(task_any.product_description, str)
        ensure_task_status(task_any.status)
        ensure_datetime(task_any.created_at)
        ensure_optional_datetime(task_any.updated_at)
        ensure_optional_datetime(task_any.completed_at)
    
    @TestIsolation.unit_test
    async def test_task_model_defaults(self, async_session: AsyncSession) -> None:
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
        task_any = cast(Any, task)
        ensure_uuid(task_any.id)
        assert ensure_task_status(task_any.status) == TaskStatus.PENDING
        ensure_datetime(task_any.created_at)
        assert task_any.updated_at is None
        assert task_any.completed_at is None
        assert task_any.error_message is None
        assert task_any.error_code is None
        assert task_any.retry_count == 0
    
    @TestIsolation.unit_test
    async def test_task_status_transitions(self, async_session: AsyncSession) -> None:
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
        setattr(task, "status", TaskStatus.PROCESSING)
        await async_session.commit()
        assert cast(TaskStatus, task.status) == TaskStatus.PROCESSING
        
        # PROCESSING -> COMPLETED
        setattr(task, "status", TaskStatus.COMPLETED)
        setattr(task, "completed_at", datetime.now())
        await async_session.commit()
        assert cast(TaskStatus, task.status) == TaskStatus.COMPLETED
        assert task.completed_at is not None
    
    @TestIsolation.unit_test
    async def test_task_failure_handling(self, async_session: AsyncSession) -> None:
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
        setattr(task, "status", TaskStatus.FAILED)
        setattr(task, "error_message", "Test error message")
        setattr(task, "error_code", "TEST_ERROR")
        setattr(task, "failure_category", FailureCategory.PROCESSING_ERROR)
        setattr(task, "retry_count", 1)
        await async_session.commit()
        
        assert cast(TaskStatus, task.status) == TaskStatus.FAILED
        task_any = cast(Any, task)
        assert task_any.error_message == "Test error message"
        assert task_any.error_code == "TEST_ERROR"
        assert ensure_optional_failure_category(task_any.failure_category) == FailureCategory.PROCESSING_ERROR
        assert task_any.retry_count == 1
    
    @TestIsolation.unit_test
    async def test_task_user_relationship(self, async_session: AsyncSession) -> None:
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
            select(Task).where(TaskUserIdColumn == user.id)
        )
        user_tasks = result.scalars().all()
        
        assert len(user_tasks) == 3
        for task in user_tasks:
            task_any = cast(Any, task)
            assert ensure_uuid(task_any.user_id) == user.id
            assert ensure_uuid(task_any.tenant_id) == user.tenant_id
    
    @TestIsolation.unit_test
    async def test_task_not_null_constraints(self, async_session: AsyncSession) -> None:
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
    async def test_task_foreign_key_constraint(self, async_session: AsyncSession) -> None:
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
    async def test_task_multi_tenant_isolation(self, async_session: AsyncSession) -> None:
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
            select(Task).where(TaskTenantIdColumn == user1.tenant_id)
        )
        tenant1_tasks = result.scalars().all()
        
        assert len(tenant1_tasks) == 1
        assert tenant1_tasks[0].product_description == "Tenant 1 task"
        
        # 查询租户2的任务
        result = await async_session.execute(
            select(Task).where(TaskTenantIdColumn == user2.tenant_id)
        )
        tenant2_tasks = result.scalars().all()
        
        assert len(tenant2_tasks) == 1
        assert tenant2_tasks[0].product_description == "Tenant 2 task"
    
    @TestIsolation.unit_test
    @performance_test(max_duration=0.1)
    async def test_task_query_performance(self, async_session: AsyncSession) -> None:
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
                TaskTenantIdColumn == user.tenant_id,
                TaskStatusColumn == TaskStatus.COMPLETED
            )
        )
        completed_tasks = result.scalars().all()
        
        assert len(completed_tasks) == 50