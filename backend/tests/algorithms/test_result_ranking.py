"""
结果排序步骤单元测试 - 类型安全版本
测试信号排序和优先级分配功能
"""

import pytest
from typing import Dict, List, Any, Tuple
from unittest.mock import Mock, patch
from datetime import datetime

from app.services.analysis.result_ranker import (
    ResultRankingStep,
    RankingCriteria,
    RankingResult,
    SignalScore,
)
from app.models.signal_pattern import SignalType
from app.models.analysis_pipeline import PipelineData, StepStatus
from app.core.analyzer_config import StepConfig

from .test_base import (
    create_test_pipeline_data,
    create_test_step_config,
    assert_pipeline_result,
)


class TestResultRanking:
    """测试结果排序功能"""

    @pytest.fixture
    def step_config(self) -> StepConfig:
        """创建步骤配置"""
        config = create_test_step_config("result_ranking")
        config.config_data = {
            "confidence_weight": 0.4,
            "relevance_weight": 0.3,
            "engagement_weight": 0.3,
            "top_k_results": 10,
        }
        return config

    @pytest.fixture
    def ranker(self, step_config: StepConfig) -> ResultRankingStep:
        """创建排序器实例"""
        return ResultRankingStep(step_config)

    @pytest.fixture
    def mock_signals(self) -> List[Dict[str, Any]]:
        """创建模拟信号数据"""
        return [
            {
                "signal_type": "PAIN_POINT",
                "content": "App crashes frequently",
                "confidence": 0.9,
                "sentiment_score": -0.7,
                "source_post_id": "post1",
                "subreddit": "r/tech",
                "matched_keywords": ["crash", "broken"],
                "context_metadata": {
                    "score": 500,
                    "comment_count": 100,
                    "title": "Major issue with app",
                },
            },
            {
                "signal_type": "COMPETITOR",
                "content": "Looking for Slack alternative",
                "confidence": 0.8,
                "sentiment_score": 0.0,
                "source_post_id": "post2",
                "subreddit": "r/productivity",
                "matched_keywords": ["alternative", "better"],
                "context_metadata": {
                    "score": 300,
                    "comment_count": 50,
                    "title": "Need team communication tool",
                },
            },
            {
                "signal_type": "OPPORTUNITY",
                "content": "AI integration would be amazing",
                "confidence": 0.7,
                "sentiment_score": 0.5,
                "source_post_id": "post3",
                "subreddit": "r/startups",
                "matched_keywords": ["feature", "idea"],
                "context_metadata": {
                    "score": 1000,
                    "comment_count": 200,
                    "title": "Feature suggestion",
                },
            },
            {
                "signal_type": "PAIN_POINT",
                "content": "UI is confusing",
                "confidence": 0.6,
                "sentiment_score": -0.4,
                "source_post_id": "post4",
                "subreddit": "r/design",
                "matched_keywords": ["confusing", "difficult"],
                "context_metadata": {
                    "score": 150,
                    "comment_count": 30,
                    "title": "UX problems",
                },
            },
        ]

    @pytest.mark.asyncio
    async def test_ranking_success(
        self, ranker: ResultRankingStep, mock_signals: List[Dict[str, Any]]
    ) -> None:
        """测试成功排序信号"""
        # 准备管道数据
        pipeline_data = create_test_pipeline_data()
        pipeline_data.intermediate_results["signal_extraction"] = {
            "signals": mock_signals,
            "total_signals": len(mock_signals),
        }

        # 执行排序
        result = await ranker._process_step(pipeline_data)

        # 验证结果
        assert_pipeline_result(result, StepStatus.COMPLETED, True)
        assert "ranked_signals" in result.data
        assert len(result.data["ranked_signals"]) == len(mock_signals)

        # 验证排序（高分在前）
        ranked = result.data["ranked_signals"]
        scores = [s["final_score"] for s in ranked]
        assert scores == sorted(scores, reverse=True)

        # 验证统计信息
        assert "ranking_summary" in result.data
        summary = result.data["ranking_summary"]
        assert summary["total_ranked"] == 4
        assert "avg_score" in summary
        assert "score_distribution" in summary

    def test_calculate_signal_score(self, ranker: ResultRankingStep) -> None:
        """测试信号评分计算"""
        signal = {
            "confidence": 0.8,
            "context_metadata": {"score": 500, "comment_count": 100},
            "matched_keywords": ["keyword1", "keyword2", "keyword3"],
        }

        score = ranker._calculate_signal_score(
            signal, weights=(0.4, 0.3, 0.3)  # confidence, relevance, engagement
        )

        assert isinstance(score, SignalScore)
        assert 0 <= score.confidence_score <= 1
        assert 0 <= score.relevance_score <= 1
        assert 0 <= score.engagement_score <= 1
        assert 0 <= score.final_score <= 1

        # 验证权重应用
        expected = (
            score.confidence_score * 0.4
            + score.relevance_score * 0.3
            + score.engagement_score * 0.3
        )
        assert abs(score.final_score - expected) < 0.01

    def test_normalize_engagement_score(self, ranker: ResultRankingStep) -> None:
        """测试参与度分数标准化"""
        # 高参与度
        high_engagement = ranker._normalize_engagement_score(1000, 200)
        assert high_engagement > 0.8

        # 中等参与度
        medium_engagement = ranker._normalize_engagement_score(100, 20)
        assert 0.3 < medium_engagement < 0.7

        # 低参与度
        low_engagement = ranker._normalize_engagement_score(10, 2)
        assert low_engagement < 0.3

    def test_apply_signal_type_boost(self, ranker: ResultRankingStep) -> None:
        """测试信号类型加权"""
        base_score = 0.5

        # 痛点信号应该有更高权重
        pain_score = ranker._apply_signal_type_boost(base_score, "PAIN_POINT")
        assert pain_score > base_score

        # 机会信号权重适中
        opp_score = ranker._apply_signal_type_boost(base_score, "OPPORTUNITY")
        assert opp_score >= base_score

        # 竞品信号权重较低
        comp_score = ranker._apply_signal_type_boost(base_score, "COMPETITOR")
        assert comp_score <= pain_score

    def test_filter_top_k_results(
        self, ranker: ResultRankingStep, mock_signals: List[Dict[str, Any]]
    ) -> None:
        """测试Top-K结果筛选"""
        # 添加分数
        for i, signal in enumerate(mock_signals):
            signal["final_score"] = (len(mock_signals) - i) * 0.2

        # 筛选Top 2
        top_2 = ranker._filter_top_k_results(mock_signals, k=2)
        assert len(top_2) == 2
        assert top_2[0]["final_score"] >= top_2[1]["final_score"]

        # 验证是否选择了最高分的信号
        all_scores = [s["final_score"] for s in mock_signals]
        top_scores = [s["final_score"] for s in top_2]
        assert top_scores[0] == max(all_scores)

    def test_generate_ranking_summary(self, ranker: ResultRankingStep) -> None:
        """测试排序摘要生成"""
        ranked_signals = [
            {"signal_type": "PAIN_POINT", "final_score": 0.9},
            {"signal_type": "OPPORTUNITY", "final_score": 0.8},
            {"signal_type": "PAIN_POINT", "final_score": 0.7},
            {"signal_type": "COMPETITOR", "final_score": 0.6},
        ]

        summary = ranker._generate_ranking_summary(ranked_signals)

        assert summary["total_ranked"] == 4
        assert summary["avg_score"] == 0.75
        assert summary["top_signal_type"] == "PAIN_POINT"

        # 验证分布统计
        distribution = summary["score_distribution"]
        assert distribution["high_confidence"] == 2  # >= 0.8
        assert distribution["medium_confidence"] == 1  # 0.5-0.8
        assert distribution["low_confidence"] == 1  # < 0.5

        # 验证类型统计
        by_type = summary["by_type"]
        assert by_type["PAIN_POINT"] == 2
        assert by_type["OPPORTUNITY"] == 1
        assert by_type["COMPETITOR"] == 1

    @pytest.mark.asyncio
    async def test_empty_signals_handling(self, ranker: ResultRankingStep) -> None:
        """测试空信号处理"""
        pipeline_data = create_test_pipeline_data()
        pipeline_data.intermediate_results["signal_extraction"] = {
            "signals": [],
            "total_signals": 0,
        }

        result = await ranker._process_step(pipeline_data)

        assert_pipeline_result(result, StepStatus.FAILED, False)
        assert "error" in result.data
        assert "信号" in result.data["error"]

    def test_ranking_stability(self, ranker: ResultRankingStep) -> None:
        """测试排序稳定性"""
        # 创建相同分数的信号
        signals = [
            {
                "id": f"signal_{i}",
                "confidence": 0.8,
                "context_metadata": {"score": 100, "comment_count": 10},
                "matched_keywords": ["test"],
            }
            for i in range(5)
        ]

        # 多次排序应该保持稳定顺序
        results = []
        for _ in range(3):
            scores = [
                ranker._calculate_signal_score(s, (0.5, 0.3, 0.2)) for s in signals
            ]
            ranked = sorted(
                zip(signals, scores), key=lambda x: x[1].final_score, reverse=True
            )
            results.append([s["id"] for s, _ in ranked])

        # 验证顺序一致性
        assert results[0] == results[1] == results[2]


