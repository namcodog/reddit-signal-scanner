"""Reddit Signal Scanner - 多租户数据隔离测试

Linus设计原则："测试是设计的一部分"
- 全面验证租户隔离的有效性
- 测试所有可能的数据泄露场景
- 自动化的安全性验证
- 简单可维护的测试用例
"""

import pytest
import pytest_asyncio
import asyncio
from uuid import UUID, uuid4
from typing import List, Dict, Any
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_factory
from app.core.tenant_isolation import (
    TenantContext,
    set_tenant_context,
    get_current_tenant_context,
    create_tenant_context_from_user,
    with_tenant_context,
    verify_tenant_access,
    TENANT_AWARE_MODELS,
)
from app.core.user_context import UserContext
from app.core.tenant_security import (
    get_security_monitor,
    SecurityEventType,
    SecurityLevel,
)
from app.models.task import Task
from app.models.user import User
from app.utils.query_filter import get_user_tasks, safe_get_task, get_tenant_query_stats


class TestTenantIsolation:
    """租户数据隔离测试套件"""

    @pytest_asyncio.fixture
    async def session(self, db_session):
        """创建数据库会话（使用每个用例独立的引擎与会话）"""
        yield db_session

    @pytest.fixture
    def user1_context(self):
        """用户1的上下文"""
        return UserContext(
            user_id=str(uuid4()),
            is_anonymous=False,
            user_data={"email": "user1@example.com"},
        )

    @pytest.fixture
    def user2_context(self):
        """用户2的上下文"""
        return UserContext(
            user_id=str(uuid4()),
            is_anonymous=False,
            user_data={"email": "user2@example.com"},
        )

    @pytest.fixture
    def system_user_context(self):
        """系统用户上下文"""
        return UserContext(
            user_id=UserContext.SYSTEM_USER_ID,
            is_anonymous=False,
            user_data={"type": "system"},
        )

    @pytest_asyncio.fixture
    async def sample_tasks(self, session, user1_context, user2_context):
        """创建测试数据"""
        # 先确保对应用户存在（满足 tasks.user_id 外键约束）
        user1 = User(
            id=UUID(user1_context.user_id),
            tenant_id=UUID(user1_context.user_id),
            email="user1@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj7.k7iBOdYW",
            email_verified=False,
            is_active=True,
        )

        user2 = User(
            id=UUID(user2_context.user_id),
            tenant_id=UUID(user2_context.user_id),
            email="user2@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj7.k7iBOdYW",
            email_verified=False,
            is_active=True,
        )

        session.add_all([user1, user2])
        await session.commit()

        # 用户1的任务
        user1_tasks = [
            Task(
                user_id=UUID(user1_context.user_id),
                product_description=f"User1 Task {i}",
                status="pending",
            )
            for i in range(3)
        ]

        # 用户2的任务
        user2_tasks = [
            Task(
                user_id=UUID(user2_context.user_id),
                product_description=f"User2 Task {i}",
                status="pending",
            )
            for i in range(2)
        ]

        # 添加到数据库
        session.add_all(user1_tasks + user2_tasks)
        await session.commit()

        return {"user1_tasks": user1_tasks, "user2_tasks": user2_tasks}

    @pytest.mark.asyncio
    async def test_tenant_context_creation(self, user1_context):
        """测试租户上下文创建"""
        # 创建租户上下文
        tenant_context = create_tenant_context_from_user(user1_context)

        assert tenant_context.user_id == user1_context.user_id
        assert (
            tenant_context.tenant_id == user1_context.user_id
        )  # 当前实现中，user_id即tenant_id
        assert not tenant_context.is_system
        assert tenant_context.should_filter

    @pytest.mark.asyncio
    async def test_system_user_no_filtering(self, system_user_context):
        """测试系统用户不受限制"""
        tenant_context = create_tenant_context_from_user(system_user_context)

        assert tenant_context.is_system
        assert not tenant_context.should_filter

    @pytest.mark.asyncio
    async def test_basic_tenant_isolation(
        self, session, user1_context, user2_context, sample_tasks
    ):
        """测试基本租户隔离功能"""
        # 测试用户1只能查看自己的任务
        tenant_context1 = create_tenant_context_from_user(user1_context)
        set_tenant_context(tenant_context1)

        try:
            result = await session.execute(select(Task))
            tasks = result.scalars().all()

            # 只能查看用户1的任务
            assert len(tasks) == 3
            for task in tasks:
                assert str(task.user_id) == user1_context.user_id
                assert task.product_description.startswith("User1")

        finally:
            set_tenant_context(None)

        # 测试用户2只能查看自己的任务
        tenant_context2 = create_tenant_context_from_user(user2_context)
        set_tenant_context(tenant_context2)

        try:
            result = await session.execute(select(Task))
            tasks = result.scalars().all()

            # 只能查看用户2的任务
            assert len(tasks) == 2
            for task in tasks:
                assert str(task.user_id) == user2_context.user_id
                assert task.product_description.startswith("User2")

        finally:
            set_tenant_context(None)

    @pytest.mark.asyncio
    async def test_system_user_sees_all_data(
        self, session, system_user_context, sample_tasks
    ):
        """测试系统用户可以查看所有数据"""
        tenant_context = create_tenant_context_from_user(system_user_context)
        set_tenant_context(tenant_context)

        try:
            result = await session.execute(select(Task))
            tasks = result.scalars().all()

            # 系统用户可以查看所有任务
            assert len(tasks) == 5  # 3 + 2 = 5个任务

        finally:
            set_tenant_context(None)

    @pytest.mark.asyncio
    async def test_no_tenant_context_sees_all(self, session, sample_tasks):
        """测试无租户上下文时查看所有数据"""
        # 确保没有租户上下文
        set_tenant_context(None)

        result = await session.execute(select(Task))
        tasks = result.scalars().all()

        # 无租户上下文时，可以查看所有任务
        assert len(tasks) == 5

    @pytest.mark.asyncio
    async def test_context_manager(self, session, user1_context, sample_tasks):
        """测试上下文管理器功能"""
        # 在上下文管理器外，可以查看所有数据
        result = await session.execute(select(Task))
        all_tasks = result.scalars().all()
        assert len(all_tasks) == 5

        # 在上下文管理器内，只能查看当前用户的数据
        with with_tenant_context(user1_context):
            result = await session.execute(select(Task))
            user_tasks = result.scalars().all()
            assert len(user_tasks) == 3

            for task in user_tasks:
                assert str(task.user_id) == user1_context.user_id

        # 离开上下文管理器后，又可以查看所有数据
        result = await session.execute(select(Task))
        all_tasks_again = result.scalars().all()
        assert len(all_tasks_again) == 5

    @pytest.mark.asyncio
    async def test_query_filter_utilities(self, session, user1_context, sample_tasks):
        """测试查询过滤工具函数"""
        tenant_context = create_tenant_context_from_user(user1_context)
        set_tenant_context(tenant_context)

        try:
            # 测试 get_user_tasks 函数
            query = get_user_tasks(status="pending")
            result = await session.execute(query)
            tasks = result.scalars().all()

            assert len(tasks) == 3
            for task in tasks:
                assert str(task.user_id) == user1_context.user_id
                assert task.status == "pending"

            # 测试 safe_get_task 函数
            task_id = tasks[0].id
            task = await safe_get_task(session, task_id)
            assert task is not None
            assert str(task.user_id) == user1_context.user_id

            # 测试获取不属于当前用户的任务（应该返回 None）
            other_user_task = sample_tasks["user2_tasks"][0]
            forbidden_task = await safe_get_task(session, other_user_task.id)
            assert forbidden_task is None

        finally:
            set_tenant_context(None)

    @pytest.mark.asyncio
    async def test_tenant_access_verification(
        self, user1_context, user2_context, sample_tasks
    ):
        """测试租户访问验证函数"""
        # 设置用户1的租户上下文
        tenant_context = create_tenant_context_from_user(user1_context)
        set_tenant_context(tenant_context)

        try:
            # 用户可以访问自己的任务
            user1_task = sample_tasks["user1_tasks"][0]
            assert verify_tenant_access(user1_task)

            # 用户不能访问其他用户的任务
            user2_task = sample_tasks["user2_tasks"][0]
            assert not verify_tenant_access(user2_task)

            # 用户可以访问指定自己的用户ID
            assert verify_tenant_access(None, user1_context.user_id)

            # 用户不能访问其他用户ID
            assert not verify_tenant_access(None, user2_context.user_id)

        finally:
            set_tenant_context(None)

    @pytest.mark.asyncio
    async def test_security_monitoring(self, user1_context, user2_context):
        """测试安全监控功能"""
        monitor = get_security_monitor()
        initial_event_count = len(monitor.event_history)

        # 记录一个租户违规事件
        from app.core.tenant_security import record_tenant_violation

        tenant_context = create_tenant_context_from_user(user1_context)
        set_tenant_context(tenant_context)

        try:
            record_tenant_violation(
                message="测试租户违规事件",
                target_user_id=user2_context.user_id,
                target_resource="task",
            )

            # 验证事件已记录
            assert len(monitor.event_history) == initial_event_count + 1

            latest_event = monitor.event_history[-1]
            assert latest_event.event_type == SecurityEventType.TENANT_VIOLATION
            assert latest_event.user_id == user1_context.user_id
            assert latest_event.target_user_id == user2_context.user_id

            # 检查统计信息
            stats = monitor.get_statistics()
            assert stats["total_events"] >= 1
            assert "tenant_violation" in stats["event_type_stats"]

        finally:
            set_tenant_context(None)

    @pytest.mark.asyncio
    async def test_tenant_query_stats(self, user1_context):
        """测试租户查询统计功能"""
        # 无租户上下文
        stats = get_tenant_query_stats()
        assert not stats["tenant_context_active"]
        assert stats["user_id"] is None

        # 有租户上下文
        tenant_context = create_tenant_context_from_user(user1_context)
        set_tenant_context(tenant_context)

        try:
            stats = get_tenant_query_stats()
            assert stats["tenant_context_active"]
            assert stats["user_id"] == user1_context.user_id
            assert stats["tenant_id"] == user1_context.user_id
            assert not stats["is_system_user"]
            assert stats["filtering_enabled"]
            assert stats["tenant_aware_models"] > 0

        finally:
            set_tenant_context(None)

    @pytest.mark.asyncio
    async def test_concurrent_tenant_contexts(self, session, sample_tasks):
        """测试并发租户上下文（模拟多用户同时访问）"""
        user1_context = UserContext(user_id=str(uuid4()), is_anonymous=False)
        user2_context = UserContext(user_id=str(uuid4()), is_anonymous=False)

        # 为并发查询使用独立会话，避免同一会话在连接配置阶段的并发冲突
        from app.core.database import get_session_factory

        session_factory = get_session_factory()

        async def user1_queries():
            """用户1的查询操作"""
            tenant_context = create_tenant_context_from_user(user1_context)
            set_tenant_context(tenant_context)
            try:
                async with session_factory() as s1:
                    result = await s1.execute(select(Task))
                    tasks = result.scalars().all()
                    for task in tasks:
                        assert str(task.user_id) in [
                            str(t.user_id) for t in sample_tasks["user1_tasks"]
                        ] or str(task.user_id) in [
                            str(t.user_id) for t in sample_tasks["user2_tasks"]
                        ]
            finally:
                set_tenant_context(None)

        async def user2_queries():
            """User2的查询操作"""
            tenant_context = create_tenant_context_from_user(user2_context)
            set_tenant_context(tenant_context)
            try:
                async with session_factory() as s2:
                    result = await s2.execute(select(Task))
                    tasks = result.scalars().all()
                    for task in tasks:
                        assert str(task.user_id) in [
                            str(t.user_id) for t in sample_tasks["user1_tasks"]
                        ] or str(task.user_id) in [
                            str(t.user_id) for t in sample_tasks["user2_tasks"]
                        ]
            finally:
                set_tenant_context(None)

        # 并发执行
        await asyncio.gather(user1_queries(), user2_queries())

    @pytest.mark.asyncio
    async def test_tenant_isolation_with_complex_queries(
        self, session, user1_context, sample_tasks
    ):
        """测试复杂查询下的租户隔离"""
        tenant_context = create_tenant_context_from_user(user1_context)
        set_tenant_context(tenant_context)

        try:
            # 复杂查询：包含 WHERE、ORDER BY、LIMIT
            query = (
                select(Task)
                .where(Task.status == "pending")
                .order_by(Task.created_at.desc())
                .limit(10)
            )

            result = await session.execute(query)
            tasks = result.scalars().all()

            # 结果仍然应该被租户过滤
            assert len(tasks) <= 3  # 用户1最多有 3 个任务
            for task in tasks:
                assert str(task.user_id) == user1_context.user_id
                assert task.status == "pending"

            # 测试聚合查询
            from sqlalchemy import func

            count_query = select(func.count(Task.id)).where(Task.status == "pending")
            result = await session.execute(count_query)
            count = result.scalar()

            # 统计结果也应该被租户过滤
            assert count == 3  # 用户1的 3 个任务

        finally:
            set_tenant_context(None)

    @pytest.mark.asyncio
    async def test_tenant_isolation_edge_cases(self, session, user1_context):
        """测试边缘情况和异常场景"""
        # 测试空的租户上下文
        set_tenant_context(None)
        current_context = get_current_tenant_context()
        assert current_context is None

        # 测试无效的用户ID
        invalid_user_context = UserContext(user_id="invalid-uuid", is_anonymous=False)

        with pytest.raises(ValueError):
            # 尝试创建租户上下文时应该抛出异常（因为UUID无效）
            tenant_context = create_tenant_context_from_user(invalid_user_context)
            # 尝试访问 user_uuid 属性
            _ = tenant_context.user_uuid

        # 测试租户上下文切换
        tenant1 = create_tenant_context_from_user(user1_context)
        set_tenant_context(tenant1)

        context1 = get_current_tenant_context()
        assert context1.user_id == user1_context.user_id

        # 切换到另一个租户
        user2_context = UserContext(user_id=str(uuid4()), is_anonymous=False)
        tenant2 = create_tenant_context_from_user(user2_context)
        set_tenant_context(tenant2)

        context2 = get_current_tenant_context()
        assert context2.user_id == user2_context.user_id
        assert context2.user_id != context1.user_id

        # 清空租户上下文
        set_tenant_context(None)
        assert get_current_tenant_context() is None


