"""
Reddit NLP 模型 - 重定向到统一实现

注意：Reddit特定的NLP处理已集成到 RedditContextAdapter 中。
实际实现位置: backend/app/services/analysis/signal_extractor.py
"""

from ..services.analysis.signal_extractor import RedditContextAdapter


class RedditNLP:
    """
    Reddit NLP处理器 - 兼容性包装

    实际功能由 RedditContextAdapter 提供
    """

    def __init__(self) -> None:
        self.adapter = RedditContextAdapter()

    def normalize_text(self, text: str) -> str:
        """文本标准化"""
        return self.adapter.normalize_text(text)

    def detect_sarcasm(self, text: str) -> bool:
        """讽刺检测"""
        return self.adapter.detect_sarcasm(text)

    def extract_features(self, text: str) -> dict[str, float]:
        """特征提取"""
        return self.adapter.extract_reddit_features(text)


# 兼容性标记
IMPLEMENTATION_STATUS = "completed"
ARCHITECTURE_NOTE = "已集成到RedditContextAdapter统一架构中"
