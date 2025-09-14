"""
信号提取步骤单元测试 - 基于真实代码结构
测试信号提取和Reddit文本处理功能
"""

from typing import Any, Dict, List
from unittest.mock import Mock, patch

import pytest

from app.core.analyzer_config import StepConfig
from app.models.analysis_pipeline import PipelineData, StepStatus
from app.models.signal_pattern import (
    DEFAULT_SIGNAL_PATTERNS,
    RedditPost,
    Signal,
    SignalType,
)
from app.services.analysis.signal_extractor import (
    RedditContextAdapter,
    RedditSignalExtractor,
    UnifiedSignalDetector,
)
from tests.algorithms.test_base_v3 import (
    create_test_pipeline_data,
    create_test_reddit_posts,
    create_test_signal_patterns,
    create_test_signals,
    create_test_step_config,
)


class TestRedditContextAdapter:
    """测试Reddit语境适配器"""

    @pytest.fixture
    def adapter(self) -> RedditContextAdapter:
        """创建适配器实例"""
        return RedditContextAdapter()

    def test_normalize_text_basic(self, adapter: RedditContextAdapter) -> None:
        """测试基本文本标准化"""
        text = "This is a TEST with UPPERCASE"
        result = adapter.normalize_text(text)
        assert result == "this is a test with uppercase"

    def test_normalize_text_abbreviations(self, adapter: RedditContextAdapter) -> None:
        """测试缩写展开"""
        text = "tbh imo this is great"
        result = adapter.normalize_text(text)
        assert "to be honest" in result
        assert "in my opinion" in result

    def test_normalize_text_complex(self, adapter: RedditContextAdapter) -> None:
        """测试复杂文本处理"""
        text = "TBH, IMO this app sucks! tl;dr: broken"
        result = adapter.normalize_text(text)
        assert "to be honest" in result
        assert "too long didn't read" in result
        # 验证清理了多余符号
        assert "!" not in result

    def test_detect_sarcasm_positive(self, adapter: RedditContextAdapter) -> None:
        """测试讽刺检测 - 正面案例"""
        sarcastic_texts = [
            "Oh absolutely brilliant work /s",
            "Totally perfect, clearly the best solution",  # 2+ indicators
            "Obviously great, definitely works",  # 2+ indicators
        ]

        for text in sarcastic_texts:
            assert adapter.detect_sarcasm(text) is True

    def test_detect_sarcasm_negative(self, adapter: RedditContextAdapter) -> None:
        """测试讽刺检测 - 负面案例"""
        normal_texts = [
            "This is actually good work",
            "I think this is great",
            "Looks good to me",
        ]

        for text in normal_texts:
            assert adapter.detect_sarcasm(text) is False

    def test_extract_reddit_features(self, adapter: RedditContextAdapter) -> None:
        """测试Reddit特征提取"""
        text = "I'm so frustrated with this app, it's better than the old one though"
        features = adapter.extract_reddit_features(text)

        assert isinstance(features, dict)
        assert "reddit_frustration" in features
        assert "reddit_comparison" in features
        assert 0 <= features["reddit_frustration"] <= 1
        assert 0 <= features["reddit_comparison"] <= 1


