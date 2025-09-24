#!/usr/bin/env python3
"""
测试ReportFormatter的兜底机制
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.report_formatter import (
    _coerce_executive_summary,
    _coerce_market_metrics,
    _coerce_pain_points,
    _coerce_competitors,
    _coerce_opportunities
)
from app.schemas.contracts.report_contract import (
    ExecutiveSummary,
    MarketMetrics,
    PainPointInsight,
    CompetitorInsight,
    OpportunityInsight
)

def test_executive_summary_fallback():
    """测试executive_summary兜底机制"""
    print("🔍 测试executive_summary兜底机制...")
    
    # 测试空数据
    result = _coerce_executive_summary(None)
    assert isinstance(result, ExecutiveSummary)
    assert result.total_communities == 0
    assert result.key_insights == 0
    assert result.summary_points == []
    
    # 测试有效数据
    valid_data = {
        "headline": "测试标题",
        "total_communities": 5,
        "key_insights": 3,
        "summary_points": ["洞察1", "洞察2"]
    }
    result = _coerce_executive_summary(valid_data)
    assert isinstance(result, ExecutiveSummary)
    assert result.headline == "测试标题"
    assert result.total_communities == 5
    
    print("✅ executive_summary兜底机制测试通过")


def test_market_metrics_fallback():
    """测试market_metrics兜底机制"""
    print("🔍 测试market_metrics兜底机制...")
    
    # 测试空数据
    result = _coerce_market_metrics(None)
    assert isinstance(result, MarketMetrics)
    assert result.total_mentions == 0
    assert result.sentiment_score == 0.0
    assert result.top_communities == []
    assert result.trending_keywords == []
    
    # 测试有效数据
    valid_data = {
        "total_mentions": 100,
        "sentiment_score": 0.7,
        "top_communities": ["r/test"],
        "trending_keywords": ["keyword1"]
    }
    result = _coerce_market_metrics(valid_data)
    assert isinstance(result, MarketMetrics)
    assert result.total_mentions == 100
    assert result.sentiment_score == 0.7
    
    print("✅ market_metrics兜底机制测试通过")


def test_pain_points_fallback():
    """测试pain_points兜底机制"""
    print("🔍 测试pain_points兜底机制...")
    
    # 测试空数据
    result = _coerce_pain_points(None)
    assert isinstance(result, list)
    assert len(result) == 0
    
    # 测试无效数据
    result = _coerce_pain_points("invalid")
    assert isinstance(result, list)
    assert len(result) == 0
    
    # 测试有效数据
    valid_data = [
        {
            "description": "测试痛点",
            "sentiment_score": -0.5,
            "frequency": 10
        }
    ]
    result = _coerce_pain_points(valid_data)
    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], PainPointInsight)
    assert result[0].description == "测试痛点"
    
    print("✅ pain_points兜底机制测试通过")


def test_competitors_fallback():
    """测试competitors兜底机制"""
    print("🔍 测试competitors兜底机制...")
    
    # 测试空数据
    result = _coerce_competitors(None)
    assert isinstance(result, list)
    assert len(result) == 0
    
    # 测试有效数据
    valid_data = [
        {
            "name": "竞品A",
            "description": "测试竞品",
            "mention_count": 50,
            "sentiment_score": 0.6
        }
    ]
    result = _coerce_competitors(valid_data)
    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], CompetitorInsight)
    assert result[0].name == "竞品A"
    
    print("✅ competitors兜底机制测试通过")


def test_opportunities_fallback():
    """测试opportunities兜底机制"""
    print("🔍 测试opportunities兜底机制...")
    
    # 测试空数据
    result = _coerce_opportunities(None)
    assert isinstance(result, list)
    assert len(result) == 0
    
    # 测试有效数据
    valid_data = [
        {
            "title": "机会1",
            "description": "测试机会",
            "potential": "high",
            "difficulty": "medium"
        }
    ]
    result = _coerce_opportunities(valid_data)
    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], OpportunityInsight)
    assert result[0].title == "机会1"
    
    print("✅ opportunities兜底机制测试通过")


def main():
    """运行所有测试"""
    print("🚀 开始ReportFormatter兜底机制测试...")
    print("=" * 50)
    
    try:
        test_executive_summary_fallback()
        test_market_metrics_fallback()
        test_pain_points_fallback()
        test_competitors_fallback()
        test_opportunities_fallback()
        
        print("=" * 50)
        print("🎉 所有ReportFormatter兜底机制测试通过！")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
