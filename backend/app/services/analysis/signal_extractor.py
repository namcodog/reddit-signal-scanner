"""
Reddit信号提取步骤 - 基于配置驱动的统一信号检测

设计理念：
- 数据结构优先：复用优雅的SignalPattern设计
- 消除特殊情况：三类信号使用统一处理逻辑
- 配置驱动：避免硬编码的条件分支
- Reddit语境适配：处理非正式语言特征
"""

import re
import time
from dataclasses import dataclass
from logging import getLogger
from typing import Any, Dict, List, Optional, Union, cast

# JSON序列化类型定义
JsonValue = Union[
    str, int, float, bool, None, List["JsonValue"], Dict[str, "JsonValue"]
]

from app.core.step_base import AnalysisStep
from app.models.analysis_pipeline import PipelineData, PipelineResult, StepStatus
from app.models.signal_pattern import (
    DEFAULT_SIGNAL_PATTERNS,
    RedditPost,
    Signal,
    SignalPattern,
)

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

    def __init__(self, patterns: List[SignalPattern]) -> None:
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
        confidence: float = (
            keyword_confidence * 0.5
            + sentiment_confidence * 0.3
            + reddit_feature_boost * 0.2
        ) * float(pattern.confidence_weight)

        # 明确转换为 float，避免 min/max 推断为 Any
        return float(min(1.0, max(0.0, confidence)))


class RedditSignalExtractor(AnalysisStep):
    """Reddit信号提取步骤 - 配置驱动的统一处理"""

    def __init__(self, config: Optional[Dict[str, JsonValue]] = None) -> None:
        from app.core.analyzer_config import StepConfig

        step_config = StepConfig(
            step_name="signal_extraction",
            max_duration=float(cast(Dict[str, Any], config).get("max_duration", 60))
            if config
            else 60.0,
            config_data=(config or {}),
        )
        super().__init__(step_config)
        self.name = "signal_extraction"

        # 配置驱动：使用预定义模式或自定义模式
        self.signal_patterns = DEFAULT_SIGNAL_PATTERNS
        self.detector = UnifiedSignalDetector(self.signal_patterns)

        logger.info(f"初始化信号提取器，加载{len(self.signal_patterns)}个信号模式")

    def validate_input(self, data: "PipelineData") -> bool:
        """验证输入数据 - AnalysisStep要求的抽象方法实现"""
        if not data:
            return False

        # 检查是否有Reddit数据收集结果
        reddit_data = data.get_step_result("data_collection")
        if not reddit_data or "reddit_posts" not in reddit_data:
            return False

        reddit_posts = reddit_data["reddit_posts"]
        # 类型检查：确保reddit_posts是列表类型且非空
        return (
            reddit_posts is not None
            and isinstance(reddit_posts, list)
            and len(reddit_posts) > 0
        )

    async def _process_step(self, data: PipelineData) -> PipelineResult:
        """
        执行Reddit信号提取

        输入：包含Reddit帖子数据的PipelineData
        输出：包含三类商业信号的PipelineResult
        """

        # 输入验证
        if not self.validate_input(data):
            return self._create_error_result("输入数据验证失败")

        # 获取Reddit数据
        reddit_data = data.get_step_result("data_collection")
        if not reddit_data or "reddit_posts" not in reddit_data:
            return self._create_error_result("未找到Reddit帖子数据")

        reddit_posts = reddit_data["reddit_posts"]
        if not reddit_posts:
            return self._create_error_result("Reddit帖子数据为空")

        # 类型断言确保安全访问
        reddit_posts_typed = cast(List[RedditPost], reddit_posts)

        logger.info(f"开始处理{len(reddit_posts_typed)}条Reddit帖子")

        try:
            # 信号提取 - 统一处理
            signals = self.detector.extract_signals(reddit_posts_typed)

            # 按信号类型分组统计
            signal_stats = self._calculate_signal_statistics(signals)
            signal_stats_json: Dict[str, JsonValue] = cast(
                Dict[str, JsonValue], signal_stats
            )

            # 质量评估
            quality_metrics = self._assess_extraction_quality(
                signals, reddit_posts_typed
            )
            quality_metrics_json: Dict[str, JsonValue] = cast(
                Dict[str, JsonValue], quality_metrics
            )

            # 构建结果
            result_data: Dict[str, JsonValue] = {
                "signals": [self._signal_to_dict(signal) for signal in signals],
                "statistics": signal_stats_json,
                "quality_metrics": quality_metrics_json,
                "total_processed": len(reddit_posts_typed),
                "total_signals": len(signals),
            }

            logger.info(
                f"信号提取完成：{len(signals)}个信号，"
                f"痛点:{signal_stats.get('PAIN_POINT', 0)}，"
                f"竞品:{signal_stats.get('COMPETITOR', 0)}，"
                f"机会:{signal_stats.get('OPPORTUNITY', 0)}"
            )

            # 构造成功结果 - 直接创建PipelineResult对象
            duration = time.time() - self._start_time if self._start_time else 0.0
            from app.models.analysis_pipeline import PipelineResult, StepStatus

            return PipelineResult(
                step_name=self.name,
                duration=duration,
                data=result_data,
                success=True,
                status=StepStatus.COMPLETED,
                metadata={
                    "step_name": self.name,
                    "execution_time": duration,
                    "config_version": self.config.step_name,
                },
            )

        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"信号提取过程发生错误：{str(e)}")
            return self._create_error_result(f"信号提取失败：{str(e)}")

    def _calculate_signal_statistics(self, signals: List[Signal]) -> Dict[str, int]:
        """计算信号统计信息"""
        stats: Dict[str, int] = {}

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

    def _signal_to_dict(self, signal: Signal) -> Dict[str, JsonValue]:
        """信号对象转字典"""
        # 使用typing.cast确保类型兼容性
        result: Dict[str, JsonValue] = {
            "signal_type": signal.signal_type.value,
            "content": signal.content,
            "matched_keywords": (
                list(signal.matched_keywords)
                if hasattr(signal, "matched_keywords") and signal.matched_keywords
                else []
            ),
            "confidence": signal.confidence,
            "sentiment_score": signal.sentiment_score,
            "source_post_id": signal.source_post_id,
            "subreddit": signal.subreddit,
            "context_metadata": (
                cast(Dict[str, JsonValue], signal.context_metadata)
                if hasattr(signal, "context_metadata") and signal.context_metadata
                else {}
            ),
            "extracted_at": signal.extracted_at.isoformat(),
        }
        return result

    def _create_error_result(
        self, error_message: str, status: StepStatus = StepStatus.FAILED
    ) -> PipelineResult:
        """创建错误结果"""
        logger.error(error_message)
        duration = 0.0
        if hasattr(self, "_start_time") and self._start_time:
            duration = time.time() - self._start_time

        return PipelineResult(
            step_name=self.name,
            duration=duration,
            data={"error": error_message},
            success=False,
            status=status,
            error_message=error_message,
            metadata={
                "step_name": self.name,
                "error_time": time.time(),
                "config_version": (
                    self.config.step_name
                    if hasattr(self.config, "step_name")
                    else "unknown"
                ),
            },
        )
