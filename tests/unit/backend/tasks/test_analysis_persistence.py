import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

pytest_plugins = ["backend.tests.conftest"]

from app.models.analysis_pipeline import AnalysisReport, InsightsData
from app.tasks.analysis_tasks import (
    _build_insights_payload,
    _build_sources_payload,
    _render_report_html,
)


@pytest.mark.asyncio
async def test_build_insights_payload_schema(db_session) -> None:
    report = AnalysisReport(
        report_id="demo-report",
        product_description="A comprehensive Reddit signal scan for demo purposes",
        generated_at=datetime.now(timezone.utc),
        insights=InsightsData(
            pain_points=[
                {
                    "description": "用户反映价格较高",
                    "sentiment_score": -0.45,
                    "frequency": 12,
                    "evidence_posts": ["post-1", "post-2"],
                    "categories": ["pricing", "value"],
                }
            ],
            competitors=[
                {
                    "name": "Competitor Zero",
                    "mention_count": 5,
                    "sentiment_score": 0.32,
                    "strengths": ["功能丰富"],
                    "weaknesses": ["服务响应慢"],
                }
            ],
            opportunities=[
                {
                    "title": "推出团队定价方案",
                    "description": "针对成长型团队的阶梯定价模型",
                    "market_size_indicator": "medium",
                    "urgency_score": 0.68,
                    "feasibility_score": 0.72,
                    "estimated_demand": 1500,
                    "related_keywords": ["pricing", "bundle"],
                }
            ],
            analysis_summary={"summary": "测试报告"},
            key_insights=["价格敏感群体占比高"],
        ),
        confidence_score=0.78,
        total_posts_analyzed=32,
        communities_scanned=["r/startups", "r/marketing"],
        data_sources={"api": 22, "cache": 10},
        total_duration=14.5,
        step_durations={"community_discovery": 4.5, "data_collection": 6.0},
        data_quality_metrics={
            "community_relevance": 0.82,
            "cache_hit_rate": 0.58,
            "data_freshness": 0.71,
            "signal_confidence": 0.67,
        },
    )

    insights_payload, market_metrics, metadata = _build_insights_payload(
        report, "A comprehensive Reddit signal scan for demo purposes"
    )

    assert insights_payload["pain_points"], "pain points should not be empty"
    assert insights_payload["competitors"], "competitors should not be empty"
    assert insights_payload["opportunities"], "opportunities should not be empty"
    assert "market_metrics" not in insights_payload
    assert market_metrics["total_mentions"] == report.total_posts_analyzed
    assert metadata["report_id"] == report.report_id

    result = await db_session.execute(
        text("SELECT validate_insights_schema(:data)"),
        {"data": json.dumps(insights_payload)},
    )
    assert result.scalar() is True


def test_build_sources_payload_defaults() -> None:
    report = AnalysisReport(
        report_id="sources-demo",
        product_description="Sources payload demo",
        insights=InsightsData(
            pain_points=[
                {
                    "description": "UX confusing",
                    "sentiment_score": -0.2,
                    "frequency": 3,
                    "evidence_posts": ["p1"],
                }
            ],
            competitors=[
                {
                    "name": "Comp",
                    "mention_count": 2,
                    "sentiment_score": 0.1,
                    "strengths": ["fast"],
                    "weaknesses": ["pricing"],
                }
            ],
            opportunities=[
                {
                    "title": "Improve onboarding",
                    "description": "Better onboarding",
                    "market_size_indicator": "small",
                    "urgency_score": 0.5,
                    "feasibility_score": 0.6,
                }
            ],
            analysis_summary={},
            key_insights=[],
        ),
        confidence_score=0.51,
        total_posts_analyzed=10,
        communities_scanned=["r/productivity"],
        data_sources={},
        total_duration=5.2,
        step_durations={},
        data_quality_metrics={},
    )

    sources_payload = _build_sources_payload(report, ["r/productivity"])
    assert sources_payload["posts_analyzed"] == 10
    assert sources_payload["communities"] == ["r/productivity"]
    assert sources_payload["time_range_days"] >= 1
    assert 0.0 <= sources_payload["cache_hit_rate"] <= 1.0


def test_render_report_html_contains_sections() -> None:
    insights_payload = {
        "pain_points": [
            {"description": "Pain", "frequency": 5, "sentiment_score": -0.3}
        ],
        "competitors": [{"name": "Comp", "mentions": 4, "sentiment": 0.2}],
        "opportunities": [
            {"title": "Opp", "relevance_score": 0.7, "potential_users": 900}
        ],
    }
    market_metrics = {
        "total_mentions": 20,
        "sentiment_score": 0.1,
        "engagement_rate": 0.5,
        "top_communities": ["r/test"],
        "trending_keywords": ["test"],
        "sample_size": 20,
    }

    html_content = _render_report_html(
        task_id="demo-task",
        product_description="Demo description",
        insights=insights_payload,
        market_metrics=market_metrics,
    )

    assert "市场指标" in html_content
    assert "用户痛点" in html_content
    assert "竞争对手" in html_content
    assert "市场机会" in html_content
