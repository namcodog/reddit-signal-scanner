"""
数据库模型关系测试

测试模型之间的关系、级联操作和数据完整性
基于SQLAlchemy最佳实践，确保关系映射和约束正确
"""

import uuid
from decimal import Decimal
from typing import Any, List, Optional, cast
import pytest
import pytest_asyncio
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.user import User
from backend.app.models.task import Task, TaskStatus
from backend.app.models.analysis import Analysis
from tests.fixtures.base_fixtures import TestIsolation
from tests.unit.backend.models.conftest import ModelTestHelpers, performance_test

TaskTenantIdColumn = cast(Any, getattr(Task, "tenant_id"))
TaskUserIdColumn = cast(Any, getattr(Task, "user_id"))
TaskStatusColumn = cast(Any, getattr(Task, "status"))
AnalysisTaskIdColumn = cast(Any, getattr(Analysis, "task_id"))

def ensure_uuid(value: Any) -> uuid.UUID:
    assert isinstance(value, uuid.UUID)
    return value

def ensure_task_status(value: Any) -> TaskStatus:
    assert isinstance(value, TaskStatus)
    return value

def ensure_decimal(value: Any) -> Decimal:
    assert isinstance(value, Decimal)
    return value

def ensure_optional_analysis(value: Any) -> Optional[Analysis]:
    assert value is None or isinstance(value, Analysis)
    return value