@pytest.mark.integration
class TestResultRankingIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_full_ranking_pipeline(self) -> None:
        """测试完整排序流程"""
        config = create_test_step_config("result_ranking")
        ranker = ResultRankingStep(config)

        # 创建大量信号进行排序
        signals = []
        for i in range(100):
            signal_type = ["PAIN_POINT", "COMPETITOR", "OPPORTUNITY"][i % 3]
            signals.append(
                {
                    "signal_type": signal_type,
                    "content": f"Signal content {i}",
                    "confidence": 0.5 + (i % 50) * 0.01,
                    "sentiment_score": -0.5 + (i % 100) * 0.01,
                    "source_post_id": f"post_{i}",
                    "subreddit": f"r/sub_{i % 10}",
                    "matched_keywords": [f"keyword_{j}" for j in range(i % 5 + 1)],
                    "context_metadata": {
                        "score": 100 + i * 10,
                        "comment_count": 10 + i % 50,
                        "title": f"Post title {i}",
                    },
                }
            )

        pipeline_data = create_test_pipeline_data()
        pipeline_data.intermediate_results["signal_extraction"] = {
            "signals": signals,
            "total_signals": len(signals),
        }

        result = await ranker._process_step(pipeline_data)

        assert result.success
        assert len(result.data["ranked_signals"]) == 100

        # 验证Top 10
        top_10 = result.data["ranked_signals"][:10]
        assert all(s["final_score"] >= 0.5 for s in top_10)

        # 验证排序正确性
        for i in range(len(top_10) - 1):
            assert top_10[i]["final_score"] >= top_10[i + 1]["final_score"]

        # 验证摘要统计
        summary = result.data["ranking_summary"]
        assert summary["total_ranked"] == 100
        assert 0 < summary["avg_score"] < 1