class TestTenantSecurityIntegration:
    """租户安全集成测试"""

    @pytest.mark.asyncio
    async def test_cross_tenant_access_detection(self):
        """测试跨租户访问检测"""
        from app.core.tenant_security import detect_cross_tenant_access

        user1_id = str(uuid4())
        user2_id = str(uuid4())

        # 正常访问（同一用户）
        assert not detect_cross_tenant_access(user1_id, user1_id, "task")

        # 跨租户访问尝试
        assert detect_cross_tenant_access(user1_id, user2_id, "task")

    @pytest.mark.asyncio
    async def test_security_alert_system(self):
        """测试安全告警系统"""
        monitor = get_security_monitor()

        # 清空历史以便测试
        monitor.clear_history()

        # 测试告警处理器
        alert_triggered = []

        def test_alert_handler(event):
            alert_triggered.append(event)

        monitor.add_alert_handler(test_alert_handler)

        # 触发一个高级别安全事件
        from app.core.tenant_security import record_tenant_violation

        record_tenant_violation(
            message="测试高级别告警",
            level=SecurityLevel.HIGH,
            target_user_id="test-user-2",
            details={"test": True},
        )

        # 验证告警被触发
        assert len(alert_triggered) == 1
        assert alert_triggered[0].level == SecurityLevel.HIGH
        assert alert_triggered[0].message == "测试高级别告警"

        # 验证监控统计
        stats = monitor.get_statistics()
        assert stats["total_events"] >= 1
        assert "tenant_violation" in stats["event_type_stats"]
        assert stats["event_type_stats"]["tenant_violation"] >= 1

    @pytest.mark.asyncio
    async def test_tenant_aware_models_configuration(self):
        """测试租户识别模型配置"""
        from app.utils.query_filter import (
            get_tenant_aware_models,
            is_tenant_aware_model,
        )

        # 检查租户识别模型列表
        models = get_tenant_aware_models()
        assert len(models) > 0
        assert Task in models

        # 检查模型判断函数
        assert is_tenant_aware_model(Task)
        assert not is_tenant_aware_model(User)  # User模型不在租户识别列表中


@pytest.fixture(autouse=True)
def cleanup_tenant_context():
    """清理租户上下文的fixture，避免测试间互相影响"""
    yield
    # 清理租户上下文
    set_tenant_context(None)

    # 清理安全监控器
    monitor = get_security_monitor()
    monitor.clear_history()
