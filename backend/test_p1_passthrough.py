#!/usr/bin/env python3
"""
PR-1 字段传递兜底机制测试
验证5个关键字段在数据流中的传递和兜底逻辑
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from typing import Dict, Any, List
import time
from datetime import datetime

# 导入需要测试的模块
from app.services.analysis.result_ranker import extract_signals_from_pipeline, rank_business_signals
from app.models.analysis_pipeline import PipelineData, PipelineResult, AnalysisReport, InsightsData
from app.tasks.analysis_tasks import _build_insights_payload, _build_market_metrics


def test_signal_extraction_passthrough():
    """测试信号提取中的字段传递兜底机制"""
    print("🔍 测试信号提取字段传递...")

    # 创建测试数据 - 包含5个关键字段
    test_data = PipelineData(
        product_description="测试产品",
        step_results={
            "signal_extraction": {
                "insights": {
                    "pain_points": [
                        {"title": "测试痛点1", "description": "痛点描述", "confidence": 0.8}
                    ],
                    "competitors": [
                        {"name": "竞品A", "description": "竞品描述", "market_share": 0.3}
                    ],
                    "opportunities": [
                        {"title": "机会1", "description": "机会描述", "potential": 0.9}
                    ],
                    "analysis_summary": "测试分析摘要",
                    "key_insights": ["洞察1", "洞察2"]
                }
            }
        }
    )

    # 测试信号提取
    signals = extract_signals_from_pipeline(test_data)

    # 验证结果
    assert len(signals) > 0, "应该提取到信号"

    # 验证每个信号都有必需字段
    for signal in signals:
        assert "type" in signal, "信号应该有type字段"
        assert "title" in signal, "信号应该有title字段"
        assert "relevance_score" in signal, "信号应该有relevance_score字段"
        assert "timestamp" in signal, "信号应该有timestamp字段"

    print("✅ 信号提取字段传递测试通过")


def test_empty_data_passthrough():
    """测试空数据的兜底机制"""
    print("🔍 测试空数据兜底机制...")

    # 创建空数据
    empty_data = PipelineData(
        product_description="测试产品",
        step_results={
            "signal_extraction": {
                "insights": {}  # 空的insights
            }
        }
    )

    # 测试信号提取
    signals = extract_signals_from_pipeline(empty_data)

    # 验证空数据处理
    assert isinstance(signals, list), "应该返回列表类型"
    assert len(signals) == 0, "空数据应该返回空列表"

    print("✅ 空数据兜底机制测试通过")


def test_insights_payload_building():
    """测试洞察数据构建的兜底机制"""
    print("🔍 测试洞察数据构建...")

    # 创建测试报告
    insights = InsightsData(
        pain_points=[{"title": "痛点1", "description": "描述1"}],
        competitors=[{"name": "竞品1", "description": "竞品描述"}],
        opportunities=[{"title": "机会1", "description": "机会描述"}],
        analysis_summary="测试摘要",
        key_insights=["洞察1"],
        confidence_score=0.8,
        data_quality_score=0.7
    )

    report = AnalysisReport(
        report_id="test-report-123",
        product_description="测试产品描述",
        insights=insights,
        confidence_score=0.8,
        total_duration=10.0,
        step_durations={"step1": 2.0, "step2": 3.0, "step3": 2.0, "step4": 3.0},
        data_sources={"reddit": 100},
        data_quality_metrics={"community_relevance": 0.8},
        communities_scanned=["test_community"],
        total_posts_analyzed=100,
        generated_at=datetime.now()
    )

    # 测试构建洞察数据
    insights_payload, market_metrics, metadata = _build_insights_payload(
        report, "测试产品描述"
    )

    # 验证5个关键字段都存在
    assert "pain_points" in insights_payload, "应该包含pain_points字段"
    assert "competitors" in insights_payload, "应该包含competitors字段"
    assert "opportunities" in insights_payload, "应该包含opportunities字段"
    assert "executive_summary" in insights_payload, "应该包含executive_summary字段"

    # 验证market_metrics字段
    assert "total_mentions" in market_metrics, "应该包含total_mentions字段"
    assert "sentiment_score" in market_metrics, "应该包含sentiment_score字段"
    assert "top_communities" in market_metrics, "应该包含top_communities字段"
    assert "trending_keywords" in market_metrics, "应该包含trending_keywords字段"

    # 验证字段类型
    assert isinstance(insights_payload["pain_points"], list), "pain_points应该是列表"
    assert isinstance(insights_payload["competitors"], list), "competitors应该是列表"
    assert isinstance(insights_payload["opportunities"], list), "opportunities应该是列表"
    assert isinstance(insights_payload["executive_summary"], dict), "executive_summary应该是字典"

    print("✅ 洞察数据构建测试通过")


def test_empty_insights_payload():
    """测试空洞察数据的兜底机制"""
    print("🔍 测试空洞察数据兜底...")

    # 创建空洞察的报告
    empty_insights = InsightsData(
        pain_points=[],
        competitors=[],
        opportunities=[],
        analysis_summary="",
        key_insights=[],
        confidence_score=0.0,
        data_quality_score=0.0
    )

    report = AnalysisReport(
        report_id="test-empty-123",
        product_description="测试产品",
        insights=empty_insights,
        confidence_score=0.0,
        total_duration=5.0,
        step_durations={"step1": 1.0, "step2": 1.0, "step3": 1.0, "step4": 2.0},
        data_sources={},
        data_quality_metrics={},
        communities_scanned=[],
        total_posts_analyzed=0,
        generated_at=datetime.now()
    )

    # 测试构建空洞察数据
    insights_payload, market_metrics, metadata = _build_insights_payload(
        report, "测试产品"
    )

    # 验证即使为空，字段也存在且类型正确
    assert isinstance(insights_payload["pain_points"], list), "空pain_points应该是列表"
    assert isinstance(insights_payload["competitors"], list), "空competitors应该是列表"
    assert isinstance(insights_payload["opportunities"], list), "空opportunities应该是列表"
    assert isinstance(insights_payload["executive_summary"], dict), "executive_summary应该是字典"

    # 验证market_metrics即使为空也有正确结构
    assert isinstance(market_metrics["total_mentions"], int), "total_mentions应该是数字"
    assert isinstance(market_metrics["top_communities"], list), "top_communities应该是列表"
    assert isinstance(market_metrics["trending_keywords"], list), "trending_keywords应该是列表"

    print("✅ 空洞察数据兜底测试通过")


def main():
    """运行所有测试"""
    print("🚀 开始PR-1字段传递兜底机制测试...")
    print("=" * 50)

    try:
        test_signal_extraction_passthrough()
        test_empty_data_passthrough()
        test_insights_payload_building()
        test_empty_insights_payload()

        print("=" * 50)
        print("🎉 所有测试通过！PR-1字段传递兜底机制工作正常")
        return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