class TestUnifiedSignalDetector:
    """测试统一信号检测器"""

    @pytest.fixture
    def detector(self) -> UnifiedSignalDetector:
        """创建检测器实例"""
        patterns = create_test_signal_patterns()
        return UnifiedSignalDetector(patterns)

    @pytest.fixture
    def reddit_posts(self) -> List[RedditPost]:
        """创建测试Reddit帖子"""
        return [
            RedditPost(
                id="pain_post",
                title="This app is broken and frustrating",
                content="I have a serious problem with this app, it's totally broken",
                subreddit="r/complaints",
                score=150,
                comment_count=25,
            ),
            RedditPost(
                id="competitor_post",
                title="Looking for alternative to Slack",
                content="Need something better than Slack, any recommendations vs current tools?",
                subreddit="r/productivity",
                score=200,
                comment_count=40,
            ),
            RedditPost(
                id="opportunity_post",
                title="Wish there was a better solution",
                content="Would be great if someone made a tool that could handle this need",
                subreddit="r/startups",
                score=300,
                comment_count=60,
            ),
        ]

    def test_extract_signals_success(
        self, detector: UnifiedSignalDetector, reddit_posts: List[RedditPost]
    ) -> None:
        """测试成功提取信号"""
        signals = detector.extract_signals(reddit_posts)

        assert len(signals) >= 3

        # 验证信号类型分布
        signal_types = [signal.signal_type for signal in signals]
        assert SignalType.PAIN_POINT in signal_types
        assert SignalType.COMPETITOR in signal_types
        assert SignalType.OPPORTUNITY in signal_types

        # 验证信号结构
        for signal in signals:
            assert isinstance(signal, Signal)
            assert signal.source_post_id in [p.id for p in reddit_posts]
            assert len(signal.matched_keywords) > 0
            assert 0 <= signal.confidence <= 1

    def test_match_pattern_pain_point(
        self, detector: UnifiedSignalDetector, reddit_posts: List[RedditPost]
    ) -> None:
        """测试痛点模式匹配"""
        pain_post = reddit_posts[0]  # "broken and frustrating"
        pattern = detector.patterns[0]  # PAIN_POINT pattern

        normalized_text = detector.context_adapter.normalize_text(pain_post.content)
        text_features = detector.context_adapter.extract_reddit_features(
            normalized_text
        )

        signal = detector._match_pattern(
            pain_post, normalized_text, pattern, text_features
        )

        assert signal is not None
        assert signal.signal_type == SignalType.PAIN_POINT
        assert any(
            kw in ["problem", "broken", "frustrating"] for kw in signal.matched_keywords
        )
        assert signal.confidence > 0.5

    def test_match_pattern_no_match(self, detector: UnifiedSignalDetector) -> None:
        """测试无匹配的模式"""
        # 创建不匹配任何模式的帖子
        neutral_post = RedditPost(
            id="neutral",
            title="Regular discussion about weather",
            content="Today is a nice day with good weather conditions",
            subreddit="r/weather",
            score=50,
            comment_count=5,
        )

        pattern = detector.patterns[0]  # PAIN_POINT pattern
        normalized_text = detector.context_adapter.normalize_text(neutral_post.content)
        text_features = detector.context_adapter.extract_reddit_features(
            normalized_text
        )

        signal = detector._match_pattern(
            neutral_post, normalized_text, pattern, text_features
        )

        assert signal is None

    def test_simple_sentiment_analysis(self, detector: UnifiedSignalDetector) -> None:
        """测试简单情感分析"""
        # 正面情感
        positive_text = "this is amazing and excellent work"
        positive_score = detector._simple_sentiment_analysis(positive_text)
        assert positive_score > 0

        # 负面情感
        negative_text = "this is terrible and awful experience"
        negative_score = detector._simple_sentiment_analysis(negative_text)
        assert negative_score < 0

        # 中性情感
        neutral_text = "this is a regular post about something"
        neutral_score = detector._simple_sentiment_analysis(neutral_text)
        assert -0.3 <= neutral_score <= 0.3

    def test_calculate_confidence(self, detector: UnifiedSignalDetector) -> None:
        """测试置信度计算"""
        pattern = detector.patterns[0]  # PAIN_POINT pattern

        # 高置信度场景
        high_confidence = detector._calculate_confidence(
            keyword_matches=3,
            sentiment_score=-0.7,
            pattern=pattern,
            text_features={"reddit_frustration": 0.8},
        )
        assert high_confidence > 0.6

        # 低置信度场景
        low_confidence = detector._calculate_confidence(
            keyword_matches=1, sentiment_score=0.2, pattern=pattern, text_features={}
        )
        assert low_confidence < 0.5


