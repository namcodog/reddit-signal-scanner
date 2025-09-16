"""
分析模型单元测试

测试Analysis模型、JSONB字段验证和Pydantic Schema
遵循项目的类型安全和简洁性原则，基于SQLAlchemy和pytest-asyncio最佳实践
"""

import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, cast
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

try:
    from sqlalchemy.exc import CheckViolation as _CheckViolation  # type: ignore[attr-defined]
except AttributeError:
    _CheckViolation = IntegrityError

CheckViolation = _CheckViolation

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.analysis import Analysis
from backend.app.models.user import User
from backend.app.models.task import Task, TaskStatus
from tests.fixtures.base_fixtures import TestIsolation
from tests.unit.backend.models.conftest import ModelTestHelpers, performance_test


class TestAnalysisModel:
    """分析模型单元测试类 - 基于SQLAlchemy最佳实践"""
    
    @TestIsolation.unit_test
    async def test_analysis_model_creation(
        self, 
        async_session: AsyncSession, 
        model_helpers: ModelTestHelpers,
        sample_analysis_data: Dict[str, Any]
    ) -> None:
        """测试分析模型创建 - 验证基本字段和关系"""
        # 创建用户和任务
        user = model_helpers.create_test_user(async_session)
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        task = model_helpers.create_test_task(user)
        async_session.add(task)
        await async_session.commit()
        await async_session.refresh(task)
        
        # 创建分析结果
        analysis = Analysis(
            task_id=task.id,
            insights=sample_analysis_data["insights"],
            sources=sample_analysis_data["sources"],
            confidence_score=Decimal("0.85"),
            analysis_version=1,
        )
        async_session.add(analysis)
        await async_session.commit()
        await async_session.refresh(analysis)
        
        # 验证字段
        assert analysis.id is not None
        assert analysis.task_id == task.id
        assert analysis.confidence_score == Decimal("0.85")
        assert analysis.analysis_version == 1
        assert analysis.created_at is not None
        assert analysis.insights == sample_analysis_data["insights"]
        assert analysis.sources == sample_analysis_data["sources"]
    
    @TestIsolation.unit_test
    async def test_analysis_field_types(self, async_session: AsyncSession) -> None:
        """测试分析模型字段类型"""
        user = User(
            email="analysis_types@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        task = Task(
            product_description="Type test",
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
        async_session.add(task)
        await async_session.commit()
        await async_session.refresh(task)
        
        analysis = Analysis(
            task_id=task.id,
            insights={"pain_points": [], "competitors": [], "opportunities": []},
            sources={"subreddits": [], "total_posts": 0},
            confidence_score=Decimal("0.75"),
        )
        async_session.add(analysis)
        await async_session.commit()
        await async_session.refresh(analysis)
        
        # 验证字段类型
        analysis_id = cast(uuid.UUID, analysis.id)
        task_id_value = cast(uuid.UUID, analysis.task_id)
        assert isinstance(analysis_id, uuid.UUID)
        assert isinstance(task_id_value, uuid.UUID)
        insights_data = cast(dict[str, Any], analysis.insights)
        sources_data = cast(dict[str, Any], analysis.sources)
        assert isinstance(insights_data, dict)
        assert isinstance(sources_data, dict)
        confidence = cast(Decimal, analysis.confidence_score)
        version_value = cast(int, analysis.analysis_version)
        created_at_value = cast(datetime, analysis.created_at)
        assert isinstance(confidence, Decimal)
        assert isinstance(version_value, int)
        assert isinstance(created_at_value, datetime)
    
    @TestIsolation.unit_test
    async def test_analysis_defaults(self, async_session: AsyncSession) -> None:
        """测试分析模型默认值"""
        user = User(
            email="analysis_defaults@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        task = Task(
            product_description="Defaults test",
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
            confidence_score=Decimal("0.80"),
        )
        async_session.add(analysis)
        await async_session.commit()
        await async_session.refresh(analysis)
        
        # 验证默认值
        assert analysis.id is not None  # UUID自动生成
        assert analysis.analysis_version == 1  # 默认版本
        assert analysis.created_at is not None  # 自动设置
    
    @TestIsolation.unit_test
    async def test_confidence_score_constraint(self, async_session: AsyncSession) -> None:
        """测试置信度约束 - 必须在0.00-1.00之间"""
        user = User(
            email="confidence_test@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        task = Task(
            product_description="Confidence test",
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
        async_session.add(task)
        await async_session.commit()
        await async_session.refresh(task)
        
        # 测试无效置信度值
        invalid_scores = [Decimal("-0.1"), Decimal("1.1"), Decimal("2.0")]
        
        for invalid_score in invalid_scores:
            analysis = Analysis(
                task_id=task.id,
                insights={"test": "data"},
                sources={"test": "source"},
                confidence_score=invalid_score,
            )
            async_session.add(analysis)
            
            with pytest.raises((IntegrityError, CheckViolation)):
                await async_session.commit()
            
            await async_session.rollback()
    
    @TestIsolation.unit_test
    async def test_analysis_version_constraint(self, async_session: AsyncSession) -> None:
        """测试分析版本约束 - 必须为正数"""
        user = User(
            email="version_test@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        task = Task(
            product_description="Version test",
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
        async_session.add(task)
        await async_session.commit()
        await async_session.refresh(task)
        
        # 测试无效版本号
        analysis = Analysis(
            task_id=task.id,
            insights={"test": "data"},
            sources={"test": "source"},
            confidence_score=Decimal("0.80"),
            analysis_version=0,  # 无效：必须为正数
        )
        async_session.add(analysis)
        
        with pytest.raises((IntegrityError, CheckViolation)):
            await async_session.commit()
    
    @TestIsolation.unit_test
    async def test_task_analysis_relationship(self, async_session: AsyncSession) -> None:
        """测试任务与分析的一对一关系"""
        user = User(
            email="relationship_test@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        task = Task(
            product_description="Relationship test",
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
        
        # 查询验证关系
        result = await async_session.execute(
            select(Analysis).where(Analysis.task_id == task.id)
        )
        found_analysis = result.scalar_one_or_none()
        
        assert found_analysis is not None
        assert found_analysis.task_id == task.id
    
    @TestIsolation.unit_test
    async def test_analysis_unique_task_constraint(self, async_session: AsyncSession) -> None:
        """测试分析结果与任务的唯一性约束 - 一个任务只能有一个分析"""
        user = User(
            email="unique_analysis@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        task = Task(
            product_description="Unique analysis test",
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
        async_session.add(task)
        await async_session.commit()
        await async_session.refresh(task)
        
        # 创建第一个分析
        analysis1 = Analysis(
            task_id=task.id,
            insights={"test": "data1"},
            sources={"test": "source1"},
            confidence_score=Decimal("0.85"),
        )
        async_session.add(analysis1)
        await async_session.commit()
        
        # 尝试创建第二个分析（应该失败）
        analysis2 = Analysis(
            task_id=task.id,
            insights={"test": "data2"},
            sources={"test": "source2"},
            confidence_score=Decimal("0.90"),
        )
        async_session.add(analysis2)
        
        with pytest.raises(IntegrityError):
            await async_session.commit()
    
    @TestIsolation.unit_test
    async def test_foreign_key_constraint(self, async_session: AsyncSession) -> None:
        """测试外键约束 - 必须引用存在的任务"""
        fake_task_id = uuid.uuid4()
        
        analysis = Analysis(
            task_id=fake_task_id,
            insights={"test": "data"},
            sources={"test": "source"},
            confidence_score=Decimal("0.75"),
        )
        async_session.add(analysis)
        
        with pytest.raises(IntegrityError):
            await async_session.commit()
    
    @TestIsolation.unit_test
    async def test_not_null_constraints(self, async_session: AsyncSession) -> None:
        """测试非空约束"""
        user = User(
            email="not_null_test@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        task = Task(
            product_description="Not null test",
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
        async_session.add(task)
        await async_session.commit()
        await async_session.refresh(task)
        
        # 测试insights非空
        with pytest.raises(IntegrityError):
            analysis = Analysis(
                task_id=task.id,
                # insights缺失
                sources={"test": "source"},
                confidence_score=Decimal("0.75"),
            )
            async_session.add(analysis)
            await async_session.commit()
        
        await async_session.rollback()
        
        # 测试sources非空
        with pytest.raises(IntegrityError):
            analysis = Analysis(
                task_id=task.id,
                insights={"test": "data"},
                # sources缺失
                confidence_score=Decimal("0.75"),
            )
            async_session.add(analysis)
            await async_session.commit()
    
    @TestIsolation.unit_test
    async def test_jsonb_insights_structure(self, async_session: AsyncSession) -> None:
        """测试JSONB insights字段结构"""
        user = User(
            email="jsonb_test@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        task = Task(
            product_description="JSONB test",
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
        async_session.add(task)
        await async_session.commit()
        await async_session.refresh(task)
        
        # 测试复杂的insights结构
        complex_insights = {
            "pain_points": [
                {
                    "title": "Complex setup",
                    "description": "Users find setup difficult",
                    "confidence": 0.85,
                    "source_count": 25,
                    "examples": ["forum post 1", "reddit comment 1"]
                }
            ],
            "competitors": [
                {
                    "name": "CompetitorX",
                    "strengths": ["Easy UI", "Good docs"],
                    "weaknesses": ["Expensive", "Limited features"],
                    "confidence": 0.78,
                    "market_share": "15%"
                }
            ],
            "opportunities": [
                {
                    "title": "Mobile-first approach",
                    "description": "Strong demand for mobile",
                    "market_size": "large",
                    "confidence": 0.92,
                    "estimated_users": 50000
                }
            ]
        }
        
        analysis = Analysis(
            task_id=task.id,
            insights=complex_insights,
            sources={"subreddits": ["r/test"], "total_posts": 100},
            confidence_score=Decimal("0.85"),
        )
        async_session.add(analysis)
        await async_session.commit()
        await async_session.refresh(analysis)
        
        # 验证JSONB数据完整性
        assert analysis.insights["pain_points"][0]["title"] == "Complex setup"
        assert analysis.insights["competitors"][0]["name"] == "CompetitorX"
        assert analysis.insights["opportunities"][0]["confidence"] == 0.92
    
    @TestIsolation.unit_test
    async def test_jsonb_sources_structure(self, async_session: AsyncSession) -> None:
        """测试JSONB sources字段结构"""
        user = User(
            email="sources_test@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        task = Task(
            product_description="Sources test",
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
        async_session.add(task)
        await async_session.commit()
        await async_session.refresh(task)
        
        # 测试复杂的sources结构
        complex_sources = {
            "subreddits": ["r/programming", "r/webdev", "r/startups"],
            "total_posts": 500,
            "date_range": {
                "start": "2024-01-01T00:00:00Z",
                "end": "2024-12-31T23:59:59Z"
            },
            "post_distribution": {
                "r/programming": 200,
                "r/webdev": 180,
                "r/startups": 120
            },
            "sentiment_analysis": {
                "positive": 0.45,
                "neutral": 0.35,
                "negative": 0.20
            }
        }
        
        analysis = Analysis(
            task_id=task.id,
            insights={"test": "data"},
            sources=complex_sources,
            confidence_score=Decimal("0.88"),
        )
        async_session.add(analysis)
        await async_session.commit()
        await async_session.refresh(analysis)
        
        # 验证JSONB数据完整性
        assert analysis.sources["total_posts"] == 500
        assert analysis.sources["subreddits"] == ["r/programming", "r/webdev", "r/startups"]
        assert analysis.sources["sentiment_analysis"]["positive"] == 0.45
    
    @TestIsolation.unit_test
    async def test_analysis_string_representation(self, async_session: AsyncSession) -> None:
        """测试字符串表示方法"""
        user = User(
            email="repr_test@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        task = Task(
            product_description="Repr test",
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
            confidence_score=Decimal("0.77"),
        )
        async_session.add(analysis)
        await async_session.commit()
        await async_session.refresh(analysis)
        
        # 测试__repr__
        repr_str = repr(analysis)
        assert "Analysis(" in repr_str
        assert str(analysis.id) in repr_str
        assert str(analysis.task_id) in repr_str
        assert "0.77" in repr_str
    
    @TestIsolation.unit_test
    async def test_confidence_percentage_property(self, async_session: AsyncSession) -> None:
        """测试置信度百分比属性"""
        user = User(
            email="percentage_test@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        task = Task(
            product_description="Percentage test",
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
            confidence_score=Decimal("0.856"),
        )
        async_session.add(analysis)
        await async_session.commit()
        await async_session.refresh(analysis)
        
        # 测试百分比转换
        assert abs(analysis.confidence_percentage - 85.6) < 0.1
    
    @TestIsolation.unit_test
    @performance_test(max_duration=0.2)
    async def test_analysis_query_performance(self, async_session: AsyncSession) -> None:
        """测试分析结果查询性能"""
        user = User(
            email="performance_analysis@example.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)
        
        # 批量创建任务和分析
        analyses = []
        for i in range(20):
            task = Task(
                product_description=f"Performance task {i}",
                user_id=user.id,
                tenant_id=user.tenant_id,
            )
            async_session.add(task)
            await async_session.flush()  # 获取task.id
            
            analysis = Analysis(
                task_id=task.id,
                insights={"test": f"data_{i}"},
                sources={"test": f"source_{i}"},
                confidence_score=Decimal(f"0.{80 + i}"),
            )
            analyses.append(analysis)
        
        async_session.add_all(analyses)
        await async_session.commit()
        
        # 性能测试：查询高置信度分析
        result = await async_session.execute(
            select(Analysis).where(Analysis.confidence_score > Decimal("0.90"))
        )
        high_confidence = result.scalars().all()
        
        # 验证结果合理性
        assert len(high_confidence) > 0
        for analysis in high_confidence:
            assert analysis.confidence_score > Decimal("0.90")