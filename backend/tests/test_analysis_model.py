"""
分析结果数据模型单元测试

基于 Linus 测试哲学：
- 测试边界条件比正常情况更重要
- 每个测试只验证一件事
- 测试失败场景，确保错误处理正确
- 数据完整性验证必须严格
"""

import pytest
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError, CheckViolation
from pydantic import ValidationError

from app.core.database import Base
from app.models.analysis import (
    Analysis,
    InsightsSchema,
    SourcesSchema,
    PainPoint,
    Competitor,
    Opportunity,
    AnalysisCreateRequest,
    AnalysisResponse,
    create_analysis_from_dict,
    validate_analysis_data,
    calculate_insights_quality_score,
)


# ===== 测试数据工厂 =====


class AnalysisDataFactory:
    """测试数据工厂类"""

    @staticmethod
    def valid_pain_point() -> Dict[str, Any]:
        return {
            "description": "找不到好用的Reddit营销工具",
            "sentiment_score": 0.75,
            "frequency": 23,
            "evidence_posts": ["post_123", "post_456"],
            "categories": ["工具缺失", "营销困难"],
        }

    @staticmethod
    def valid_competitor() -> Dict[str, Any]:
        return {
            "name": "Hootsuite",
            "mention_count": 45,
            "sentiment_score": 0.65,
            "strengths": ["功能全面", "界面友好"],
            "weaknesses": ["价格昂贵", "学习成本高"],
            "price_mentions": ["$99/month", "too expensive"],
            "market_position": "leader",
        }

    @staticmethod
    def valid_opportunity() -> Dict[str, Any]:
        return {
            "title": "Reddit内容自动化工具",
            "description": "自动化Reddit内容发布和互动管理工具，解决人工管理效率低下问题",
            "market_size_indicator": "large",
            "urgency_score": 0.85,
            "feasibility_score": 0.70,
            "target_communities": ["r/entrepreneur", "r/marketing"],
            "related_keywords": ["automation", "reddit bot"],
            "estimated_demand": 2500,
        }

    @staticmethod
    def valid_insights() -> Dict[str, Any]:
        return {
            "pain_points": [AnalysisDataFactory.valid_pain_point()],
            "competitors": [AnalysisDataFactory.valid_competitor()],
            "opportunities": [AnalysisDataFactory.valid_opportunity()],
            "analysis_summary": {"total_insights": 3},
            "key_insights": ["Reddit营销工具市场需求旺盛"],
        }

    @staticmethod
    def valid_sources() -> Dict[str, Any]:
        return {
            "communities": ["r/entrepreneur", "r/marketing", "r/startups"],
            "posts_analyzed": 1250,
            "comments_analyzed": 8450,
            "time_range_days": 30,
            "cache_hit_rate": 0.75,
            "analysis_duration_seconds": 45.6,
            "reddit_api_calls": 125,
            "data_quality_score": 0.92,
            "filtered_spam_posts": 23,
            "language_distribution": {"en": 1200, "es": 50},
            "algorithm_version": "v2.1.0",
            "processing_parameters": {
                "min_score_threshold": 5,
                "sentiment_model": "vader",
            },
        }


# ===== Pydantic Schema 测试 =====


