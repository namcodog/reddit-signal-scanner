#!/usr/bin/env python3
"""
调试算法行为 - 理解信号检测失败的原因
"""

import sys

sys.path.append("/Users/hujia/Desktop/最小化Navigator/backend")

from app.models.signal_pattern import DEFAULT_SIGNAL_PATTERNS, RedditPost, SignalType
from app.services.analysis.signal_extractor import UnifiedSignalDetector


def debug_signal_detection():
    """调试信号检测算法"""

    # 创建检测器
    detector = UnifiedSignalDetector(DEFAULT_SIGNAL_PATTERNS)

    # 测试痛点检测
    print("=== 调试痛点检测算法 ===")
    pain_post = RedditPost(
        id="debug_pain",
        title="Test Pain Point",
        content="This app is broken and frustrating to use",
        subreddit="r/test",
        score=100,
        comment_count=20,
    )

    print(f"输入文本: {pain_post.content}")

    # 步骤1: 文本标准化
    normalized = detector.context_adapter.normalize_text(pain_post.content)
    print(f"标准化文本: {normalized}")

    # 步骤2: 提取Reddit特征
    features = detector.context_adapter.extract_reddit_features(normalized)
    print(f"Reddit特征: {features}")

    # 步骤3: 检查痛点模式
    pain_pattern = next(
        p for p in detector.patterns if p.signal_type == SignalType.PAIN_POINT
    )
    print(f"痛点模式关键词: {pain_pattern.keywords}")
    print(f"痛点模式情感阈值: {pain_pattern.sentiment_threshold}")
    print(f"痛点模式最小关键词匹配: {pain_pattern.min_keyword_matches}")

    # 步骤4: 关键词匹配
    keyword_matches = detector._count_keyword_matches(normalized, pain_pattern.keywords)
    print(f"关键词匹配数: {keyword_matches}")

    # 步骤5: 情感分析
    sentiment = detector._simple_sentiment_analysis(normalized)
    print(f"情感分数: {sentiment}")
    print(
        f"是否满足情感阈值({pain_pattern.sentiment_threshold}): {sentiment <= pain_pattern.sentiment_threshold}"
    )

    # 步骤6: 完整信号提取
    signals = detector.extract_signals([pain_post])
    print(f"检测到的信号数量: {len(signals)}")

    if signals:
        signal = signals[0]
        print(f"信号类型: {signal.signal_type}")
        print(f"匹配关键词: {signal.matched_keywords}")
        print(f"置信度: {signal.confidence}")
    else:
        print("❌ 没有检测到任何信号！")


if __name__ == "__main__":
    debug_signal_detection()
