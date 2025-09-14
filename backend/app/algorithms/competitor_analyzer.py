"""
竞品分析器 - 重定向到统一实现

注意：此功能已集成到 UnifiedSignalDetector 中。
实际实现位置: backend/app/services/analysis/signal_extractor.py
"""

from typing import Any

from ..models.signal_pattern import SignalType
from ..services.analysis.signal_extractor import UnifiedSignalDetector


def analyze_competitors(posts: Any, patterns: Any = None) -> Any:
    """
    竞品分析 - 重定向到统一检测器
    """
    detector = UnifiedSignalDetector(patterns or [])
    signals = detector.extract_signals(posts)
    return [s for s in signals if s.signal_type == SignalType.COMPETITOR]


IMPLEMENTATION_STATUS = "completed"
ARCHITECTURE_NOTE = "已集成到UnifiedSignalDetector统一架构中"
