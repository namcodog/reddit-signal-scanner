"""
分析算法直接测试 - Linus架构师批准版本

设计原则：
- 数据结构优先：直接测试算法，不测试Mock
- 消除特殊情况：统一测试模式处理所有信号类型
- 类型安全：零容忍Any类型
- 简洁胜过聪明：输入→算法→输出验证

测试的算法组件：
1. RedditContextAdapter - Reddit文本处理算法
2. UnifiedSignalDetector - 统一信号检测算法
"""

from dataclasses import dataclass
from typing import List

import pytest

from app.models.signal_pattern import (
    DEFAULT_SIGNAL_PATTERNS,
    RedditPost,
    SignalType,
)
from app.services.analysis.signal_extractor import (
    RedditContextAdapter,
    UnifiedSignalDetector,
)


@dataclass
class AlgorithmTestCase:
    """算法测试用例 - 具体类型定义，无Any"""

    input_text: str
    expected_signal_type: SignalType
    expected_confidence_min: float
    expected_keywords: List[str]
    description: str


@dataclass
class TextNormalizationTestCase:
    """文本标准化测试用例"""

    input_text: str
    expected_output: str
    description: str


class TestRedditContextAdapter:
    """Reddit语境适配器算法测试"""

    def setup_method(self) -> None:
        """测试准备 - 创建适配器实例"""
        self.adapter = RedditContextAdapter()

    @pytest.mark.parametrize(
        "test_case",
        [
            TextNormalizationTestCase(
                input_text="This is a TEST with UPPERCASE",
                expected_output="this is a test with uppercase",
                description="基础大小写转换",
            ),
            TextNormalizationTestCase(
                input_text="tbh imo this is great",
                expected_output="to be honest in my opinion this is great",
                description="Reddit缩写展开",
            ),
            TextNormalizationTestCase(
                input_text="TBH, IMO this app sucks! tl;dr: broken",
                expected_output="to be honest  in my opinion this app sucks! too long didn t read  broken",
                description="复合缩写+符号清理",
            ),
        ],
    )
    def test_normalize_text_algorithm(
        self, test_case: TextNormalizationTestCase
    ) -> None:
        """测试文本标准化算法"""
        result = self.adapter.normalize_text(test_case.input_text)
        assert result == test_case.expected_output, f"测试失败: {test_case.description}"

    @pytest.mark.parametrize(
        "sarcastic_text,expected_result",
        [
            ("Oh absolutely brilliant work /s", True),
            ("Totally perfect, clearly the best solution", True),  # 2+ indicators
            ("Obviously great, definitely works", True),  # 2+ indicators
            ("This is actually good work", False),
            ("I think this is great", False),
            ("Looks good to me", False),
        ],
    )
    def test_detect_sarcasm_algorithm(
        self, sarcastic_text: str, expected_result: bool
    ) -> None:
        """测试讽刺检测算法"""
        result = self.adapter.detect_sarcasm(sarcastic_text)
        assert result == expected_result, f"讽刺检测错误: {sarcastic_text}"

    def test_extract_reddit_features_algorithm(self) -> None:
        """测试Reddit特征提取算法"""
        text = "I'm so frustrated with this app, it's better than the old one though"
        features = self.adapter.extract_reddit_features(text)

        # 验证返回的特征结构
        assert isinstance(features, dict)
        assert "reddit_frustration" in features
        assert "reddit_comparison" in features

        # 验证特征值范围 [0.0, 1.0]
        for feature_name, value in features.items():
            assert 0.0 <= value <= 1.0, f"特征值超出范围: {feature_name}={value}"


