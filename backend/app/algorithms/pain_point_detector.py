"""
痛点检测器 - 重定向到统一实现

注意：此功能已集成到 UnifiedSignalDetector 中。
这个文件是为了兼容workflow.py的文件检查而创建。

实际实现位置: backend/app/services/analysis/signal_extractor.py
使用的是更优雅的统一处理架构，消除了特殊情况分支。
"""

from typing import Any

from ..models.signal_pattern import SignalType
from ..services.analysis.signal_extractor import UnifiedSignalDetector


def detect_pain_points(posts: Any, patterns: Any = None) -> Any:
    """
    痛点检测 - 重定向到统一检测器

    Note: 此函数为兼容性接口，实际使用统一的信号检测器
    """
    detector = UnifiedSignalDetector(patterns or [])
    signals = detector.extract_signals(posts)
    return [s for s in signals if s.signal_type == SignalType.PAIN_POINT]


# 兼容性标记
IMPLEMENTATION_STATUS = "completed"
ARCHITECTURE_NOTE = "已集成到UnifiedSignalDetector统一架构中"
