"""
Reddit信号提取器单元测试

测试覆盖：
1. 三类信号检测准确性
2. Reddit语境适配效果
3. 配置驱动的统一处理逻辑
4. 性能基准验证
"""

import pytest
import asyncio
from unittest.mock import Mock, patch
from typing import List, Dict, Any

from app.services.analysis.signal_extractor import (
    RedditSignalExtractor,
    UnifiedSignalDetector,
    RedditContextAdapter,
    RedditTextMetrics,
)
from app.models.signal_pattern import (
    SignalPattern,
    Signal,
    SignalType,
    RedditPost,
    DEFAULT_SIGNAL_PATTERNS,
)
from app.models.analysis_pipeline import PipelineData, AnalysisConfig


class TestRedditContextAdapter:
    """Reddit语境适配器测试"""

    def setup_method(self):
        self.adapter = RedditContextAdapter()

    def test_normalize_text_handles_abbreviations(self):
        """测试缩写展开功能"""
        text = "tbh this sucks imo, totally broken"
        normalized = self.adapter.normalize_text(text)

        assert "to be honest" in normalized
        assert "in my opinion" in normalized
        assert "tbh" not in normalized
        assert "imo" not in normalized

    def test_sarcasm_detection_basic(self):
        """测试基础讽刺检测"""
        # 明确的讽刺标记
        assert self.adapter.detect_sarcasm("Great job breaking the app /s")

        # 多个讽刺指示词
        assert self.adapter.detect_sarcasm(
            "totally awesome and definitely working perfectly"
        )

        # 正常文本
        assert not self.adapter.detect_sarcasm("This is a good product")

    def test_reddit_pattern_extraction(self):
        """测试Reddit特色模式识别"""
        text = "This is better than that other tool, try checking out the new version"
        features = self.adapter.extract_reddit_features(text)

        assert features["reddit_comparison"] > 0
        assert features["reddit_recommendation"] > 0
        assert "reddit_frustration" in features


