"""ReportData 契约字段单元测试。"""

from __future__ import annotations

from typing import Any, Dict

import pytest
from pydantic import ValidationError

from app.schemas.contracts.report_contract import ReportData


def _make_payload() -> Dict[str, Any]:
    """构造带有结构化洞察的标准载荷。"""

    return {
        "task_id": "tsk_demo_001",
        "query": "寻找 Reddit 营销自动化机会",
        "total_posts": 120,
        "total_comments": 340,
        "analysis_duration": 142.5,
        "key_insights": [
            {
                "title": "营销自动化需求强烈",
                "content": "大量用户提到需要自动化工具以节省时间。",
                "confidence": 0.9,
                "source_count": 24,
                "tags": ["automation", "growth"],
            }
        ],
        "sentiment_summary": {"positive": 0.62, "neutral": 0.25, "negative": 0.13},
        "trending_topics": ["workflow", "ai assistant"],
        "user_personas": [
            {
                "name": "增长负责人",
                "pain_points": ["缺少自动化工具"],
                "priority": "high",
            }
        ],
        "generated_at": "2025-09-23T10:00:00Z",
        "data_freshness": "6小时内",
        "executive_summary": {
            "headline": "Reddit 营销自动化趋势洞察",
            "total_communities": 18,
            "key_insights": 5,
            "top_opportunity": "自动化运营中小社区",
            "confidence_score": 0.82,
            "summary_points": [
                "用户对自动化工具的兴趣持续走高",
                "竞品在价格策略上存在空档",
            ],
        },
        "market_metrics": {
            "total_mentions": 460,
            "sentiment_score": 0.37,
            "top_communities": ["r/startups", "r/marketing"],
            "trending_keywords": ["automation", "reddit bot"],
            "engagement_rate": 0.41,
            "sample_size": 180,
        },
        "pain_points": [
            {
                "description": "缺少一体化 Reddit 营销工具",
                "sentiment_score": -0.32,
                "frequency": 28,
                "confidence": 0.78,
                "severity": "high",
                "categories": ["效率", "工具缺口"],
                "tags": ["automation", "campaign"],
                "example_posts": [
                    {
                        "post_id": "abc123",
                        "community": "r/startups",
                        "permalink": "https://reddit.com/abc123",
                        "content_snippet": "有没有一体化的 Reddit 营销工具？",
                        "upvotes": 156,
                    }
                ],
            }
        ],
        "competitors": [
            {
                "name": "CompetitorX",
                "mention_count": 45,
                "sentiment_score": 0.18,
                "strengths": ["自动化流程完善"],
                "weaknesses": ["价格昂贵"],
                "price_mentions": ["$199/mo"],
                "market_position": "leader",
                "summary": "高端定位但价格较高",
                "share_of_voice": 0.33,
                "website": "https://competitor.example",
            }
        ],
        "opportunities": [
            {
                "title": "面向中小企业的 Reddit 自动化套件",
                "description": "推出可负担的 Reddit 自动化工具，降低使用门槛。",
                "market_size_indicator": "large",
                "urgency_score": 0.74,
                "feasibility_score": 0.68,
                "target_communities": ["r/smallbusiness", "r/marketing"],
                "related_keywords": ["automation", "smb"],
                "estimated_demand": 520,
                "potential_score": 0.81,
                "timeframe": "Q4",
            }
        ],
        "html_content": "<section>自动化洞察报告</section>",
    }


def test_report_data_parses_structured_sections() -> None:
    payload = _make_payload()
    report = ReportData(**payload)

    assert report.executive_summary.total_communities == 18
    assert report.executive_summary.summary_points[0].startswith("用户对自动化工具")
    assert report.market_metrics.total_mentions == 460
    assert report.market_metrics.trending_keywords[-1] == "reddit bot"

    pain_point = report.pain_points[0]
    assert pain_point.severity == "high"
    assert pain_point.example_posts[0].post_id == "abc123"

    competitor = report.competitors[0]
    assert competitor.market_position == "leader"
    assert pytest.approx(competitor.share_of_voice or 0.0, rel=1e-3) == 0.33

    opportunity = report.opportunities[0]
    assert opportunity.market_size_indicator == "large"
    assert opportunity.timeframe == "Q4"


def test_report_data_defaults_when_sections_missing() -> None:
    payload = _make_payload()
    payload.pop("executive_summary")
    payload.pop("market_metrics")
    payload.pop("pain_points")
    payload.pop("competitors")
    payload.pop("opportunities")

    report = ReportData(**payload)

    assert report.executive_summary.total_communities == 0
    assert report.market_metrics.trending_keywords == []
    assert report.pain_points == []
    assert report.competitors == []
    assert report.opportunities == []


def test_invalid_sentiment_score_rejected() -> None:
    payload = _make_payload()
    payload["market_metrics"]["sentiment_score"] = 1.5

    with pytest.raises(ValidationError):
        ReportData(**payload)


def test_invalid_pain_point_severity_rejected() -> None:
    payload = _make_payload()
    payload["pain_points"][0]["severity"] = "critical"

    with pytest.raises(ValidationError):
        ReportData(**payload)

