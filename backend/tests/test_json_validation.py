"""
Reddit Signal Scanner - JSON Schema 验证测试
基于 Linus Torvalds 原则：彻底测试，确保可靠性
PRD-01-04: 验证JSON validation functions的正确性
"""

import pytest
import asyncio
from typing import Dict, Any, List
from unittest.mock import AsyncMock, patch
import json

import asyncpg
from app.core.database import get_engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


class TestJSONValidation:
    """JSON Schema验证函数测试套件"""

    @pytest.fixture
    async def db_session(self):
        """创建数据库连接用于测试"""
        engine = get_engine()
        async with engine.begin() as conn:
            yield conn

    # ====================================================================
    # validate_insights_schema 测试用例
    # ====================================================================

    def get_valid_insights_data(self) -> Dict[str, Any]:
        """返回有效的insights JSON数据"""
        return {
            "pain_points": [
                {
                    "description": "高价格困扰用户",
                    "frequency": 156,
                    "sentiment_score": -0.7,
                    "example_posts": ["post_id_1", "post_id_2", "post_id_3"],
                },
                {
                    "description": "缺乏功能性",
                    "frequency": 89,
                    "sentiment_score": -0.4,
                    "example_posts": ["post_id_4", "post_id_5"],
                },
            ],
            "competitors": [
                {
                    "name": "Competitor A",
                    "mentions": 45,
                    "sentiment": 0.6,
                    "strengths": ["价格低", "功能多"],
                    "weaknesses": ["质量差", "服务不好"],
                },
                {
                    "name": "Competitor B",
                    "mentions": 23,
                    "sentiment": 0.2,
                    "strengths": ["品牌知名度高"],
                    "weaknesses": ["价格贵", "更新慢"],
                },
            ],
            "opportunities": [
                {
                    "description": "价格敏感市场机会",
                    "relevance_score": 0.8,
                    "potential_users": 1500,
                },
                {
                    "description": "功能增强需求",
                    "relevance_score": 0.7,
                    "potential_users": 800,
                },
            ],
        }

    async def test_validate_insights_schema_valid_data(self, db_session):
        """测试有效的insights数据验证"""
        valid_data = self.get_valid_insights_data()

        result = await db_session.execute(
            text("SELECT validate_insights_schema(:data)"),
            {"data": json.dumps(valid_data)},
        )

        assert result.scalar() is True

    async def test_validate_insights_schema_missing_pain_points(self, db_session):
        """测试缺少pain_points字段"""
        invalid_data = self.get_valid_insights_data()
        del invalid_data["pain_points"]

        result = await db_session.execute(
            text("SELECT validate_insights_schema(:data)"),
            {"data": json.dumps(invalid_data)},
        )

        assert result.scalar() is False

    async def test_validate_insights_schema_missing_competitors(self, db_session):
        """测试缺少competitors字段"""
        invalid_data = self.get_valid_insights_data()
        del invalid_data["competitors"]

        result = await db_session.execute(
            text("SELECT validate_insights_schema(:data)"),
            {"data": json.dumps(invalid_data)},
        )

        assert result.scalar() is False

    async def test_validate_insights_schema_missing_opportunities(self, db_session):
        """测试缺少opportunities字段"""
        invalid_data = self.get_valid_insights_data()
        del invalid_data["opportunities"]

        result = await db_session.execute(
            text("SELECT validate_insights_schema(:data)"),
            {"data": json.dumps(invalid_data)},
        )

        assert result.scalar() is False

    async def test_validate_insights_schema_wrong_pain_point_type(self, db_session):
        """测试pain_points中字段类型错误"""
        invalid_data = self.get_valid_insights_data()
        invalid_data["pain_points"][0]["frequency"] = "not_a_number"

        result = await db_session.execute(
            text("SELECT validate_insights_schema(:data)"),
            {"data": json.dumps(invalid_data)},
        )

        assert result.scalar() is False

    async def test_validate_insights_schema_sentiment_out_of_range(self, db_session):
        """测试sentiment_score超出范围[-1, 1]"""
        invalid_data = self.get_valid_insights_data()
        invalid_data["pain_points"][0]["sentiment_score"] = 2.0  # 超出范围

        result = await db_session.execute(
            text("SELECT validate_insights_schema(:data)"),
            {"data": json.dumps(invalid_data)},
        )

        assert result.scalar() is False

    async def test_validate_insights_schema_negative_frequency(self, db_session):
        """测试负数frequency"""
        invalid_data = self.get_valid_insights_data()
        invalid_data["pain_points"][0]["frequency"] = -10

        result = await db_session.execute(
            text("SELECT validate_insights_schema(:data)"),
            {"data": json.dumps(invalid_data)},
        )

        assert result.scalar() is False

    async def test_validate_insights_schema_wrong_competitor_structure(
        self, db_session
    ):
        """测试competitors结构错误"""
        invalid_data = self.get_valid_insights_data()
        invalid_data["competitors"][0]["strengths"] = "not_an_array"

        result = await db_session.execute(
            text("SELECT validate_insights_schema(:data)"),
            {"data": json.dumps(invalid_data)},
        )

        assert result.scalar() is False

    async def test_validate_insights_schema_empty_arrays(self, db_session):
        """测试空数组是否被接受"""
        valid_data = {"pain_points": [], "competitors": [], "opportunities": []}

        result = await db_session.execute(
            text("SELECT validate_insights_schema(:data)"),
            {"data": json.dumps(valid_data)},
        )

        assert result.scalar() is True

    # ====================================================================
    # validate_sources_schema 测试用例
    # ====================================================================

    def get_valid_sources_data(self) -> Dict[str, Any]:
        """返回有效的sources JSON数据"""
        return {
            "communities": ["r/startups", "r/entrepreneur", "r/business"],
            "posts_analyzed": 150,
            "cache_hit_rate": 0.75,
            "analysis_duration_seconds": 45.5,
            "reddit_api_calls": 28,
        }

    async def test_validate_sources_schema_valid_data(self, db_session):
        """测试有效的sources数据验证"""
        valid_data = self.get_valid_sources_data()

        result = await db_session.execute(
            text("SELECT validate_sources_schema(:data)"),
            {"data": json.dumps(valid_data)},
        )

        assert result.scalar() is True

    async def test_validate_sources_schema_missing_communities(self, db_session):
        """测试缺少communities字段"""
        invalid_data = self.get_valid_sources_data()
        del invalid_data["communities"]

        result = await db_session.execute(
            text("SELECT validate_sources_schema(:data)"),
            {"data": json.dumps(invalid_data)},
        )

        assert result.scalar() is False

    async def test_validate_sources_schema_invalid_community_format(self, db_session):
        """测试无效的Reddit社区格式"""
        invalid_data = self.get_valid_sources_data()
        invalid_data["communities"] = ["invalid_format", "r/valid"]

        result = await db_session.execute(
            text("SELECT validate_sources_schema(:data)"),
            {"data": json.dumps(invalid_data)},
        )

        assert result.scalar() is False

    async def test_validate_sources_schema_community_with_special_chars(
        self, db_session
    ):
        """测试包含特殊字符的社区名（应该失败）"""
        invalid_data = self.get_valid_sources_data()
        invalid_data["communities"] = ["r/test-community", "r/valid"]

        result = await db_session.execute(
            text("SELECT validate_sources_schema(:data)"),
            {"data": json.dumps(invalid_data)},
        )

        assert result.scalar() is False

    async def test_validate_sources_schema_negative_posts_analyzed(self, db_session):
        """测试负数posts_analyzed"""
        invalid_data = self.get_valid_sources_data()
        invalid_data["posts_analyzed"] = -5

        result = await db_session.execute(
            text("SELECT validate_sources_schema(:data)"),
            {"data": json.dumps(invalid_data)},
        )

        assert result.scalar() is False

    async def test_validate_sources_schema_cache_hit_rate_out_of_range(
        self, db_session
    ):
        """测试cache_hit_rate超出[0, 1]范围"""
        invalid_data = self.get_valid_sources_data()
        invalid_data["cache_hit_rate"] = 1.5  # 超出范围

        result = await db_session.execute(
            text("SELECT validate_sources_schema(:data)"),
            {"data": json.dumps(invalid_data)},
        )

        assert result.scalar() is False

    async def test_validate_sources_schema_wrong_field_type(self, db_session):
        """测试字段类型错误"""
        invalid_data = self.get_valid_sources_data()
        invalid_data["analysis_duration_seconds"] = "not_a_number"

        result = await db_session.execute(
            text("SELECT validate_sources_schema(:data)"),
            {"data": json.dumps(invalid_data)},
        )

        assert result.scalar() is False

    async def test_validate_sources_schema_edge_cases(self, db_session):
        """测试边界情况"""
        edge_case_data = {
            "communities": ["r/a"],  # 最短的有效社区名
            "posts_analyzed": 0,  # 最小值
            "cache_hit_rate": 0.0,  # 最小值
            "analysis_duration_seconds": 0.1,  # 接近最小值
            "reddit_api_calls": 0,  # 最小值
        }

        result = await db_session.execute(
            text("SELECT validate_sources_schema(:data)"),
            {"data": json.dumps(edge_case_data)},
        )

        assert result.scalar() is True

    async def test_validate_sources_schema_perfect_cache_hit(self, db_session):
        """测试完美缓存命中率（1.0）"""
        perfect_cache_data = self.get_valid_sources_data()
        perfect_cache_data["cache_hit_rate"] = 1.0

        result = await db_session.execute(
            text("SELECT validate_sources_schema(:data)"),
            {"data": json.dumps(perfect_cache_data)},
        )

        assert result.scalar() is True

    # ====================================================================
    # 异常处理和边界测试
    # ====================================================================

    async def test_validate_insights_schema_null_input(self, db_session):
        """测试NULL输入"""
        result = await db_session.execute(text("SELECT validate_insights_schema(NULL)"))

        assert result.scalar() is False

    async def test_validate_sources_schema_null_input(self, db_session):
        """测试NULL输入"""
        result = await db_session.execute(text("SELECT validate_sources_schema(NULL)"))

        assert result.scalar() is False

    async def test_validate_insights_schema_empty_json(self, db_session):
        """测试空JSON对象"""
        result = await db_session.execute(
            text("SELECT validate_insights_schema('{}')"),
        )

        assert result.scalar() is False

    async def test_validate_sources_schema_empty_json(self, db_session):
        """测试空JSON对象"""
        result = await db_session.execute(
            text("SELECT validate_sources_schema('{}')"),
        )

        assert result.scalar() is False

    async def test_validate_insights_schema_malformed_json(self, db_session):
        """测试格式错误的JSON（数据库会在解析阶段就失败）"""
        with pytest.raises(Exception):  # 数据库级别的JSON解析错误
            await db_session.execute(
                text("SELECT validate_insights_schema('{invalid json}')"),
            )

    # ====================================================================
    # 性能和并发测试
    # ====================================================================

    async def test_validate_functions_performance(self, db_session):
        """测试验证函数的性能（应该很快完成）"""
        import time

        valid_insights = self.get_valid_insights_data()
        valid_sources = self.get_valid_sources_data()

        # 测试insights验证性能
        start_time = time.time()
        for _ in range(100):
            await db_session.execute(
                text("SELECT validate_insights_schema(:data)"),
                {"data": json.dumps(valid_insights)},
            )
        insights_duration = time.time() - start_time

        # 测试sources验证性能
        start_time = time.time()
        for _ in range(100):
            await db_session.execute(
                text("SELECT validate_sources_schema(:data)"),
                {"data": json.dumps(valid_sources)},
            )
        sources_duration = time.time() - start_time

        # 性能断言：100次调用应该在1秒内完成
        assert insights_duration < 1.0, f"insights验证太慢: {insights_duration}s"
        assert sources_duration < 1.0, f"sources验证太慢: {sources_duration}s"

    # ====================================================================
    # 集成测试辅助函数
    # ====================================================================

    async def test_functions_are_parallel_safe(self, db_session):
        """测试函数是否真正支持并行执行"""
        valid_insights = self.get_valid_insights_data()
        valid_sources = self.get_valid_sources_data()

        # 并发执行多个验证
        tasks = []
        for i in range(10):
            tasks.append(
                db_session.execute(
                    text("SELECT validate_insights_schema(:data)"),
                    {"data": json.dumps(valid_insights)},
                )
            )
            tasks.append(
                db_session.execute(
                    text("SELECT validate_sources_schema(:data)"),
                    {"data": json.dumps(valid_sources)},
                )
            )

        # 所有任务应该都成功完成
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            assert not isinstance(result, Exception), f"并行执行失败: {result}"
            assert result.scalar() is True


# 运行测试的配置
if __name__ == "__main__":
    """
    运行测试的说明：

    1. 确保数据库已启动并包含json_validators.sql中的函数
    2. 运行命令: pytest backend/tests/test_json_validation.py -v
    3. 查看覆盖率: pytest --cov=backend/database/functions backend/tests/test_json_validation.py
    """
    print("🧪 JSON验证函数测试套件")
    print("📋 包含以下测试类别：")
    print("   • 有效数据验证")
    print("   • 结构完整性检查")
    print("   • 类型验证")
    print("   • 范围检查")
    print("   • 边界情况处理")
    print("   • 异常处理")
    print("   • 性能测试")
    print("   • 并发安全性测试")
    print("")
    print("⚡ 使用命令运行: pytest backend/tests/test_json_validation.py -v")
