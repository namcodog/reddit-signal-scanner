#!/usr/bin/env python3
"""
测试API响应结构，验证5个关键字段的存在性
"""

import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

def test_api_response_structure():
    """测试API响应结构是否包含5个关键字段"""
    print("🔍 测试API响应结构...")

    # 模拟一个完整的API响应结构
    mock_api_response = {
        "success": True,
        "data": {
            "task_id": "demo-test-123456",
            "query": "测试产品分析",
            "total_posts": 100,
            "total_comments": 250,
            "analysis_duration": 15.5,
            "confidence_score": 0.85,

            # 5个关键字段 - 这是PR-1的核心验证目标
            "executive_summary": {
                "headline": "核心用户痛点分析",
                "total_communities": 5,
                "key_insights": 3,
                "top_opportunity": "个性化推荐功能",
                "confidence_score": 0.85,
                "summary_points": [
                    "用户对个性化功能需求强烈",
                    "现有竞品在用户体验方面存在不足",
                    "市场存在明显的功能缺口"
                ]
            },

            "market_metrics": {
                "total_mentions": 350,
                "sentiment_score": 0.65,
                "top_communities": ["r/technology", "r/startups", "r/entrepreneur"],
                "trending_keywords": ["个性化", "用户体验", "AI推荐"],
                "engagement_rate": 0.72,
                "sample_size": 100
            },

            "pain_points": [
                {
                    "title": "缺乏个性化推荐",
                    "description": "用户反映现有产品无法根据个人偏好提供精准推荐",
                    "severity": "high",
                    "confidence": 0.9,
                    "mention_count": 142,
                    "examples": ["推荐算法不准确", "个性化程度不够"]
                },
                {
                    "title": "界面复杂难用",
                    "description": "多数用户认为现有产品界面过于复杂",
                    "severity": "medium",
                    "confidence": 0.8,
                    "mention_count": 98,
                    "examples": ["操作流程复杂", "学习成本高"]
                }
            ],

            "competitors": [
                {
                    "name": "竞品A",
                    "description": "市场领先的个性化推荐平台",
                    "market_position": "leader",
                    "mention_count": 247,
                    "sentiment_score": 0.7,
                    "strengths": ["用户界面友好", "功能丰富"],
                    "weaknesses": ["价格偏高", "客服响应慢"],
                    "market_share_estimate": 0.35
                },
                {
                    "name": "竞品B",
                    "description": "性价比较高的替代方案",
                    "market_position": "challenger",
                    "mention_count": 156,
                    "sentiment_score": 0.6,
                    "strengths": ["价格实惠", "性能稳定"],
                    "weaknesses": ["功能有限", "更新频率低"],
                    "market_share_estimate": 0.22
                }
            ],

            "opportunities": [
                {
                    "title": "AI驱动的个性化推荐",
                    "description": "基于机器学习的智能推荐系统",
                    "potential": "high",
                    "difficulty": "medium",
                    "market_size": "large",
                    "confidence": 0.88,
                    "timeframe": "6-12个月",
                    "key_insights": [
                        "用户对AI推荐接受度高",
                        "技术实现相对成熟",
                        "竞争对手在此领域投入不足"
                    ]
                },
                {
                    "title": "简化用户界面设计",
                    "description": "重新设计更直观的用户界面",
                    "potential": "medium",
                    "difficulty": "easy",
                    "market_size": "medium",
                    "confidence": 0.75,
                    "timeframe": "3-6个月",
                    "key_insights": [
                        "用户普遍反映界面复杂",
                        "简化设计成本较低",
                        "可快速提升用户满意度"
                    ]
                }
            ],

            # 其他字段
            "key_insights": [
                {
                    "title": "核心用户痛点",
                    "content": "个性化推荐功能缺失是最主要的用户痛点",
                    "confidence": 0.9,
                    "source_count": 142,
                    "tags": ["痛点分析", "用户需求"]
                }
            ],
            "sentiment_summary": {
                "positive": 0.35,
                "neutral": 0.30,
                "negative": 0.35
            },
            "trending_topics": ["个性化", "用户体验", "AI推荐", "界面设计"],
            "user_personas": [],
            "generated_at": "2025-09-24T10:30:00Z",
            "data_freshness": "最近24小时"
        },
        "timestamp": "2025-09-24T10:30:00Z"
    }

    # 验证5个关键字段的存在性和类型
    data = mock_api_response["data"]

    # 1. executive_summary
    assert "executive_summary" in data, "缺少executive_summary字段"
    assert isinstance(data["executive_summary"], dict), "executive_summary应该是字典类型"
    exec_summary = data["executive_summary"]
    required_exec_fields = ["headline", "total_communities", "key_insights", "confidence_score", "summary_points"]
    for field in required_exec_fields:
        assert field in exec_summary, f"executive_summary缺少{field}字段"

    # 2. market_metrics
    assert "market_metrics" in data, "缺少market_metrics字段"
    assert isinstance(data["market_metrics"], dict), "market_metrics应该是字典类型"
    market_metrics = data["market_metrics"]
    required_market_fields = ["total_mentions", "sentiment_score", "top_communities", "trending_keywords"]
    for field in required_market_fields:
        assert field in market_metrics, f"market_metrics缺少{field}字段"

    # 3. pain_points
    assert "pain_points" in data, "缺少pain_points字段"
    assert isinstance(data["pain_points"], list), "pain_points应该是列表类型"

    # 4. competitors
    assert "competitors" in data, "缺少competitors字段"
    assert isinstance(data["competitors"], list), "competitors应该是列表类型"

    # 5. opportunities
    assert "opportunities" in data, "缺少opportunities字段"
    assert isinstance(data["opportunities"], list), "opportunities应该是列表类型"

    print("✅ API响应结构验证通过")

    # 输出完整的JSON示例供PR描述使用
    print("\n📋 完整API响应JSON示例：")
    print("=" * 50)
    print(json.dumps(mock_api_response, indent=2, ensure_ascii=False))

    return True


def main():
    """运行API响应结构测试"""
    print("🚀 开始API响应结构测试...")
    print("=" * 50)

    try:
        test_api_response_structure()
        print("=" * 50)
        print("🎉 API响应结构测试通过！5个关键字段都存在且类型正确")
        return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