class TestUnifiedSignalDetector:
    """统一信号检测器测试"""

    def setup_method(self):
        # 创建测试专用的信号模式
        self.test_patterns = [
            SignalPattern(
                signal_type=SignalType.PAIN_POINT,
                keywords=["broken", "sucks", "terrible"],
                sentiment_threshold=-0.5,
                confidence_weight=0.9,
            ),
            SignalPattern(
                signal_type=SignalType.COMPETITOR,
                keywords=["better than", "alternative", "compared to"],
                sentiment_threshold=0.0,
                confidence_weight=0.8,
            ),
            SignalPattern(
                signal_type=SignalType.OPPORTUNITY,
                keywords=["need", "want", "missing"],
                sentiment_threshold=0.2,
                confidence_weight=0.7,
            ),
        ]
        self.detector = UnifiedSignalDetector(self.test_patterns)

    def create_test_post(
        self, content: str, score: int = 10, subreddit: str = "test"
    ) -> RedditPost:
        """创建测试用Reddit帖子"""
        return RedditPost(
            id=f"test_{hash(content)}",
            title="Test Post",
            content=content,
            score=score,
            subreddit=subreddit,
            author="test_user",
            created_utc=1234567890,
            permalink="/r/test/comments/test",
            comment_count=5,
        )

    def test_pain_point_signal_detection(self):
        """测试痛点信号检测"""
        posts = [
            self.create_test_post("This app is broken and terrible, nothing works"),
            self.create_test_post("Love this feature, works perfectly"),  # 不应该匹配
            self.create_test_post("The interface sucks but has potential"),
        ]

        signals = self.detector.extract_signals(posts)

        # 筛选痛点信号
        pain_signals = [s for s in signals if s.signal_type == SignalType.PAIN_POINT]

        assert len(pain_signals) >= 2
        assert all(s.confidence > 0.3 for s in pain_signals)
        assert all(
            "broken" in s.content.lower()
            or "sucks" in s.content.lower()
            or "terrible" in s.content.lower()
            for s in pain_signals
        )

    def test_competitor_signal_detection(self):
        """测试竞品信号检测"""
        posts = [
            self.create_test_post("This is better than Slack for team communication"),
            self.create_test_post(
                "Looking for an alternative to Zoom that actually works"
            ),
            self.create_test_post("Just regular discussion about features"),  # 不应该匹配
        ]

        signals = self.detector.extract_signals(posts)

        # 筛选竞品信号
        competitor_signals = [
            s for s in signals if s.signal_type == SignalType.COMPETITOR
        ]

        assert len(competitor_signals) >= 2
        assert all(s.confidence > 0.2 for s in competitor_signals)

    def test_opportunity_signal_detection(self):
        """测试机会信号检测"""
        posts = [
            self.create_test_post(
                "Really need a tool that can handle large files efficiently"
            ),
            self.create_test_post(
                "Want something that integrates with existing workflows"
            ),
            self.create_test_post("Missing feature for batch processing"),
        ]

        signals = self.detector.extract_signals(posts)

        # 筛选机会信号
        opportunity_signals = [
            s for s in signals if s.signal_type == SignalType.OPPORTUNITY
        ]

        assert len(opportunity_signals) >= 3
        assert all(s.confidence > 0.1 for s in opportunity_signals)

    def test_unified_processing_logic(self):
        """测试统一处理逻辑 - 确保三类信号使用相同的处理流程"""
        # 创建包含所有三类信号的混合数据
        posts = [
            self.create_test_post("This broken app sucks and is terrible"),  # 痛点
            self.create_test_post("Much better than the competition"),  # 竞品
            self.create_test_post("Really need this missing feature"),  # 机会
        ]

        signals = self.detector.extract_signals(posts)

        # 验证每种信号类型都被检测到
        signal_types = {signal.signal_type for signal in signals}
        assert SignalType.PAIN_POINT in signal_types
        assert SignalType.COMPETITOR in signal_types
        assert SignalType.OPPORTUNITY in signal_types

        # 验证所有信号都有统一的结构
        for signal in signals:
            assert hasattr(signal, "confidence")
            assert hasattr(signal, "sentiment_score")
            assert hasattr(signal, "metadata")
            assert 0.0 <= signal.confidence <= 1.0
            assert -1.0 <= signal.sentiment_score <= 1.0

    def test_sarcasm_confidence_adjustment(self):
        """测试讽刺检测对置信度的影响"""
        posts = [
            self.create_test_post("This is totally broken /s"),  # 讽刺
            self.create_test_post("This is totally broken"),  # 非讽刺
        ]

        signals = self.detector.extract_signals(posts)

        # 找到两个信号（假设都被检测为痛点信号）
        if len(signals) >= 2:
            sarcastic_signal = next((s for s in signals if "/s" in s.content), None)
            non_sarcastic_signal = next(
                (s for s in signals if "/s" not in s.content), None
            )

            if sarcastic_signal and non_sarcastic_signal:
                # 讽刺信号的置信度应该更低
                assert sarcastic_signal.confidence < non_sarcastic_signal.confidence

    def test_confidence_calculation_factors(self):
        """测试置信度计算的各个因子"""
        # 高质量信号：多关键词匹配，情感明确
        high_quality_post = self.create_test_post(
            "This app is broken, terrible, and completely sucks", score=100
        )

        # 低质量信号：单关键词，情感不明确
        low_quality_post = self.create_test_post(
            "This app is somewhat broken maybe", score=1
        )

        signals = self.detector.extract_signals([high_quality_post, low_quality_post])

        if len(signals) >= 2:
            high_confidence_signal = max(signals, key=lambda s: s.confidence)
            low_confidence_signal = min(signals, key=lambda s: s.confidence)

            assert high_confidence_signal.confidence > low_confidence_signal.confidence


