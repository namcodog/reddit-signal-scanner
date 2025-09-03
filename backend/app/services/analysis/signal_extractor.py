"""
Reddit信号提取步骤 - 基于配置驱动的统一信号检测

设计理念：
- 数据结构优先：复用优雅的SignalPattern设计
- 消除特殊情况：三类信号使用统一处理逻辑
- 配置驱动：避免硬编码的条件分支
- Reddit语境适配：处理非正式语言特征
"""

import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from logging import getLogger

from app.core.step_base import BaseAnalysisStep, step_performance_monitor
from app.models.signal_pattern import (
    SignalPattern,
    Signal,
    DEFAULT_SIGNAL_PATTERNS,
    RedditPost,
)
from app.models.analysis_pipeline import PipelineData, PipelineResult, StepStatus


logger = getLogger(__name__)


@dataclass
class RedditTextMetrics:
    """Reddit文本特征指标"""

    sentiment_score: float  # [-1.0, 1.0]
    informal_ratio: float  # 非正式语言比率 [0.0, 1.0]
    keyword_density: float  # 关键词密度 [0.0, 1.0]
    engagement_score: float  # 互动活跃度 [0.0, 1.0]


class RedditContextAdapter:
    """Reddit语境适配器 - 处理非正式语言特征"""

    # Reddit常用缩写和俚语映射
    REDDIT_ABBREVIATIONS = {
        "tbh": "to be honest",
        "imo": "in my opinion",
        "imho": "in my humble opinion",
        "fwiw": "for what it's worth",
        "tl;dr": "too long didn't read",
        "eli5": "explain like i'm 5",
        "dae": "does anyone else",
        "til": "today i learned",
        "ftfy": "fixed that for you",
        "afaik": "as far as i know",
    }

    # 反讽/讽刺检测关键词
    SARCASM_INDICATORS = [
        "totally",
        "absolutely",
        "definitely",
        "clearly",
        "obviously",
        "/s",
        "not",
        "sure",
        "great job",
        "brilliant",
    ]

    # Reddit特色表达模式
    REDDIT_PATTERNS = {
        "frustration": r"\b(god|jesus|fuck|damn)\s+(this|that)\b",
        "excitement": r"\b(omg|wow|holy)\s+(shit|crap|cow)\b",
        "comparison": r"\b(better|worse)\s+than\s+\w+",
        "recommendation": r"\b(try|use|check\s+out)\s+\w+",
    }

    def normalize_text(self, text: str) -> str:
        """标准化Reddit文本 - 处理缩写、俚语、表情"""
        normalized = text.lower().strip()

        # 展开缩写
        for abbr, full in self.REDDIT_ABBREVIATIONS.items():
            normalized = re.sub(f"\\b{abbr}\\b", full, normalized)

        # 清理多余空白和符号
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = re.sub(r"[^\w\s\.\!\?]", " ", normalized)

        return normalized.strip()

    def detect_sarcasm(self, text: str) -> bool:
        """检测讽刺/反话"""
        text_lower = text.lower()
        sarcasm_count = sum(
            1 for indicator in self.SARCASM_INDICATORS if indicator in text_lower
        )

        # 简单规则：包含2个以上讽刺指示词，或明确的/s标记
        return sarcasm_count >= 2 or "/s" in text_lower

    def extract_reddit_features(self, text: str) -> Dict[str, float]:
        """提取Reddit特色特征"""
        features = {}
        text_lower = text.lower()

        for pattern_name, pattern in self.REDDIT_PATTERNS.items():
            matches = len(re.findall(pattern, text_lower))
            features[f"reddit_{pattern_name}"] = min(1.0, matches / 3.0)

        return features