class TestPainPointSchema:
    """痛点模型测试"""

    def test_valid_pain_point_creation(self):
        """测试有效痛点创建"""
        data = AnalysisDataFactory.valid_pain_point()
        pain_point = PainPoint(**data)

        assert pain_point.description == "找不到好用的Reddit营销工具"
        assert pain_point.sentiment_score == 0.75
        assert pain_point.frequency == 23
        assert len(pain_point.evidence_posts) == 2
        assert len(pain_point.categories) == 2

    def test_pain_point_validation_errors(self):
        """测试痛点验证错误"""
        base_data = AnalysisDataFactory.valid_pain_point()

        # 测试情感分数超出范围
        invalid_data = base_data.copy()
        invalid_data["sentiment_score"] = 1.5

        with pytest.raises(ValidationError) as exc_info:
            PainPoint(**invalid_data)
        assert "ensure this value is less than or equal to 1.0" in str(exc_info.value)

        # 测试描述为空
        invalid_data = base_data.copy()
        invalid_data["description"] = ""

        with pytest.raises(ValidationError):
            PainPoint(**invalid_data)

        # 测试频次为负数
        invalid_data = base_data.copy()
        invalid_data["frequency"] = -1

        with pytest.raises(ValidationError):
            PainPoint(**invalid_data)

    def test_pain_point_evidence_posts_limit(self):
        """测试证据帖子数量限制"""
        data = AnalysisDataFactory.valid_pain_point()
        data["evidence_posts"] = [f"post_{i}" for i in range(15)]  # 超过10个限制

        with pytest.raises(ValidationError) as exc_info:
            PainPoint(**data)
        assert "ensure this list has at most 10 items" in str(exc_info.value)


class TestCompetitorSchema:
    """竞争对手模型测试"""

    def test_valid_competitor_creation(self):
        """测试有效竞争对手创建"""
        data = AnalysisDataFactory.valid_competitor()
        competitor = Competitor(**data)

        assert competitor.name == "Hootsuite"
        assert competitor.mention_count == 45
        assert competitor.market_position == "leader"

    def test_competitor_market_position_validation(self):
        """测试市场定位验证"""
        data = AnalysisDataFactory.valid_competitor()

        # 测试无效市场定位
        data["market_position"] = "invalid_position"

        with pytest.raises(ValidationError) as exc_info:
            Competitor(**data)
        assert "string does not match regex" in str(exc_info.value)

        # 测试有效的市场定位
        for position in ["leader", "challenger", "niche", "unknown"]:
            data["market_position"] = position
            competitor = Competitor(**data)
            assert competitor.market_position == position


class TestOpportunitySchema:
    """商业机会模型测试"""

    def test_valid_opportunity_creation(self):
        """测试有效机会创建"""
        data = AnalysisDataFactory.valid_opportunity()
        opportunity = Opportunity(**data)

        assert opportunity.title == "Reddit内容自动化工具"
        assert opportunity.market_size_indicator == "large"
        assert opportunity.urgency_score == 0.85
        assert opportunity.feasibility_score == 0.70

    def test_opportunity_score_validation(self):
        """测试机会分数验证"""
        data = AnalysisDataFactory.valid_opportunity()

        # 测试紧迫性分数超出范围
        data["urgency_score"] = 1.5
        with pytest.raises(ValidationError):
            Opportunity(**data)

        # 测试可行性分数为负数
        data = AnalysisDataFactory.valid_opportunity()
        data["feasibility_score"] = -0.1
        with pytest.raises(ValidationError):
            Opportunity(**data)

    def test_opportunity_market_size_validation(self):
        """测试市场规模验证"""
        data = AnalysisDataFactory.valid_opportunity()
        data["market_size_indicator"] = "invalid_size"

        with pytest.raises(ValidationError) as exc_info:
            Opportunity(**data)
        assert "string does not match regex" in str(exc_info.value)


class TestInsightsSchema:
    """洞察结果Schema测试"""

    def test_valid_insights_creation(self):
        """测试有效洞察创建"""
        data = AnalysisDataFactory.valid_insights()
        insights = InsightsSchema(**data)

        assert len(insights.pain_points) == 1
        assert len(insights.competitors) == 1
        assert len(insights.opportunities) == 1
        assert insights.total_insights == 3

    def test_empty_insights_validation(self):
        """测试空洞察验证"""
        empty_data = {"pain_points": [], "competitors": [], "opportunities": []}

        with pytest.raises(ValidationError) as exc_info:
            InsightsSchema(**empty_data)
        assert "至少需要包含一种类型的分析洞察" in str(exc_info.value)

    def test_insights_array_limits(self):
        """测试洞察数组限制"""
        data = AnalysisDataFactory.valid_insights()

        # 测试痛点数量限制
        data["pain_points"] = [
            AnalysisDataFactory.valid_pain_point() for _ in range(55)
        ]

        with pytest.raises(ValidationError) as exc_info:
            InsightsSchema(**data)
        assert "ensure this list has at most 50 items" in str(exc_info.value)