class TestRedditSignalExtractor:
    """Reddit信号提取器集成测试"""

    def setup_method(self):
        self.extractor = RedditSignalExtractor()

    def create_test_pipeline_data(self) -> PipelineData:
        """创建测试用的流水线数据"""
        config = AnalysisConfig(product_description="Test product for data analysis")
        data = PipelineData(
            product_description="Test product for data analysis",
            target_keywords=["test", "product"],
            analysis_config=config,
            pipeline_id="test-pipeline-123",
            total_steps=4,
        )

        # 模拟数据收集步骤的输出
        test_posts = [
            RedditPost(
                id="post1",
                title="Pain point discussion",
                content="This tool is broken and sucks, very frustrating to use",
                score=50,
                subreddit="productivity",
                author="user1",
                created_utc=1234567890,
                permalink="/r/productivity/comments/post1",
                comment_count=10,
            ),
            RedditPost(
                id="post2",
                title="Competitor comparison",
                content="Much better than Notion, this alternative works perfectly",
                score=25,
                subreddit="tools",
                author="user2",
                created_utc=1234567891,
                permalink="/r/tools/comments/post2",
                comment_count=5,
            ),
            RedditPost(
                id="post3",
                title="Feature request",
                content="Really need a feature for batch processing, currently missing",
                score=75,
                subreddit="requests",
                author="user3",
                created_utc=1234567892,
                permalink="/r/requests/comments/post3",
                comment_count=15,
            ),
        ]

        # 添加数据收集结果
        data.step_results["data_collection"] = {
            "reddit_posts": test_posts,
            "total_posts": len(test_posts),
            "cache_hit_rate": 0.8,
        }

        return data

    @pytest.mark.asyncio
    async def test_successful_signal_extraction(self):
        """测试成功的信号提取流程"""
        data = self.create_test_pipeline_data()

        result = await self.extractor.execute(data)

        assert result.success is True
        assert result.step_name == "signal_extraction"
        assert "signals" in result.data
        assert "statistics" in result.data
        assert "quality_metrics" in result.data

        signals = result.data["signals"]
        assert len(signals) > 0

        # 验证信号结构
        for signal in signals:
            assert "signal_type" in signal
            assert "content" in signal
            assert "confidence" in signal
            assert "sentiment_score" in signal
            assert "metadata" in signal

    @pytest.mark.asyncio
    async def test_signal_statistics_calculation(self):
        """测试信号统计计算"""
        data = self.create_test_pipeline_data()

        result = await self.extractor.execute(data)

        assert result.success is True

        stats = result.data["statistics"]
        total_signals = sum(stats.values())

        assert total_signals > 0
        assert all(count >= 0 for count in stats.values())

    @pytest.mark.asyncio
    async def test_quality_metrics_assessment(self):
        """测试质量指标评估"""
        data = self.create_test_pipeline_data()

        result = await self.extractor.execute(data)

        assert result.success is True

        quality_metrics = result.data["quality_metrics"]

        assert "extraction_rate" in quality_metrics
        assert "avg_confidence" in quality_metrics
        assert "quality_score" in quality_metrics

        # 验证指标范围
        assert 0.0 <= quality_metrics["extraction_rate"] <= 1.0
        assert 0.0 <= quality_metrics["avg_confidence"] <= 1.0
        assert 0.0 <= quality_metrics["quality_score"] <= 1.0

    @pytest.mark.asyncio
    async def test_error_handling_no_reddit_data(self):
        """测试缺少Reddit数据的错误处理"""
        config = AnalysisConfig(product_description="Test product")
        data = PipelineData(
            product_description="Test product",
            target_keywords=["test"],
            analysis_config=config,
            pipeline_id="test-pipeline-error",
            total_steps=4,
        )

        # 不添加data_collection结果，模拟缺少数据的情况

        result = await self.extractor.execute(data)

        assert result.success is False
        assert "未找到Reddit帖子数据" in result.data.get("error", "")

    @pytest.mark.asyncio
    async def test_error_handling_empty_posts(self):
        """测试空帖子数据的错误处理"""
        config = AnalysisConfig(product_description="Test product")
        data = PipelineData(
            product_description="Test product",
            target_keywords=["test"],
            analysis_config=config,
            pipeline_id="test-pipeline-empty",
            total_steps=4,
        )

        # 添加空的Reddit帖子列表
        data.step_results["data_collection"] = {
            "reddit_posts": [],
            "total_posts": 0,
        }

        result = await self.extractor.execute(data)

        assert result.success is False
        assert "Reddit帖子数据为空" in result.data.get("error", "")

    @pytest.mark.asyncio
    async def test_custom_signal_patterns(self):
        """测试自定义信号模式"""
        # 创建自定义信号模式
        custom_patterns = [
            SignalPattern(
                signal_type=SignalType.PAIN_POINT,
                keywords=["buggy", "crashes"],
                sentiment_threshold=-0.7,
                confidence_weight=1.0,
            )
        ]

        extractor = RedditSignalExtractor(custom_patterns=custom_patterns)
        data = self.create_test_pipeline_data()

        # 修改测试数据，使用自定义关键词
        data.step_results["data_collection"]["reddit_posts"][
            0
        ].content = "This app is buggy and crashes frequently"

        result = await self.extractor.execute(data)

        assert result.success is True
        signals = result.data["signals"]

        # 应该能检测到使用自定义关键词的信号
        buggy_signals = [s for s in signals if "buggy" in s["content"].lower()]
        assert len(buggy_signals) > 0