class UnifiedSignalDetector:
    """统一信号检测器 - 消除三类信号的特殊处理逻辑"""

    def __init__(self, patterns: List[SignalPattern]):
        self.patterns = patterns
        self.context_adapter = RedditContextAdapter()

    def extract_signals(self, reddit_posts: List[RedditPost]) -> List[Signal]:
        """统一信号提取 - 无条件分支设计"""
        all_signals = []

        for post in reddit_posts:
            # 统一预处理
            normalized_text = self.context_adapter.normalize_text(post.content)
            text_features = self.context_adapter.extract_reddit_features(
                normalized_text
            )

            # 统一模式匹配 - 对所有信号模式使用相同逻辑
            for pattern in self.patterns:
                signal = self._match_pattern(
                    post, normalized_text, pattern, text_features
                )
                if signal:
                    all_signals.append(signal)

        return all_signals

    def _match_pattern(
        self,
        post: RedditPost,
        normalized_text: str,
        pattern: SignalPattern,
        text_features: Dict[str, float],
    ) -> Optional[Signal]:
        """模式匹配 - 统一处理逻辑"""

        # 关键词匹配
        keyword_matches = self._count_keyword_matches(normalized_text, pattern.keywords)
        if keyword_matches < pattern.min_keyword_matches:
            return None

        # 情感分析
        sentiment_score = self._simple_sentiment_analysis(normalized_text)
        if not self._meets_sentiment_threshold(
            sentiment_score, pattern.sentiment_threshold
        ):
            return None

        # 语境规则验证
        if not self._validate_context_rules(normalized_text, pattern.context_rules):
            return None

        # 计算置信度
        confidence = self._calculate_confidence(
            keyword_matches, sentiment_score, pattern, text_features
        )

        # 讽刺检测调整
        if self.context_adapter.detect_sarcasm(post.content):
            confidence *= 0.7  # 讽刺内容降低置信度

        return Signal(
            signal_type=pattern.signal_type,
            content=(
                post.content[:200] + "..." if len(post.content) > 200 else post.content
            ),
            matched_keywords=[
                kw for kw in pattern.keywords if kw.lower() in normalized_text.lower()
            ],
            confidence=confidence,
            sentiment_score=sentiment_score,
            source_post_id=post.id,
            subreddit=post.subreddit,
            context_metadata={
                "score": post.score,
                "comment_count": post.comment_count,
                "keyword_matches": keyword_matches,
                "text_features": text_features,
                "title": post.title,
            },
        )

    def _count_keyword_matches(self, text: str, keywords: List[str]) -> int:
        """统计关键词匹配数量"""
        text_lower = text.lower()
        return sum(1 for keyword in keywords if keyword.lower() in text_lower)

    def _simple_sentiment_analysis(self, text: str) -> float:
        """简单情感分析 - 避免重型NLP依赖"""
        positive_words = [
            "good",
            "great",
            "excellent",
            "love",
            "awesome",
            "perfect",
            "amazing",
        ]
        negative_words = [
            "bad",
            "terrible",
            "awful",
            "hate",
            "sucks",
            "broken",
            "frustrating",
        ]

        text_words = text.lower().split()
        positive_count = sum(1 for word in text_words if word in positive_words)
        negative_count = sum(1 for word in text_words if word in negative_words)

        total_words = len(text_words)
        if total_words == 0:
            return 0.0

        # 简单的情感评分 [-1.0, 1.0]
        sentiment = (positive_count - negative_count) / max(1, total_words) * 10
        return max(-1.0, min(1.0, sentiment))

    def _meets_sentiment_threshold(
        self, sentiment_score: float, threshold: float
    ) -> bool:
        """情感阈值检查"""
        if threshold < 0:  # 负面情感要求
            return sentiment_score <= threshold
        elif threshold > 0:  # 正面情感要求
            return sentiment_score >= threshold
        else:  # 中性情感
            return abs(sentiment_score) <= 0.3

    def _validate_context_rules(self, text: str, context_rules: List[str]) -> bool:
        """语境规则验证 - 简化实现"""
        if not context_rules:
            return True

        # 简单规则匹配（可扩展为更复杂的规则引擎）
        text_lower = text.lower()
        for rule in context_rules:
            if rule.lower() in text_lower:
                return True

        return len(context_rules) == 0  # 空规则默认通过

    def _calculate_confidence(
        self,
        keyword_matches: int,
        sentiment_score: float,
        pattern: SignalPattern,
        text_features: Dict[str, float],
    ) -> float:
        """置信度计算"""

        # 基础置信度：关键词匹配度
        keyword_confidence = min(1.0, keyword_matches / max(1, len(pattern.keywords)))

        # 情感匹配度
        sentiment_confidence = (
            1.0 - abs(sentiment_score - pattern.sentiment_threshold) / 2.0
        )
        sentiment_confidence = max(0.0, sentiment_confidence)

        # Reddit特征加权
        reddit_feature_boost = sum(text_features.values()) * 0.1

        # 综合置信度
        confidence = (
            keyword_confidence * 0.5
            + sentiment_confidence * 0.3
            + reddit_feature_boost * 0.2
        ) * pattern.confidence_weight

        return min(1.0, max(0.0, confidence))