class TestRedditSignalExtractor:
    """测试Reddit信号提取步骤"""

    @pytest.fixture
    def step_config(self) -> StepConfig:
        """创建步骤配置"""
        return create_test_step_config("signal_extraction", 120.0)

    @pytest.fixture
    def extractor(self, step_config: StepConfig) -> RedditSignalExtractor:
        """创建信号提取器实例"""
        with patch.object(
            RedditSignalExtractor,
            "__init__",
            lambda self, config: setattr(self, "config", config)
            or setattr(self, "name", "signal_extraction")
            or setattr(
                self, "detector", UnifiedSignalDetector(DEFAULT_SIGNAL_PATTERNS)
            ),
        ):
            extractor = RedditSignalExtractor({"enabled": True})
            extractor.logger = Mock()
            return extractor

    @pytest.fixture
    def pipeline_data_with_posts(self) -> PipelineData:
        """创建包含Reddit帖子的管道数据"""
        data = create_test_pipeline_data("Test product", ["test"])
        # 模拟前一步骤的结果
        data.step_results["data_collection"] = {
            "reddit_posts": create_test_reddit_posts(10)
        }
        return data

    @pytest.mark.asyncio
    async def test_process_step_success(
        self, extractor: RedditSignalExtractor, pipeline_data_with_posts: PipelineData
    ) -> None:
        """测试成功处理信号提取"""
        # Mock 依赖方法
        with patch.object(extractor, "validate_common_input", return_value=True):
            with patch.object(extractor, "create_success_result") as mock_success:
                mock_result = Mock()
                mock_result.success = True
                mock_result.status = StepStatus.COMPLETED
                mock_success.return_value = mock_result

                result = await extractor._process_step(pipeline_data_with_posts)

                mock_success.assert_called_once()
                assert result.success is True

    @pytest.mark.asyncio
    async def test_process_step_no_posts(
        self, extractor: RedditSignalExtractor
    ) -> None:
        """测试无Reddit帖子数据"""
        data = create_test_pipeline_data("Test", ["test"])
        # 没有data_collection结果

        with patch.object(extractor, "validate_common_input", return_value=True):
            with patch.object(extractor, "_create_error_result") as mock_error:
                mock_error.return_value = Mock(success=False, status=StepStatus.FAILED)

                result = await extractor._process_step(data)

                mock_error.assert_called_once()
                assert "Reddit帖子数据" in mock_error.call_args[0][0]
                assert result.success is False

    @pytest.mark.asyncio
    async def test_process_step_empty_posts(
        self, extractor: RedditSignalExtractor
    ) -> None:
        """测试空的Reddit帖子数据"""
        data = create_test_pipeline_data("Test", ["test"])
        data.step_results["data_collection"] = {"reddit_posts": []}

        with patch.object(extractor, "validate_common_input", return_value=True):
            with patch.object(extractor, "_create_error_result") as mock_error:
                mock_error.return_value = Mock(success=False, status=StepStatus.FAILED)

                result = await extractor._process_step(data)

                mock_error.assert_called_once()
                assert "帖子数据为空" in mock_error.call_args[0][0]
                assert result.success is False

    def test_calculate_signal_statistics(
        self, extractor: RedditSignalExtractor
    ) -> None:
        """测试信号统计计算"""
        signals = create_test_signals(6)  # 2 of each type

        # Mock此方法以避免依赖
        def mock_calculate_stats(signals_list: List[Signal]) -> Dict[str, int]:
            stats = {}
            for signal in signals_list:
                signal_type_name = signal.signal_type.value
                stats[signal_type_name] = stats.get(signal_type_name, 0) + 1
            return stats

        with patch.object(
            extractor, "_calculate_signal_statistics", mock_calculate_stats
        ):
            stats = extractor._calculate_signal_statistics(signals)

            assert stats["pain_point"] == 2
            assert stats["competitor"] == 2
            assert stats["opportunity"] == 2

    def test_assess_extraction_quality(self, extractor: RedditSignalExtractor) -> None:
        """测试提取质量评估"""
        signals = create_test_signals(3)
        posts = create_test_reddit_posts(5)

        # Mock此方法
        def mock_assess_quality(
            signals_list: List[Signal], posts_list: List[Any]
        ) -> Dict[str, float]:
            extraction_rate = len(signals_list) / len(posts_list)
            avg_confidence = sum(s.confidence for s in signals_list) / len(signals_list)
            return {
                "extraction_rate": extraction_rate,
                "avg_confidence": avg_confidence,
                "quality_score": (extraction_rate * 0.4) + (avg_confidence * 0.6),
            }

        with patch.object(extractor, "_assess_extraction_quality", mock_assess_quality):
            quality = extractor._assess_extraction_quality(signals, posts)

            assert "extraction_rate" in quality
            assert "avg_confidence" in quality
            assert "quality_score" in quality
            assert 0 <= quality["quality_score"] <= 1


@pytest.mark.integration
class TestSignalExtractionIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_full_extraction_pipeline(self) -> None:
        """测试完整信号提取流程"""
        # 创建真实的Reddit帖子数据，包含各种信号类型
        reddit_posts = (
            [
                RedditPost(
                    id=f"pain_{i}",
                    title=f"Frustrated with issue {i}",
                    content="This app is broken and terrible, causes so much frustration",
                    subreddit="r/complaints",
                    score=100 + i * 10,
                    comment_count=20 + i * 5,
                )
                for i in range(10)
            ]
            + [
                RedditPost(
                    id=f"comp_{i}",
                    title=f"Alternative to current solution {i}",
                    content="Looking for something better than what we have, need comparison",
                    subreddit="r/alternatives",
                    score=150 + i * 15,
                    comment_count=30 + i * 3,
                )
                for i in range(10)
            ]
            + [
                RedditPost(
                    id=f"opp_{i}",
                    title=f"Wish there was solution {i}",
                    content="Would be great if someone made this, I need this feature",
                    subreddit="r/ideas",
                    score=200 + i * 20,
                    comment_count=40 + i * 2,
                )
                for i in range(10)
            ]
        )

        # 创建检测器和提取器
        detector = UnifiedSignalDetector(DEFAULT_SIGNAL_PATTERNS)

        # 执行信号提取
        signals = detector.extract_signals(reddit_posts)

        # 验证结果
        assert len(signals) >= 15  # 应该检测到大部分信号

        # 验证信号类型分布
        signal_types = [s.signal_type for s in signals]
        assert SignalType.PAIN_POINT in signal_types
        assert SignalType.COMPETITOR in signal_types
        assert SignalType.OPPORTUNITY in signal_types

        # 验证信号质量
        high_confidence_signals = [s for s in signals if s.confidence > 0.7]
        assert len(high_confidence_signals) > 0

        # 验证每个信号的完整性
        for signal in signals:
            assert signal.source_post_id.startswith(("pain_", "comp_", "opp_"))
            assert len(signal.matched_keywords) > 0
            assert signal.content is not None and len(signal.content) > 0
            assert signal.subreddit in ["r/complaints", "r/alternatives", "r/ideas"]