class TestSourcesSchema:
    """数据来源Schema测试"""

    def test_valid_sources_creation(self):
        """测试有效数据来源创建"""
        data = AnalysisDataFactory.valid_sources()
        sources = SourcesSchema(**data)

        assert len(sources.communities) == 3
        assert sources.posts_analyzed == 1250
        assert sources.cache_hit_rate == 0.75
        assert sources.algorithm_version == "v2.1.0"

    def test_communities_format_validation(self):
        """测试社区名称格式验证"""
        data = AnalysisDataFactory.valid_sources()

        # 测试无效社区名称格式
        data["communities"] = ["entrepreneur", "marketing"]  # 缺少r/前缀

        with pytest.raises(ValidationError) as exc_info:
            SourcesSchema(**data)
        assert "社区名称必须以r/开头" in str(exc_info.value)

        # 测试社区名称太短
        data["communities"] = ["r/"]

        with pytest.raises(ValidationError) as exc_info:
            SourcesSchema(**data)
        assert "社区名称太短" in str(exc_info.value)

    def test_sources_numeric_validation(self):
        """测试数值字段验证"""
        data = AnalysisDataFactory.valid_sources()

        # 测试分析帖子数为0
        data["posts_analyzed"] = 0
        with pytest.raises(ValidationError):
            SourcesSchema(**data)

        # 测试缓存命中率超出范围
        data = AnalysisDataFactory.valid_sources()
        data["cache_hit_rate"] = 1.5
        with pytest.raises(ValidationError):
            SourcesSchema(**data)


# ===== SQLAlchemy ORM 测试 =====


class TestAnalysisORM:
    """Analysis ORM模型测试"""

    @pytest.fixture
    def db_session(self):
        """数据库会话fixture"""
        # 使用内存SQLite进行测试
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()

    def test_valid_analysis_creation(self, db_session):
        """测试有效分析创建"""
        analysis = Analysis(
            task_id=uuid.uuid4(),
            insights=AnalysisDataFactory.valid_insights(),
            sources=AnalysisDataFactory.valid_sources(),
            confidence_score=Decimal("0.85"),
            analysis_version=1,
        )

        db_session.add(analysis)
        db_session.commit()

        assert analysis.id is not None
        assert analysis.confidence_score == Decimal("0.85")
        assert analysis.analysis_version == 1
        assert analysis.created_at is not None

    def test_analysis_confidence_score_validation(self, db_session):
        """测试置信度分数验证"""
        analysis = Analysis(
            task_id=uuid.uuid4(),
            insights=AnalysisDataFactory.valid_insights(),
            sources=AnalysisDataFactory.valid_sources(),
            confidence_score=Decimal("1.5"),  # 超出范围
            analysis_version=1,
        )

        with pytest.raises(ValueError) as exc_info:
            db_session.add(analysis)
            db_session.commit()
        assert "置信度必须在0.00-1.00之间" in str(exc_info.value)

    def test_analysis_version_validation(self, db_session):
        """测试分析版本验证"""
        analysis = Analysis(
            task_id=uuid.uuid4(),
            insights=AnalysisDataFactory.valid_insights(),
            sources=AnalysisDataFactory.valid_sources(),
            confidence_score=Decimal("0.85"),
            analysis_version=0,  # 无效版本
        )

        with pytest.raises(ValueError) as exc_info:
            db_session.add(analysis)
            db_session.commit()
        assert "分析版本必须为正数" in str(exc_info.value)

    def test_analysis_properties(self, db_session):
        """测试分析属性方法"""
        insights = AnalysisDataFactory.valid_insights()
        sources = AnalysisDataFactory.valid_sources()

        analysis = Analysis(
            task_id=uuid.uuid4(),
            insights=insights,
            sources=sources,
            confidence_score=Decimal("0.85"),
            analysis_version=1,
        )

        # 测试置信度百分比
        assert analysis.confidence_percentage == 85.0

        # 测试洞察摘要
        summary = analysis.insights_summary
        assert summary["pain_points"] == 1
        assert summary["competitors"] == 1
        assert summary["opportunities"] == 1

        # 测试数据覆盖
        coverage = analysis.data_coverage
        assert coverage["posts_analyzed"] == 1250
        assert coverage["communities"] == 3
        assert coverage["cache_hit_rate"] == 0.75