class RedditSignalExtractor(BaseAnalysisStep):
    """Reddit信号提取步骤 - 配置驱动的统一处理"""

    def __init__(self, custom_patterns: Optional[List[SignalPattern]] = None):
        super().__init__()
        self.name = "signal_extraction"

        # 配置驱动：使用预定义模式或自定义模式
        self.signal_patterns = custom_patterns or DEFAULT_SIGNAL_PATTERNS
        self.detector = UnifiedSignalDetector(self.signal_patterns)

        logger.info(f"初始化信号提取器，加载{len(self.signal_patterns)}个信号模式")

    @step_performance_monitor
    async def execute(self, data: PipelineData) -> PipelineResult:
        """
        执行Reddit信号提取

        输入：包含Reddit帖子数据的PipelineData
        输出：包含三类商业信号的PipelineResult
        """

        # 输入验证
        if not self.validate_common_input(data):
            return self._create_error_result("输入数据验证失败")

        # 获取Reddit数据
        reddit_data = data.get_step_result("data_collection")
        if not reddit_data or "reddit_posts" not in reddit_data:
            return self._create_error_result("未找到Reddit帖子数据")

        reddit_posts = reddit_data["reddit_posts"]
        if not reddit_posts:
            return self._create_error_result("Reddit帖子数据为空")

        logger.info(f"开始处理{len(reddit_posts)}条Reddit帖子")

        try:
            # 信号提取 - 统一处理
            signals = self.detector.extract_signals(reddit_posts)

            # 按信号类型分组统计
            signal_stats = self._calculate_signal_statistics(signals)

            # 质量评估
            quality_metrics = self._assess_extraction_quality(signals, reddit_posts)

            # 构建结果
            result_data = {
                "signals": [self._signal_to_dict(signal) for signal in signals],
                "statistics": signal_stats,
                "quality_metrics": quality_metrics,
                "total_processed": len(reddit_posts),
                "total_signals": len(signals),
            }

            logger.info(
                f"信号提取完成：{len(signals)}个信号，"
                f"痛点:{signal_stats.get('PAIN_POINT', 0)}，"
                f"竞品:{signal_stats.get('COMPETITOR', 0)}，"
                f"机会:{signal_stats.get('OPPORTUNITY', 0)}"
            )

            return self.create_success_result(result_data)

        except Exception as e:
            logger.error(f"信号提取过程发生错误：{str(e)}")
            return self._create_error_result(f"信号提取失败：{str(e)}")

    def _calculate_signal_statistics(self, signals: List[Signal]) -> Dict[str, int]:
        """计算信号统计信息"""
        stats = {}

        for signal in signals:
            signal_type_name = signal.signal_type.value
            stats[signal_type_name] = stats.get(signal_type_name, 0) + 1

        return stats

    def _assess_extraction_quality(
        self, signals: List[Signal], posts: List[RedditPost]
    ) -> Dict[str, float]:
        """评估提取质量"""
        if not posts:
            return {"extraction_rate": 0.0, "avg_confidence": 0.0, "quality_score": 0.0}

        extraction_rate = len(signals) / len(posts)
        avg_confidence = sum(signal.confidence for signal in signals) / max(
            1, len(signals)
        )

        # 综合质量评分
        quality_score = (
            min(1.0, extraction_rate * 2) * 0.4  # 提取率权重40%
            + avg_confidence * 0.6  # 置信度权重60%
        )

        return {
            "extraction_rate": extraction_rate,
            "avg_confidence": avg_confidence,
            "quality_score": quality_score,
        }

    def _signal_to_dict(self, signal: Signal) -> Dict[str, Any]:
        """信号对象转字典"""
        return {
            "signal_type": signal.signal_type.value,
            "content": signal.content,
            "matched_keywords": signal.matched_keywords,
            "confidence": signal.confidence,
            "sentiment_score": signal.sentiment_score,
            "source_post_id": signal.source_post_id,
            "subreddit": signal.subreddit,
            "context_metadata": signal.context_metadata,
            "extracted_at": signal.extracted_at.isoformat(),
        }

    def _create_error_result(self, error_message: str) -> PipelineResult:
        """创建错误结果"""
        logger.error(error_message)
        return PipelineResult(
            step_name=self.name,
            duration=0.0,
            data={"error": error_message},
            success=False,
            status=StepStatus.FAILED,
        )
