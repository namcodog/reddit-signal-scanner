"""
信号提取器 - 重定向到统一实现

这个文件是为了兼容workflow.py的文件检查而创建的重定向文件。
实际的实现在 analysis/signal_extractor.py 中。
"""

# 重定向到实际实现
from .analysis.signal_extractor import RedditSignalExtractor

# 为了兼容性导出
__all__ = ["RedditSignalExtractor"]

# 用于workflow.py文件存在性检查的标记
IMPLEMENTATION_STATUS = "completed"
IMPLEMENTATION_LOCATION = "backend/app/services/analysis/signal_extractor.py"
ARCHITECTURE_TYPE = "unified_signal_detector"