class TestUnifiedSignalDetector:
    """统一信号检测器算法测试"""

    def setup_method(self) -> None:
        """测试准备 - 创建检测器实例"""
        self.detector = UnifiedSignalDetector(DEFAULT_SIGNAL_PATTERNS)

    @pytest.mark.parametrize(
        "test_case",
        [
            AlgorithmTestCase(
                input_text="This app sucks and is terrible, my complaint is that it's broken",
                expected_signal_type=SignalType.PAIN_POINT,
                expected_confidence_min=0.4,
                expected_keywords=["sucks", "terrible", "broken"],
                description="痛点检测算法",
            ),
            AlgorithmTestCase(
                input_text="Looking for alternative to Slack vs Zoom comparison, need something better than current tools",
                expected_signal_type=SignalType.COMPETITOR,
                expected_confidence_min=0.3,
                expected_keywords=["alternative", "vs", "better than"],
                description="竞争对手分析算法",
            ),
            AlgorithmTestCase(
                input_text="Wish there was a great solution for this unmet_need, missing this awesome feature would pay for it",
                expected_signal_type=SignalType.OPPORTUNITY,
                expected_confidence_min=0.3,
                expected_keywords=[
                    "wish there was",
                    "need",
                    "missing",
                    "would pay for",
                ],
                description="机会发现算法",
            ),
        ],
    )
    def test_signal_detection_algorithm(self, test_case: AlgorithmTestCase) -> None:
        """统一信号检测算法测试 - 消除特殊情况分支"""
        # 创建测试Reddit帖子
        reddit_post = RedditPost(
            id=f"test_post_{test_case.expected_signal_type.value}",
            title=f"Test {test_case.description}",
            content=test_case.input_text,
            subreddit="r/test",
            score=100,
            comment_count=20,
        )

        # 执行核心算法
        signals = self.detector.extract_signals([reddit_post])

        # 验证算法输出
        assert len(signals) > 0, f"算法未检测到信号: {test_case.description}"

        signal = signals[0]
        assert (
            signal.signal_type == test_case.expected_signal_type
        ), f"信号类型错误: expected={test_case.expected_signal_type}, actual={signal.signal_type}"

        assert (
            signal.confidence >= test_case.expected_confidence_min
        ), f"置信度过低: expected>={test_case.expected_confidence_min}, actual={signal.confidence}"

        # 验证关键词匹配
        matched_keywords = [kw.lower() for kw in signal.matched_keywords]
        for expected_kw in test_case.expected_keywords:
            assert any(
                expected_kw.lower() in matched_kw for matched_kw in matched_keywords
            ), f"缺少关键词: {expected_kw} in {matched_keywords}"

    def test_sentiment_analysis_algorithm(self) -> None:
        """情感分析算法测试"""
        # 正面情感
        positive_score = self.detector._simple_sentiment_analysis(
            "this is amazing and excellent work"
        )
        assert positive_score > 0, "正面情感分析错误"

        # 负面情感
        negative_score = self.detector._simple_sentiment_analysis(
            "this is terrible and awful experience"
        )
        assert negative_score < 0, "负面情感分析错误"

        # 中性情感
        neutral_score = self.detector._simple_sentiment_analysis(
            "this is a regular post about something"
        )
        assert -0.3 <= neutral_score <= 0.3, "中性情感分析错误"

    def test_confidence_calculation_algorithm(self) -> None:
        """置信度计算算法测试"""
        pattern = self.detector.patterns[0]  # PAIN_POINT pattern

        # 高置信度场景
        high_confidence = self.detector._calculate_confidence(
            keyword_matches=3,
            sentiment_score=-0.7,
            pattern=pattern,
            text_features={"reddit_frustration": 0.8},
        )
        assert high_confidence > 0.4, "高置信度计算错误"

        # 低置信度场景
        low_confidence = self.detector._calculate_confidence(
            keyword_matches=1, sentiment_score=0.2, pattern=pattern, text_features={}
        )
        assert low_confidence < 0.5, "低置信度计算错误"

    def test_keyword_matching_algorithm(self) -> None:
        """关键词匹配算法测试"""
        text = "This application is broken and has serious problems"
        keywords = ["broken", "problem", "issue", "bug"]

        matches = self.detector._count_keyword_matches(text, keywords)
        assert matches >= 2, f"关键词匹配算法错误: expected>=2, actual={matches}"


@pytest.mark.integration
class TestAlgorithmIntegration:
    """算法集成测试 - 验证完整算法链条"""

    def test_complete_signal_extraction_pipeline(self) -> None:
        """完整信号提取算法管道测试"""
        # 创建真实测试数据 - 每种信号类型的典型Reddit帖子
        reddit_posts = [
            RedditPost(
                id="pain_001",
                title="App crashes constantly",
                content="This app sucks and is awful, my complaint is that it's broken and crashes constantly",
                subreddit="r/bugs",
                score=45,
                comment_count=12,
            ),
            RedditPost(
                id="competitor_001",
                title="Alternative to current tool",
                content="Looking for alternative to current tool vs others comparison, need something better than what we have",
                subreddit="r/alternatives",
                score=67,
                comment_count=23,
            ),
            RedditPost(
                id="opportunity_001",
                title="Feature request",
                content="Wish there was a great solution for this unmet_need, missing this awesome functionality would pay for it",
                subreddit="r/ideas",
                score=89,
                comment_count=34,
            ),
        ]

        # 执行完整算法管道
        detector = UnifiedSignalDetector(DEFAULT_SIGNAL_PATTERNS)
        signals = detector.extract_signals(reddit_posts)

        # 验证算法输出质量
        assert len(signals) >= 3, "算法管道未产生足够信号"

        # 验证信号类型分布
        signal_types = {signal.signal_type for signal in signals}
        assert SignalType.PAIN_POINT in signal_types, "缺少痛点信号"
        assert SignalType.COMPETITOR in signal_types, "缺少竞争者信号"
        assert SignalType.OPPORTUNITY in signal_types, "缺少机会信号"

        # 验证信号质量
        high_confidence_signals = [s for s in signals if s.confidence > 0.3]
        assert len(high_confidence_signals) > 0, "高置信度信号数量不足"

        # 验证每个信号的完整性
        for signal in signals:
            assert signal.source_post_id is not None
            assert signal.source_post_id.startswith(
                ("pain_", "competitor_", "opportunity_")
            )
            assert len(signal.matched_keywords) > 0
            assert signal.content is not None and len(signal.content) > 0
            assert 0.0 <= signal.confidence <= 1.0
            assert -1.0 <= signal.sentiment_score <= 1.0