class TestModelRelationships:
    """模型关系测试类"""
    
    @TestIsolation.unit_test
    async def test_user_task_relationship(
        self, 
        async_session: AsyncSession,
        model_helpers: ModelTestHelpers
    ) -> None:
        """测试用户与任务的一对多关系"""
        # 创建用户
        user = model_helpers.create_test_user(async_session)
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        # 创建多个任务
        tasks = []
        for i in range(3):
            task = model_helpers.create_test_task(
                user, 
                product_description=f"Task {i} description"
            )
            tasks.append(task)
        
        async_session.add_all(tasks)
        await async_session.commit()
        
        # 验证关系：查询用户的所有任务
        result = await async_session.execute(
            select(Task).where(TaskUserIdColumn == user.id).order_by(Task.product_description)
        )
        user_tasks = result.scalars().all()
        
        assert len(user_tasks) == 3
        for i, task in enumerate(user_tasks):
            task_any = cast(Any, task)
            assert ensure_uuid(task_any.user_id) == user.id
            assert ensure_uuid(task_any.tenant_id) == user.tenant_id
            assert isinstance(task_any.product_description, str)
            assert f"Task {i}" in task_any.product_description
    
    @TestIsolation.unit_test
    async def test_task_analysis_relationship(self, async_session: AsyncSession) -> None:
        """测试任务与分析的一对一关系"""
        # 创建用户和任务
        user = User(
            email="task_analysis@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        task = Task(
            product_description="Analysis relationship test",
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
        async_session.add(task)
        await async_session.commit()
        await async_session.refresh(task)
        
        # 创建分析结果
        analysis = Analysis(
            task_id=task.id,
            insights={"pain_points": [], "competitors": [], "opportunities": []},
            sources={"subreddits": [], "total_posts": 0},
            confidence_score=Decimal("0.85"),
        )
        async_session.add(analysis)
        await async_session.commit()
        
        # 验证一对一关系
        result = await async_session.execute(cast(Any, select(Analysis).where(Analysis.task_id == task.id)))
        task_analysis_optional = result.scalar_one_or_none()
        task_analysis = ensure_optional_analysis(task_analysis_optional)
        assert task_analysis is not None
        assert ensure_uuid(task_analysis.task_id) == task.id
        assert ensure_decimal(task_analysis.confidence_score) == Decimal("0.85")
    
    @TestIsolation.unit_test
    async def test_cascade_delete_user_tasks(self, async_session: AsyncSession) -> None:
        """测试用户删除时的级联操作"""
        # 创建用户和任务
        user = User(
            email="cascade_test@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        # 创建多个任务
        task_ids = []
        for i in range(3):
            task = Task(
                product_description=f"Cascade test task {i}",
                user_id=user.id,
                tenant_id=user.tenant_id,
            )
            async_session.add(task)
            await async_session.flush()
            task_ids.append(task.id)
        
        await async_session.commit()
        
        # 删除用户（应该级联删除任务）
        await async_session.execute(delete(User).where(User.id == user.id))
        await async_session.commit()
        
        # 验证任务已被级联删除
        result = await async_session.execute(
            select(Task).where(Task.id.in_(task_ids))
        )
        remaining_tasks = result.scalars().all()
        
        assert len(remaining_tasks) == 0
    
    @TestIsolation.unit_test
    async def test_cascade_delete_task_analysis(self, async_session: AsyncSession) -> None:
        """测试任务删除时分析结果的级联删除"""
        # 创建用户、任务和分析
        user = User(
            email="analysis_cascade@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        task = Task(
            product_description="Analysis cascade test",
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
        async_session.add(task)
        await async_session.commit()
        await async_session.refresh(task)
        
        analysis = Analysis(
            task_id=task.id,
            insights={"test": "data"},
            sources={"test": "source"},
            confidence_score=Decimal("0.90"),
        )
        async_session.add(analysis)
        await async_session.commit()
        
        analysis_id = analysis.id
        
        # 删除任务（应该级联删除分析）
        await async_session.execute(delete(Task).where(Task.id == task.id))
        await async_session.commit()
        
        # 验证分析已被级联删除
        result = await async_session.execute(
            select(Analysis).where(Analysis.id == analysis_id)
        )
        remaining_analysis = result.scalar_one_or_none()
        
        assert remaining_analysis is None
    
    @TestIsolation.unit_test
    async def test_multi_tenant_data_isolation(self, async_session: AsyncSession) -> None:
        """测试多租户数据隔离的完整性"""
        # 创建两个租户的用户
        user1 = User(
            email="tenant1@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        user2 = User(
            email="tenant2@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        
        async_session.add_all([user1, user2])
        await async_session.commit()
        await async_session.refresh(user1)
        await async_session.refresh(user2)
        
        # 为每个租户创建任务和分析
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
        await async_session.refresh(task1)
        await async_session.refresh(task2)
        
        analysis1 = Analysis(
            task_id=task1.id,
            insights={"tenant": 1},
            sources={"tenant": 1},
            confidence_score=Decimal("0.85"),
        )
        analysis2 = Analysis(
            task_id=task2.id,
            insights={"tenant": 2},
            sources={"tenant": 2},
            confidence_score=Decimal("0.90"),
        )
        
        async_session.add_all([analysis1, analysis2])
        await async_session.commit()
        
        # 验证租户1只能看到自己的数据
        result = await async_session.execute(
            select(Task).where(TaskTenantIdColumn == user1.tenant_id)
        )
        tenant1_tasks = result.scalars().all()
        
        assert len(tenant1_tasks) == 1
        task_any_t1 = cast(Any, tenant1_tasks[0])
        assert isinstance(task_any_t1.product_description, str)
        assert task_any_t1.product_description == "Tenant 1 task"
        
        # 验证租户2只能看到自己的数据
        result = await async_session.execute(
            select(Task).where(TaskTenantIdColumn == user2.tenant_id)
        )
        tenant2_tasks = result.scalars().all()
        
        assert len(tenant2_tasks) == 1
        task_any_t2 = cast(Any, tenant2_tasks[0])
        assert isinstance(task_any_t2.product_description, str)
        assert task_any_t2.product_description == "Tenant 2 task"
        
        # 验证分析结果也隔离
        result = await async_session.execute(
            select(Analysis)
            .join(Task)
            .where(TaskTenantIdColumn == user1.tenant_id)
        )
        tenant1_analyses = result.scalars().all()
        
        assert len(tenant1_analyses) == 1
        analysis_any = cast(Any, tenant1_analyses[0])
        assert analysis_any.insights["tenant"] == 1
    
    @TestIsolation.unit_test
    async def test_eager_loading_relationships(self, async_session: AsyncSession) -> None:
        """测试预加载关系以避免N+1查询问题"""
        # 创建用户和多个任务
        user = User(
            email="eager_loading@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        tasks_with_analysis = []
        for i in range(5):
            task = Task(
                product_description=f"Eager loading task {i}",
                user_id=user.id,
                tenant_id=user.tenant_id,
            )
            async_session.add(task)
            await async_session.flush()
            
            if i % 2 == 0:  # 只为偶数任务创建分析
                analysis = Analysis(
                    task_id=task.id,
                    insights={"task_number": i},
                    sources={"task_number": i},
                    confidence_score=Decimal("0.80"),
                )
                async_session.add(analysis)
                tasks_with_analysis.append(task.id)
        
        await async_session.commit()
        
        # 使用预加载查询任务和分析
        result = await async_session.execute(
            select(Task)
            .options(selectinload(Task.analysis))
            .where(TaskUserIdColumn == user.id)
            .order_by(Task.product_description)
        )
        tasks = result.scalars().all()
        
        assert len(tasks) == 5
        
        # 验证预加载的分析结果
        analysis_count = 0
        for task in tasks:
            task_any = cast(Any, task)
            if task_any.id in tasks_with_analysis:
                # 这些任务应该有分析结果，且已预加载
                assert hasattr(task_any, "analysis")
                analysis_count += 1
        
        assert analysis_count == 3  # 偶数任务：0, 2, 4
    
    @TestIsolation.unit_test
    async def test_referential_integrity_violations(self, async_session: AsyncSession) -> None:
        """测试引用完整性违反的处理"""
        # 创建用户和任务
        user = User(
            email="integrity_test@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        # 测试：尝试创建引用不存在用户的任务
        with pytest.raises(Exception):  # 外键约束违反
            fake_user_id = uuid.uuid4()
            task = Task(
                product_description="Invalid user task",
                user_id=fake_user_id,
                tenant_id=user.tenant_id,
            )
            async_session.add(task)
            await async_session.commit()
    
    @TestIsolation.unit_test
    async def test_complex_query_across_relationships(self, async_session: AsyncSession) -> None:
        """测试跨关系的复杂查询"""
        # 创建测试数据
        users = []
        for i in range(2):
            user = User(
                email=f"complex_query_{i}@example.com",
                password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
            )
            users.append(user)
            async_session.add(user)
        
        await async_session.commit()
        
        # 为每个用户创建不同数量的任务
        all_analyses = []
        for i, user in enumerate(users):
            await async_session.refresh(user)
            for j in range(i + 2):  # user0: 2 tasks, user1: 3 tasks
                task = Task(
                    product_description=f"User {i} task {j}",
                    status=TaskStatus.COMPLETED if j == 0 else TaskStatus.PENDING,
                    user_id=user.id,
                    tenant_id=user.tenant_id,
                )
                async_session.add(task)
                await async_session.flush()
                
                if j == 0:  # 只为第一个任务创建分析
                    analysis = Analysis(
                        task_id=task.id,
                        insights={"user": i, "task": j},
                        sources={"user": i, "task": j},
                        confidence_score=Decimal(f"0.{80 + i * 5}"),
                    )
                    async_session.add(analysis)
                    all_analyses.append(analysis)
        
        await async_session.commit()
        
        # 复杂查询：查找所有已完成任务的高置信度分析
        query = select(Analysis)
        query = query.join(Task)
        query = query.join(User)
        query = query.where(
            TaskStatusColumn == TaskStatus.COMPLETED,
            Analysis.confidence_score > Decimal("0.80")
        )
        query = query.order_by(User.email)
        result = await async_session.execute(cast(Any, query))
        high_confidence_analyses = result.scalars().all()
        
        # 验证结果
        assert len(high_confidence_analyses) == 1  # 只有user1的分析满足条件
        assert high_confidence_analyses[0].confidence_score == Decimal("0.85")
    
    @TestIsolation.unit_test
    @performance_test(max_duration=0.3)
    async def test_relationship_query_performance(self, async_session: AsyncSession) -> None:
        """测试关系查询性能"""
        # 创建大量数据进行性能测试
        user = User(
            email="performance_relationships@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        # 批量创建任务和分析
        batch_size = 50
        for i in range(batch_size):
            task = Task(
                product_description=f"Performance task {i}",
                user_id=user.id,
                tenant_id=user.tenant_id,
                status=TaskStatus.COMPLETED if i % 3 == 0 else TaskStatus.PENDING,
            )
            async_session.add(task)
            await async_session.flush()
            
            if i % 3 == 0:  # 每3个任务创建一个分析
                analysis = Analysis(
                    task_id=task.id,
                    insights={"batch_number": i},
                    sources={"batch_number": i},
                    confidence_score=Decimal(f"0.{70 + (i % 30)}"),
                )
                async_session.add(analysis)
        
        await async_session.commit()
        
        # 性能测试：复杂的连接查询
        result = await async_session.execute(
            select(Task, Analysis)
            .outerjoin(Analysis)
            .where(
                TaskUserIdColumn == user.id,
                Task.status == TaskStatus.COMPLETED
            )
            .order_by(Task.created_at.desc())
        )
        task_analysis_pairs = result.all()
        
        # 验证查询结果合理性
        completed_count = len([pair for pair in task_analysis_pairs if pair[0].status == TaskStatus.COMPLETED])
        assert completed_count > 0
        assert completed_count <= batch_size // 3 + 1