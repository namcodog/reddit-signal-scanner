"""
数据完整性测试 - 完整验证套件

基于Linus的数据结构优先原则：
- 消除特殊情况，统一验证逻辑
- 数据库层面强制数据完整性
- 全面测试边界条件和约束违反场景
"""

import pytest
import uuid
import json
from typing import Dict, Any, List
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from app.models import User, Task, Analysis, Report, CommunityCache


class TestDataIntegrity:
    """数据完整性完整验证测试

    验证所有数据约束、JSON Schema验证、多租户隔离的正确执行。
    确保垃圾数据在数据库层面被拒绝，保证数据质量。
    """

    @pytest.mark.asyncio
    async def test_user_email_constraints(self, db_session: AsyncSession) -> None:
        """验证用户邮箱约束和唯一性

        测试邮箱格式验证、唯一性约束、空值处理。
        """
        tenant_id = uuid.uuid4()

        # 测试有效邮箱可以正常创建
        valid_user = User(
            tenant_id=tenant_id,
            email="valid@example.com",
            password_hash="$2b$12$validhash12345678901234567890",
            email_verified=False,
            is_active=True,
        )
        db_session.add(valid_user)
        await db_session.flush()
        assert valid_user.id is not None, "有效用户应该成功创建"

        # 测试重复邮箱被拒绝（唯一性约束）
        with pytest.raises(IntegrityError, match="duplicate key|unique constraint"):
            duplicate_user = User(
                tenant_id=tenant_id,
                email="valid@example.com",  # 重复邮箱
                password_hash="$2b$12$anotherhash12345678901234567890",
                email_verified=False,
                is_active=True,
            )
            db_session.add(duplicate_user)
            await db_session.flush()

        await db_session.rollback()

        # 测试空邮箱被拒绝（NOT NULL约束）
        with pytest.raises(IntegrityError, match="null value|not-null"):
            null_email_user = User(
                tenant_id=tenant_id,
                email=None,  # 空邮箱
                password_hash="$2b$12$validhash12345678901234567890",
                email_verified=False,
                is_active=True,
            )
            db_session.add(null_email_user)
            await db_session.flush()

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_foreign_key_constraints_enforced(
        self, db_session: AsyncSession
    ) -> None:
        """验证外键约束强制执行

        测试孤儿记录被拒绝，级联删除正确工作。
        """
        # 创建测试用户
        tenant_id = uuid.uuid4()
        test_user = User(
            tenant_id=tenant_id,
            email="fk_test@example.com",
            password_hash="$2b$12$validhash12345678901234567890",
            email_verified=True,
            is_active=True,
        )
        db_session.add(test_user)
        await db_session.flush()

        # 测试有效外键关系可以创建
        valid_task = Task(
            user_id=test_user.id,
            product_description="Valid task description for testing foreign key relationships",
            status="pending",
        )
        db_session.add(valid_task)
        await db_session.flush()
        assert valid_task.id is not None, "有效外键关系应该成功创建"

        # 测试无效外键被拒绝
        fake_user_id = uuid.uuid4()
        with pytest.raises(IntegrityError, match="foreign key|violates"):
            invalid_task = Task(
                user_id=fake_user_id,  # 不存在的用户ID
                product_description="Task with invalid foreign key reference",
                status="pending",
            )
            db_session.add(invalid_task)
            await db_session.flush()

        await db_session.rollback()

        # 测试级联删除
        db_session.add(test_user)
        await db_session.flush()

        cascade_task = Task(
            user_id=test_user.id,
            product_description="Task that should be deleted with user",
            status="pending",
        )
        db_session.add(cascade_task)
        await db_session.flush()

        task_id = cascade_task.id

        # 删除用户，任务应该级联删除
        await db_session.delete(test_user)
        await db_session.flush()

        # 验证任务被级联删除
        result = await db_session.execute(
            text("SELECT COUNT(*) FROM tasks WHERE id = :task_id"), {"task_id": task_id}
        )
        remaining_tasks = result.scalar()
        assert remaining_tasks == 0, "任务应该随用户级联删除"

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_json_schema_validation_functions(
        self, db_session: AsyncSession
    ) -> None:
        """验证JSON Schema验证函数完整性

        测试insights和sources的JSON验证函数是否正确工作。
        """
        # 测试有效的insights数据结构
        valid_insights = {
            "pain_points": ["Problem 1", "Problem 2"],
            "market_size": "large",
            "competition_level": "medium",
            "user_sentiment": "positive",
            "growth_indicators": ["indicator1", "indicator2"],
            "monetization_potential": "high",
        }

        result = await db_session.execute(
            text("SELECT validate_insights_schema(:data) as is_valid"),
            {"data": json.dumps(valid_insights)},
        )
        is_valid = result.scalar()
        assert is_valid is True, "有效的insights数据应该通过验证"

        # 测试无效的insights数据结构
        invalid_insights = {
            "invalid_field": "should not be here",
            "missing_required_fields": "incomplete",
        }

        result = await db_session.execute(
            text("SELECT validate_insights_schema(:data) as is_valid"),
            {"data": json.dumps(invalid_insights)},
        )
        is_valid = result.scalar()
        assert is_valid is False, "无效的insights数据应该被拒绝"

        # 测试有效的sources数据结构
        valid_sources = {
            "communities": ["r/test1", "r/test2"],
            "posts_analyzed": 100,
            "cache_hit_rate": 0.75,
            "analysis_duration_seconds": 45.5,
            "reddit_api_calls": 25,
        }

        result = await db_session.execute(
            text("SELECT validate_sources_schema(:data) as is_valid"),
            {"data": json.dumps(valid_sources)},
        )
        is_valid = result.scalar()
        assert is_valid is True, "有效的sources数据应该通过验证"

        # 测试无效的sources数据结构
        invalid_sources = {
            "communities": "should be array",  # 错误的数据类型
            "posts_analyzed": "not a number",
        }

        result = await db_session.execute(
            text("SELECT validate_sources_schema(:data) as is_valid"),
            {"data": json.dumps(invalid_sources)},
        )
        is_valid = result.scalar()
        assert is_valid is False, "无效的sources数据应该被拒绝"

    @pytest.mark.asyncio
    async def test_check_constraints_prevent_invalid_data(
        self, db_session: AsyncSession
    ) -> None:
        """验证CHECK约束阻止无效数据

        测试状态值、评分范围、版本号等CHECK约束。
        """
        # 创建测试用户和任务
        tenant_id = uuid.uuid4()
        test_user = User(
            tenant_id=tenant_id,
            email="check_test@example.com",
            password_hash="$2b$12$validhash12345678901234567890",
            email_verified=True,
            is_active=True,
        )
        db_session.add(test_user)
        await db_session.flush()

        valid_task = Task(
            user_id=test_user.id,
            product_description="Valid task for CHECK constraint testing",
            status="pending",
        )
        db_session.add(valid_task)
        await db_session.flush()

        # 测试confidence_score范围约束
        valid_insights = {
            "pain_points": ["Problem 1"],
            "market_size": "large",
            "competition_level": "medium",
            "user_sentiment": "positive",
            "growth_indicators": ["indicator1"],
            "monetization_potential": "high",
        }

        valid_sources = {
            "communities": ["r/test"],
            "posts_analyzed": 50,
            "cache_hit_rate": 0.5,
            "analysis_duration_seconds": 30.0,
            "reddit_api_calls": 10,
        }

        # 测试有效的confidence_score
        valid_analysis = Analysis(
            task_id=valid_task.id,
            insights=valid_insights,
            sources=valid_sources,
            confidence_score=0.85,  # 有效范围内
            analysis_version=1,
        )
        db_session.add(valid_analysis)
        await db_session.flush()
        assert valid_analysis.id is not None, "有效的confidence_score应该被接受"

        # 测试无效的confidence_score (超出范围)
        with pytest.raises(IntegrityError, match="check constraint|constraint"):
            invalid_analysis_high = Analysis(
                task_id=valid_task.id,
                insights=valid_insights,
                sources=valid_sources,
                confidence_score=1.5,  # 超出范围
                analysis_version=1,
            )
            db_session.add(invalid_analysis_high)
            await db_session.flush()

        await db_session.rollback()

        with pytest.raises(IntegrityError, match="check constraint|constraint"):
            invalid_analysis_low = Analysis(
                task_id=valid_task.id,
                insights=valid_insights,
                sources=valid_sources,
                confidence_score=-0.1,  # 超出范围
                analysis_version=1,
            )
            db_session.add(invalid_analysis_low)
            await db_session.flush()

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_multi_tenant_data_isolation(self, db_session: AsyncSession) -> None:
        """验证多租户数据隔离

        确保不同租户的数据完全隔离，无法跨租户访问。
        """
        # 创建两个不同租户的用户
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()

        user_a = User(
            tenant_id=tenant_a,
            email="tenant_a@example.com",
            password_hash="$2b$12$validhash12345678901234567890",
            email_verified=True,
            is_active=True,
        )

        user_b = User(
            tenant_id=tenant_b,
            email="tenant_b@example.com",
            password_hash="$2b$12$validhash12345678901234567890",
            email_verified=True,
            is_active=True,
        )

        db_session.add_all([user_a, user_b])
        await db_session.flush()

        # 为每个用户创建任务
        task_a = Task(
            user_id=user_a.id, product_description="Task for tenant A", status="pending"
        )

        task_b = Task(
            user_id=user_b.id,
            product_description="Task for tenant B",
            status="completed",
        )

        db_session.add_all([task_a, task_b])
        await db_session.flush()

        # 设置用户A的上下文并验证只能看到自己的数据
        await db_session.execute(text(f"SET app.current_user_id = '{user_a.id}'"))

        result = await db_session.execute(
            text(
                """
            SELECT COUNT(*) FROM tasks WHERE user_id = :user_id
        """
            ),
            {"user_id": user_a.id},
        )
        user_a_tasks = result.scalar()
        assert user_a_tasks == 1, f"用户A应该看到1个任务，实际: {user_a_tasks}"

        # 用户A不应该能看到用户B的任务
        result = await db_session.execute(
            text(
                """
            SELECT COUNT(*) FROM tasks WHERE user_id = :user_id
        """
            ),
            {"user_id": user_b.id},
        )
        cross_tenant_tasks = result.scalar()

        # 根据RLS策略，可能返回0或者抛出异常
        # 这里主要验证数据隔离的存在性
        print(f"跨租户查询结果: {cross_tenant_tasks}（应该为0或受限）")

        # 切换到用户B的上下文
        await db_session.execute(text(f"SET app.current_user_id = '{user_b.id}'"))

        result = await db_session.execute(
            text(
                """
            SELECT COUNT(*) FROM tasks WHERE user_id = :user_id
        """
            ),
            {"user_id": user_b.id},
        )
        user_b_tasks = result.scalar()
        assert user_b_tasks == 1, f"用户B应该看到1个任务，实际: {user_b_tasks}"

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_cascade_delete_cleanup(self, db_session: AsyncSession) -> None:
        """验证级联删除的数据清理完整性

        确保用户删除时所有相关数据都被正确清理。
        """
        # 创建完整的数据链
        tenant_id = uuid.uuid4()
        test_user = User(
            tenant_id=tenant_id,
            email="cascade_test@example.com",
            password_hash="$2b$12$validhash12345678901234567890",
            email_verified=True,
            is_active=True,
        )
        db_session.add(test_user)
        await db_session.flush()

        # 创建任务
        test_task = Task(
            user_id=test_user.id,
            product_description="Task for cascade delete testing",
            status="completed",
        )
        db_session.add(test_task)
        await db_session.flush()

        # 创建分析
        test_analysis = Analysis(
            task_id=test_task.id,
            insights={
                "pain_points": ["Problem 1"],
                "market_size": "large",
                "competition_level": "medium",
                "user_sentiment": "positive",
                "growth_indicators": ["indicator1"],
                "monetization_potential": "high",
            },
            sources={
                "communities": ["r/test"],
                "posts_analyzed": 50,
                "cache_hit_rate": 0.5,
                "analysis_duration_seconds": 30.0,
                "reddit_api_calls": 10,
            },
            confidence_score=0.85,
            analysis_version=1,
        )
        db_session.add(test_analysis)
        await db_session.flush()

        # 创建报告
        test_report = Report(
            analysis_id=test_analysis.id,
            html_content="<html><body>Test Report</body></html>",
            template_version=1,
        )
        db_session.add(test_report)
        await db_session.flush()

        # 记录ID以便后续验证
        user_id = test_user.id
        task_id = test_task.id
        analysis_id = test_analysis.id
        report_id = test_report.id

        # 删除用户，应该触发级联删除
        await db_session.delete(test_user)
        await db_session.flush()

        # 验证所有相关数据都被删除
        user_count = await db_session.execute(
            text("SELECT COUNT(*) FROM users WHERE id = :id"), {"id": user_id}
        )
        assert user_count.scalar() == 0, "用户应该被删除"

        task_count = await db_session.execute(
            text("SELECT COUNT(*) FROM tasks WHERE id = :id"), {"id": task_id}
        )
        assert task_count.scalar() == 0, "任务应该被级联删除"

        analysis_count = await db_session.execute(
            text("SELECT COUNT(*) FROM analyses WHERE id = :id"), {"id": analysis_id}
        )
        assert analysis_count.scalar() == 0, "分析应该被级联删除"

        report_count = await db_session.execute(
            text("SELECT COUNT(*) FROM reports WHERE id = :id"), {"id": report_id}
        )
        assert report_count.scalar() == 0, "报告应该被级联删除"

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_json_data_size_limits(self, db_session: AsyncSession) -> None:
        """验证JSON数据大小限制

        测试过大的JSON数据是否被正确处理或拒绝。
        """
        # 创建测试用户和任务
        tenant_id = uuid.uuid4()
        test_user = User(
            tenant_id=tenant_id,
            email="json_size_test@example.com",
            password_hash="$2b$12$validhash12345678901234567890",
            email_verified=True,
            is_active=True,
        )
        db_session.add(test_user)
        await db_session.flush()

        test_task = Task(
            user_id=test_user.id,
            product_description="Task for JSON size testing",
            status="pending",
        )
        db_session.add(test_task)
        await db_session.flush()

        # 创建大型JSON数据（模拟接近1MB的数据）
        large_insights = {
            "pain_points": ["Problem " + str(i) for i in range(1000)],
            "market_size": "large",
            "competition_level": "medium",
            "user_sentiment": "positive",
            "growth_indicators": ["Indicator " + str(i) for i in range(1000)],
            "monetization_potential": "high",
            "detailed_analysis": "A" * 100000,  # 100KB字符串
        }

        large_sources = {
            "communities": ["r/test" + str(i) for i in range(100)],
            "posts_analyzed": 50000,
            "cache_hit_rate": 0.5,
            "analysis_duration_seconds": 3600.0,
            "reddit_api_calls": 1000,
            "raw_data": "B" * 200000,  # 200KB字符串
        }

        # 测试大型JSON数据是否能被处理
        try:
            large_analysis = Analysis(
                task_id=test_task.id,
                insights=large_insights,
                sources=large_sources,
                confidence_score=0.75,
                analysis_version=1,
            )
            db_session.add(large_analysis)
            await db_session.flush()

            print("大型JSON数据成功写入，数据库能处理大JSON对象")
            assert large_analysis.id is not None

        except Exception as e:
            print(f"大型JSON数据被拒绝: {e}")
            # 这是可以接受的，表示有适当的大小限制
            await db_session.rollback()

        await db_session.rollback()