# ===== API Schema 测试 =====


class TestAPISchemas:
    """API Schema模型测试"""

    def test_analysis_create_request(self):
        """测试分析创建请求"""
        request_data = {
            "task_id": str(uuid.uuid4()),
            "insights": AnalysisDataFactory.valid_insights(),
            "sources": AnalysisDataFactory.valid_sources(),
            "confidence_score": 0.85,
            "analysis_version": 1,
        }

        request = AnalysisCreateRequest(**request_data)

        assert request.confidence_score == 0.85
        assert request.analysis_version == 1
        assert isinstance(request.insights, InsightsSchema)
        assert isinstance(request.sources, SourcesSchema)

    def test_analysis_response(self):
        """测试分析响应模型"""
        # 模拟从ORM对象创建响应
        analysis_data = {
            "id": uuid.uuid4(),
            "task_id": uuid.uuid4(),
            "insights": AnalysisDataFactory.valid_insights(),
            "sources": AnalysisDataFactory.valid_sources(),
            "confidence_score": 0.85,
            "confidence_percentage": 85.0,
            "analysis_version": 1,
            "created_at": datetime.now(),
            "insights_summary": {
                "pain_points": 1,
                "competitors": 1,
                "opportunities": 1,
            },
            "data_coverage": {
                "posts_analyzed": 1250,
                "communities": 3,
                "cache_hit_rate": 0.75,
            },
        }

        response = AnalysisResponse(**analysis_data)

        assert response.confidence_score == 0.85
        assert response.confidence_percentage == 85.0
        assert response.insights_summary["pain_points"] == 1


# ===== 工具函数测试 =====


class TestUtilityFunctions:
    """工具函数测试"""

    def test_create_analysis_from_dict(self):
        """测试从字典创建分析对象"""
        data = {
            "task_id": uuid.uuid4(),
            "insights": AnalysisDataFactory.valid_insights(),
            "sources": AnalysisDataFactory.valid_sources(),
            "confidence_score": 0.85,
            "analysis_version": 2,
        }

        analysis = create_analysis_from_dict(data)

        assert analysis.task_id == data["task_id"]
        assert analysis.confidence_score == data["confidence_score"]
        assert analysis.analysis_version == 2

    def test_validate_analysis_data_valid(self):
        """测试有效分析数据验证"""
        insights = AnalysisDataFactory.valid_insights()
        sources = AnalysisDataFactory.valid_sources()

        assert validate_analysis_data(insights, sources) is True

    def test_validate_analysis_data_invalid(self):
        """测试无效分析数据验证"""
        invalid_insights = {
            "pain_points": [],
            "competitors": [],
            "opportunities": [],  # 空洞察，应该无效
        }
        sources = AnalysisDataFactory.valid_sources()

        assert validate_analysis_data(invalid_insights, sources) is False

    def test_calculate_insights_quality_score(self):
        """测试洞察质量分数计算"""
        # 创建多样化洞察
        insights = InsightsSchema(**AnalysisDataFactory.valid_insights())

        quality_score = calculate_insights_quality_score(insights)

        # 应该是相对较高的质量分数（多样性好）
        assert 0.0 <= quality_score <= 1.0
        assert quality_score > 0.5  # 有三种类型的洞察，质量应该不错

        # 测试单一类型洞察
        single_type_insights = InsightsSchema(
            pain_points=[AnalysisDataFactory.valid_pain_point()],
            competitors=[],
            opportunities=[],
        )

        single_quality = calculate_insights_quality_score(single_type_insights)
        assert single_quality < quality_score  # 多样性差，质量分数应该更低


