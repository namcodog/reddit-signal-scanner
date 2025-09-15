#!/usr/bin/env python3
"""
调试机会发现算法失败原因
"""

import sys

sys.path.append("/Users/hujia/Desktop/最小化Navigator/backend")

from app.models.signal_pattern import DEFAULT_SIGNAL_PATTERNS, RedditPost, SignalType
from app.services.analysis.signal_extractor import UnifiedSignalDetector


def debug_opportunity_detection():
    """调试机会发现算法"""

    # 创建检测器
    detector = UnifiedSignalDetector(DEFAULT_SIGNAL_PATTERNS)

    # 测试机会检测
    print("=== 调试机会发现算法 ===")
    opportunity_post = RedditPost(
        id="debug_opportunity",
        title="Test Opportunity",
        content="Wish there was a solution for this unmet need, missing this feature would pay for it",
        subreddit="r/test",
        score=100,
        comment_count=20,
    )

    print(f"输入文本: {opportunity_post.content}")

    # 步骤1: 文本标准化
    normalized = detector.context_adapter.normalize_text(opportunity_post.content)
    print(f"标准化文本: {normalized}")

    # 步骤2: 提取Reddit特征
    features = detector.context_adapter.extract_reddit_features(normalized)
    print(f"Reddit特征: {features}")

    # 步骤3: 检查机会模式
    opportunity_pattern = next(
        p for p in detector.patterns if p.signal_type == SignalType.OPPORTUNITY
    )
    print(f"机会模式关键词: {opportunity_pattern.keywords}")
    print(f"机会模式情感阈值: {opportunity_pattern.sentiment_threshold}")
    print(f"机会模式最小关键词匹配: {opportunity_pattern.min_keyword_matches}")
    print(f"机会模式上下文规则: {opportunity_pattern.context_rules}")

    # 步骤4: 关键词匹配检查
    keyword_matches = detector._count_keyword_matches(
        normalized, opportunity_pattern.keywords
    )
    print(f"关键词匹配数: {keyword_matches}")

    # 详细检查每个关键词
    print("\n关键词匹配详情:")
    for keyword in opportunity_pattern.keywords:
        match = keyword.lower() in normalized.lower()
        print(f"  '{keyword}' -> {match}")

    # 步骤5: 情感分析
    sentiment = detector._simple_sentiment_analysis(normalized)
    print(f"\n情感分数: {sentiment}")
    print(
        f"是否满足情感阈值({opportunity_pattern.sentiment_threshold}): {sentiment >= opportunity_pattern.sentiment_threshold}"
    )

    # 步骤6: 上下文规则验证
    context_valid = detector._validate_context_rules(
        normalized, opportunity_pattern.context_rules
    )
    print(f"上下文规则验证: {context_valid}")
    print(f"上下文规则详情:")
    for rule in opportunity_pattern.context_rules:
        in_text = rule.lower() in normalized.lower()
        print(f"  '{rule}' 在文本中: {in_text}")

    # 步骤7: 完整信号提取
    signals = detector.extract_signals([opportunity_post])
    print(f"\n检测到的信号数量: {len(signals)}")

    if signals:
        signal = signals[0]
        print(f"信号类型: {signal.signal_type}")
        print(f"匹配关键词: {signal.matched_keywords}")
        print(f"置信度: {signal.confidence}")
    else:
        print("❌ 没有检测到任何信号！")


if __name__ == "__main__":
    debug_opportunity_detection()