class TestSignalExtractorPerformance:
    """信号提取器性能测试"""

    def setup_method(self):
        self.extractor = RedditSignalExtractor()

    def create_large_test_dataset(self, size: int) -> List[RedditPost]:
        """创建大规模测试数据集"""
        posts = []
        content_templates = [
            "This product is broken and terrible",
            "Much better than the competition",
            "Really need this missing feature",
            "Great tool but has some issues",
            "Perfect alternative to existing solutions",
        ]

        for i in range(size):
            content = content_templates[i % len(content_templates)] + f" - post {i}"
            posts.append(
                RedditPost(
                    id=f"perf_test_{i}",
                    title=f"Performance Test Post {i}",
                    content=content,
                    score=i % 100,
                    subreddit=f"test_{i % 10}",
                    author=f"user_{i % 50}",
                    created_utc=1234567890 + i,
                    permalink=f"/r/test/comments/post_{i}",
                    comment_count=i % 20,
                )
            )

        return posts

    @pytest.mark.asyncio
    async def test_performance_benchmark(self):
        """性能基准测试 - 1000条帖子应在60秒内处理完成"""
        import time

        # 创建1000条测试帖子
        large_dataset = self.create_large_test_dataset(1000)

        config = AnalysisConfig(product_description="Performance test product")
        data = PipelineData(
            product_description="Performance test product",
            target_keywords=["test"],
            analysis_config=config,
            pipeline_id="perf-test-pipeline",
            total_steps=4,
        )

        data.step_results["data_collection"] = {
            "reddit_posts": large_dataset,
            "total_posts": len(large_dataset),
            "cache_hit_rate": 0.8,
        }

        start_time = time.time()
        result = await self.extractor.execute(data)
        end_time = time.time()

        processing_time = end_time - start_time

        # 验证性能要求：1000条帖子在60秒内处理完成
        assert (
            processing_time < 60.0
        ), f"Processing took {processing_time:.2f}s, expected < 60s"
        assert result.success is True

        # 验证处理结果质量
        assert result.data["total_processed"] == 1000
        assert result.data["total_signals"] > 0

        print(f"性能测试结果：1000条帖子处理耗时 {processing_time:.2f}s")

    @pytest.mark.asyncio
    async def test_memory_usage_stability(self):
        """内存使用稳定性测试"""
        import gc
        import sys

        # 获取初始内存使用量
        gc.collect()
        initial_objects = len(gc.get_objects())

        # 多次执行小批量处理
        for batch in range(10):
            small_dataset = self.create_large_test_dataset(50)

            config = AnalysisConfig(product_description=f"Memory test batch {batch}")
            data = PipelineData(
                product_description=f"Memory test batch {batch}",
                target_keywords=["test"],
                analysis_config=config,
                pipeline_id=f"memory-test-{batch}",
                total_steps=4,
            )

            data.step_results["data_collection"] = {
                "reddit_posts": small_dataset,
                "total_posts": len(small_dataset),
            }

            result = await self.extractor.execute(data)
            assert result.success is True

            # 清理变量
            del small_dataset, data, result

        # 强制垃圾回收
        gc.collect()
        final_objects = len(gc.get_objects())

        # 验证没有严重的内存泄露
        object_growth = final_objects - initial_objects
        assert object_growth < 1000, f"可能存在内存泄露，对象增长: {object_growth}"


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "--tb=short"])