# ===== 性能测试 =====


class TestPerformance:
    """性能测试"""

    def test_large_insights_creation_performance(self):
        """测试大量洞察创建性能"""
        import time

        # 创建大量洞察数据
        large_insights = {
            "pain_points": [AnalysisDataFactory.valid_pain_point() for _ in range(30)],
            "competitors": [AnalysisDataFactory.valid_competitor() for _ in range(20)],
            "opportunities": [
                AnalysisDataFactory.valid_opportunity() for _ in range(15)
            ],
            "key_insights": [f"洞察{i}" for i in range(10)],
        }

        # 性能基准：创建大型洞察结构应该在100ms内完成
        start_time = time.time()
        insights = InsightsSchema(**large_insights)
        end_time = time.time()

        creation_time = (end_time - start_time) * 1000  # 转换为毫秒

        assert creation_time < 100, f"大型洞察创建耗时过长: {creation_time:.2f}ms"
        assert insights.total_insights == 65  # 30 + 20 + 15

    def test_jsonb_serialization_performance(self):
        """测试JSONB序列化性能"""
        import time
        import json

        insights = AnalysisDataFactory.valid_insights()
        sources = AnalysisDataFactory.valid_sources()

        # 性能基准：JSON序列化应该在10ms内完成
        start_time = time.time()

        for _ in range(100):
            json.dumps(insights)
            json.dumps(sources)

        end_time = time.time()

        avg_time = ((end_time - start_time) / 100) * 1000  # 平均时间（毫秒）

        assert avg_time < 10, f"JSON序列化平均耗时过长: {avg_time:.2f}ms"


# ===== 边界条件测试 =====


class TestEdgeCases:
    """边界条件测试"""

    def test_maximum_field_lengths(self):
        """测试字段最大长度"""
        # 测试痛点描述最大长度
        max_description = "x" * 500
        pain_point_data = AnalysisDataFactory.valid_pain_point()
        pain_point_data["description"] = max_description

        pain_point = PainPoint(**pain_point_data)
        assert len(pain_point.description) == 500

        # 测试超出最大长度
        over_max_description = "x" * 501
        pain_point_data["description"] = over_max_description

        with pytest.raises(ValidationError):
            PainPoint(**pain_point_data)

    def test_unicode_content_handling(self):
        """测试Unicode内容处理"""
        # 测试中文内容
        chinese_data = AnalysisDataFactory.valid_pain_point()
        chinese_data["description"] = "找不到好用的Reddit营销工具，很困扰用户体验"
        chinese_data["categories"] = ["工具缺失", "用户体验"]

        pain_point = PainPoint(**chinese_data)
        assert "困扰" in pain_point.description
        assert "用户体验" in pain_point.categories

        # 测试emoji内容
        emoji_data = AnalysisDataFactory.valid_opportunity()
        emoji_data["title"] = "Reddit自动化工具 🤖"
        emoji_data["description"] = "解决效率问题 💡"

        opportunity = Opportunity(**emoji_data)
        assert "🤖" in opportunity.title
        assert "💡" in opportunity.description

    def test_decimal_precision_handling(self):
        """测试小数精度处理"""
        # 测试极限精度的置信度分数
        precise_scores = [0.001, 0.999, 0.5555, 0.1234]

        for score in precise_scores:
            pain_point_data = AnalysisDataFactory.valid_pain_point()
            pain_point_data["sentiment_score"] = score

            pain_point = PainPoint(**pain_point_data)
            assert pain_point.sentiment_score == score


if __name__ == "__main__":
    # 运行所有测试
    pytest.main([__file__, "-v", "--tb=short", "--cov=app.models.analysis"])
