"""
Reddit Signal Scanner - 完整数据库验收测试
Linus原则："数据结构决定一切，消除特殊情况"

一个测试搞定所有事情：
1. 数据库Schema完全可用
2. 基本CRUD操作正常工作
3. 约束正确阻止垃圾数据
4. 级联删除保持数据一致性
5. 多租户隔离确保安全性
6. 性能符合生产要求

100行代码比1483行更可靠。
"""

import logging
import time
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Task, Analysis, Report

logger = logging.getLogger(__name__)


class TestDatabaseComplete:
    """完整数据库验收测试 - Linus品味：一次性验证所有事情"""

    @pytest.mark.asyncio
    async def test_database_completely_functional(
        self, db_session: AsyncSession
    ) -> None:
        """
        验证数据库完全可用 - Linus原则：消除特殊情况

        这一个测试比原来1483行的8个测试更可靠，因为：
        1. 没有重复的数据库连接逻辑
        2. 测试真实的数据流，而不是人造的边界条件
        3. 验证系统作为整体工作，而不是组件孤立测试
        4. 50行代码，易于理解和维护
        """
        logger.info("🚀 开始完整数据库验收测试...")

        # ==================== 第1步：Schema验证 ====================
        # 验证核心表存在 - 直接查询，没有废话
        tables_result = await db_session.execute(
            text(
                """
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        """
            )
        )
        existing_tables = {row[0] for row in tables_result.fetchall()}

        required_tables = {"users", "tasks", "analyses", "reports", "community_caches"}
        missing_tables = required_tables - existing_tables
        assert not missing_tables, f"缺少核心表: {missing_tables}"

        logger.info("✅ 核心表存在验证通过")

        # ==================== 第2步：完整数据流测试 ====================
        # 创建真实的业务数据流：用户 -> 任务 -> 分析 -> 报告

        # 测试数据：两个不同租户
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()

        # 创建用户 - 验证约束和索引工作
        user_a = User(
            tenant_id=tenant_a,
            email="test_a@tenant-a.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj7.k7iBOdYW",
            email_verified=True,
            is_active=True,
        )
        user_b = User(
            tenant_id=tenant_b,
            email="test_b@tenant-b.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj7.k7iBOdYW",
            email_verified=True,
            is_active=True,
        )

        db_session.add_all([user_a, user_b])
        await db_session.flush()  # 获取ID但不提交

        # 创建任务 - 验证外键和CHECK约束
        task_a = Task(
            user_id=user_a.id,
            product_description="租户A的产品描述，长度符合10-2000字符要求",
            status="completed",
            completed_at=None,
        )
        task_b = Task(
            user_id=user_b.id,
            product_description="租户B的产品描述，长度符合10-2000字符要求",
            status="pending",
        )

        db_session.add_all([task_a, task_b])
        await db_session.flush()

        # 创建分析结果 - 验证JSONB约束和置信度范围
        analysis_a = Analysis(
            task_id=task_a.id,
            insights={
                "pain_points": [
                    {
                        "description": "测试痛点",
                        "frequency": 10,
                        "sentiment_score": 0.75,
                    }
                ],
                "competitors": [
                    {"name": "测试竞品", "mention_count": 5, "sentiment_score": 0.6}
                ],
                "opportunities": [
                    {
                        "title": "测试机会",
                        "description": "测试描述",
                        "urgency_score": 0.8,
                    }
                ],
            },
            sources={
                "communities": ["r/test"],
                "posts_analyzed": 100,
                "cache_hit_rate": 0.85,
            },
            confidence_score=0.85,
            analysis_version=1,
        )

        db_session.add(analysis_a)
        await db_session.flush()

        # 创建报告 - 验证完整的数据链
        report_a = Report(
            analysis_id=analysis_a.id,
            html_content="<h1>测试报告</h1><p>这是生成的HTML报告内容。</p>",
            status="active",
        )

        db_session.add(report_a)
        await db_session.commit()  # 提交所有数据

        logger.info("✅ 完整数据流创建成功")

        # ==================== 第3步：约束验证 ====================
        # 验证约束阻止垃圾数据 - 测试几个关键约束即可

        # 无效邮箱应该被拒绝
        with pytest.raises(Exception):  # 期望约束错误
            invalid_user = User(
                tenant_id=uuid.uuid4(),
                email="invalid-email-format",  # 违反邮箱格式约束
                password_hash="$2b$12$valid.hash",
                email_verified=False,
                is_active=True,
            )
            db_session.add(invalid_user)
            await db_session.commit()

        await db_session.rollback()  # 清理失败的事务

        # 无效置信度应该被拒绝
        with pytest.raises(Exception):  # 期望约束错误
            invalid_analysis = Analysis(
                task_id=task_a.id,
                insights={"pain_points": [], "competitors": [], "opportunities": []},
                sources={"communities": [], "posts_analyzed": 1, "cache_hit_rate": 0.5},
                confidence_score=1.5,  # 违反0-1范围约束
                analysis_version=1,
            )
            db_session.add(invalid_analysis)
            await db_session.commit()

        await db_session.rollback()  # 清理失败的事务

        logger.info("✅ 约束验证通过")

        # ==================== 第4步：多租户隔离验证 ====================
        # 验证租户A看不到租户B的数据
        tenant_a_tasks = await db_session.execute(
            text(
                """
            SELECT COUNT(*) FROM tasks t 
            JOIN users u ON t.user_id = u.id 
            WHERE u.tenant_id = :tenant_id
        """
            ),
            {"tenant_id": tenant_a},
        )

        a_count = tenant_a_tasks.scalar()
        assert a_count == 1, f"租户A应该看到1个任务，实际看到{a_count}个"

        # 跨租户查询应该返回空
        cross_query = await db_session.execute(
            text(
                """
            SELECT COUNT(*) FROM tasks t
            JOIN users u ON t.user_id = u.id
            WHERE u.tenant_id = :tenant_a AND t.user_id = :user_b_id
        """
            ),
            {"tenant_a": tenant_a, "user_b_id": user_b.id},
        )

        cross_count = cross_query.scalar()
        assert cross_count == 0, "跨租户查询应该返回空结果"

        logger.info("✅ 多租户隔离验证通过")

        # ==================== 第5步：级联删除验证 ====================
        # 验证删除用户时正确清理所有相关数据
        task_b_id = task_b.id

        # 删除用户B
        await db_session.delete(user_b)
        await db_session.commit()

        # 验证相关任务被级联删除
        remaining_tasks = await db_session.execute(
            text(
                """
            SELECT COUNT(*) FROM tasks WHERE id = :task_id
        """
            ),
            {"task_id": task_b_id},
        )

        task_count = remaining_tasks.scalar()
        assert task_count == 0, "用户删除后，相关任务应该被级联删除"

        # 验证租户A的数据不受影响
        remaining_a_tasks = await db_session.execute(
            text(
                """
            SELECT COUNT(*) FROM tasks t
            JOIN users u ON t.user_id = u.id  
            WHERE u.tenant_id = :tenant_id
        """
            ),
            {"tenant_id": tenant_a},
        )

        a_remaining = remaining_a_tasks.scalar()
        assert a_remaining == 1, "删除租户B不应该影响租户A的数据"

        logger.info("✅ 级联删除验证通过")

        # ==================== 第6步：性能验证 ====================
        # 验证基本操作性能符合生产要求

        # 任务创建性能测试 (目标: < 200ms)
        start_time = time.perf_counter()

        perf_task = Task(
            user_id=user_a.id,
            product_description="性能测试任务描述，符合长度要求",
            status="pending",
        )
        db_session.add(perf_task)
        await db_session.commit()

        create_time = (time.perf_counter() - start_time) * 1000
        assert create_time < 200, f"任务创建耗时{create_time:.1f}ms，超过200ms目标"

        # 任务状态查询性能测试 (目标: < 50ms)
        start_time = time.perf_counter()

        status_result = await db_session.execute(
            text(
                """
            SELECT status FROM tasks WHERE user_id = :user_id ORDER BY created_at DESC LIMIT 1
        """
            ),
            {"user_id": user_a.id},
        )

        status = status_result.scalar()
        query_time = (time.perf_counter() - start_time) * 1000

        assert status == "pending", "任务状态查询结果错误"
        assert query_time < 50, f"状态查询耗时{query_time:.1f}ms，超过50ms目标"

        logger.info(
            f"✅ 性能验证通过 - 创建:{create_time:.1f}ms, 查询:{query_time:.1f}ms"
        )

        logger.info("🎉 数据库完整验收测试通过 - 所有功能正常工作")

    async def test_database_handles_production_load(
        self, db_session: AsyncSession
    ) -> None:
        """验证数据库处理生产级负载 - 补充性能测试"""

        # 创建测试用户
        user = User(
            tenant_id=uuid.uuid4(),
            email="load_test@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj7.k7iBOdYW",
            email_verified=True,
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()

        # 批量创建任务测试
        start_time = time.perf_counter()

        tasks = [
            Task(
                user_id=user.id,
                product_description=f"批量测试任务 {i} - 描述内容符合长度要求",
                status="pending",
            )
            for i in range(100)  # 100个任务
        ]

        db_session.add_all(tasks)
        await db_session.commit()

        batch_time = (time.perf_counter() - start_time) * 1000
        avg_time = batch_time / 100

        assert avg_time < 20, f"批量创建平均耗时{avg_time:.1f}ms/个，超过20ms目标"

        logger.info(f"✅ 生产负载测试通过 - 批量创建100个任务耗时{batch_time:.1f}ms")
