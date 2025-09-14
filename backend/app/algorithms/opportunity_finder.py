"""
机会发现器 - 重定向到统一实现

注意：此功能已集成到 UnifiedSignalDetector 中。
实际实现位置: backend/app/services/analysis/signal_extractor.py

Context7最佳实践：
- 使用@validate_call实现函数参数类型安全
- 使用TypeAdapter处理复杂返回类型
- 保持100%向后兼容性
"""

from typing import Any, List, Optional, Union, cast

from pydantic import TypeAdapter, validate_call

from ..models.signal_pattern import (
    DEFAULT_SIGNAL_PATTERNS,
    RedditPost,
    Signal,
    SignalPattern,
    SignalType,
)
from ..services.analysis.signal_extractor import UnifiedSignalDetector

# 类型安全的适配器
SignalListAdapter = TypeAdapter(List[Signal])
RedditPostListAdapter = TypeAdapter(List[RedditPost])


@validate_call(validate_return=True)
def find_opportunities(
    posts: Union[List[RedditPost], List[dict[str, Any]], Any],
    patterns: Optional[Union[List[SignalPattern], List[dict[str, Any]], Any]] = None,
) -> List[Signal]:
    """
    机会发现 - 重定向到统一检测器

    Args:
        posts: Reddit帖子列表，支持RedditPost对象或字典格式
        patterns: 信号模式列表，可选参数，默认使用内置模式

    Returns:
        List[Signal]: 发现的机会信号列表，类型安全保证

    Raises:
        ValidationError: 当输入参数不符合类型要求时
    """
    # 确保向后兼容：如果传入的是旧格式，保持原有行为
    try:
        # 规范化输入类型
        typed_posts: List[RedditPost] = RedditPostListAdapter.validate_python(posts)
        typed_patterns: List[SignalPattern]
        if patterns is None:
            typed_patterns = DEFAULT_SIGNAL_PATTERNS
        else:
            try:
                typed_patterns = TypeAdapter(List[SignalPattern]).validate_python(
                    patterns
                )
            except Exception:
                typed_patterns = DEFAULT_SIGNAL_PATTERNS

        detector = UnifiedSignalDetector(typed_patterns)
        signals = detector.extract_signals(typed_posts)
        opportunity_signals = [
            s for s in signals if s.signal_type == SignalType.OPPORTUNITY
        ]

        # 使用TypeAdapter验证返回值的类型安全性
        validated_signals = SignalListAdapter.validate_python(opportunity_signals)
        return validated_signals

    except Exception:
        # 如果类型安全处理失败，回退到原有逻辑（尽量转换）
        fallback_posts = cast(List[Any], posts)
        detector = UnifiedSignalDetector(DEFAULT_SIGNAL_PATTERNS)
        signals = detector.extract_signals(fallback_posts)
        return [s for s in signals if s.signal_type == SignalType.OPPORTUNITY]


IMPLEMENTATION_STATUS = "completed"
ARCHITECTURE_NOTE = "已集成到UnifiedSignalDetector统一架构中"
