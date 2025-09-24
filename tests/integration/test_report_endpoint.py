from __future__ import annotations

pytest_plugins = ["backend.tests.conftest"]

from datetime import datetime, timedelta, timezone
from typing import Dict
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from decimal import Decimal

from app.models.analysis import Analysis
from app.models.analysis_pipeline import AnalysisReport, InsightsData
from app.models.report import Report
from app.models.task import Task, TaskStatus
from app.tasks.analysis_tasks import (
    _build_insights_payload,
    _build_sources_payload,
    _render_report_html,
    _sanitize_communities,
)
from app.services.report_formatter import ReportFormatterService, get_formatted_report
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session, sessionmaker
from app.core.jwt_handler import get_jwt_handler


@pytest.fixture
def sample_analysis_report() -> AnalysisReport:
    insights = InsightsData(
        pain_points=[
            {
                "description": "用户反馈初始设置复杂，缺少逐步引导",
                "sentiment_score": -0.58,
                "frequency": 34,
                "evidence_posts": ["post-1", "post-2"],
                "categories": ["onboarding", "usability"],
                "tags": ["setup"],
            }
        ],
        competitors=[
            {
                "name": "Competitor Alpha",
                "mention_count": 21,
                "sentiment_score": 0.24,
                "strengths": ["生态完善", "品牌知名度"],
                "weaknesses": ["价格昂贵", "学习曲线陡峭"],
                "market_position": "leader",
            }
        ],
        opportunities=[
            {
                "title": "引入智能化的信号监控中心",
                "description": "提供跨社区的关键词报警和竞品联动分析",
                "market_size_indicator": "large",
                "urgency_score": 0.78,
                "feasibility_score": 0.66,
                "related_keywords": ["automation", "alerting"],
                "target_communities": ["r/startups", "r/marketing"],
                "estimated_demand": 1800,
            }
        ],
        analysis_summary={
            "headline": "自动化监控与协作整合是近期最高优先级",
            "summary_points": [
                "用户在初始设置时急需可视化指引",
                "竞品在整合能力上领先但价格不具优势",
                "跨团队协作的实时洞察是最大的增量空间",
            ],
        },
        key_insights=[
            "自动化预警是短期高价值能力",
            "深度协作集成提升团队留存",
            "模板化上手降低实施阻力",
        ],
        confidence_score=0.74,
        data_quality_score=0.68,
    )

    step_durations: Dict[str, float] = {
        "community_discovery": 3.6,
        "data_collection": 6.8,
        "signal_extraction": 4.1,
        "result_ranking": 2.9,
    }

    data_sources: Dict[str, int] = {"api": 45, "cache": 120}
    data_quality_metrics: Dict[str, float] = {
        "community_relevance": 0.81,
        "cache_hit_rate": 0.56,
        "data_freshness": 0.72,
        "signal_confidence": 0.69,
    }

    report = AnalysisReport(
        report_id="demo-p1-report",
        product_description="AI 驱动的 Reddit Signal Scanner",
        generated_at=datetime.now(timezone.utc),
        insights=insights,
        confidence_score=0.74,
        total_posts_analyzed=210,
        communities_scanned=["r/startups", "r/marketing", "r/SaaS"],
        data_sources=data_sources,
        total_duration=sum(step_durations.values()),
        step_durations=step_durations,
        data_quality_metrics=data_quality_metrics,
    )
    return report


def test_report_endpoint_returns_structured_data(
    client: TestClient,
    sync_db_session,
    sample_analysis_report: AnalysisReport,
    monkeypatch,
) -> None:
    session = sync_db_session

    tenant_id = uuid4()
    user_id = uuid4()
    session.execute(
        sa_text(
            """
            INSERT INTO users (id, tenant_id, email, password_hash)
            VALUES (CAST(:id AS uuid), CAST(:tenant_id AS uuid), :email, :password_hash)
            """
        ),
        {
            "id": str(user_id),
            "tenant_id": str(tenant_id),
            "email": "report-example@example.com",
            "password_hash": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        },
    )
    session.commit()

    started_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    completed_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    task = Task(
        product_description="AI 驱动的 Reddit Signal Scanner",
        user_id=user_id,
        status=TaskStatus.COMPLETED.value,
        started_at=started_at,
        completed_at=completed_at,
    )
    session.add(task)
    session.commit()

    insights_payload, market_metrics, metadata = _build_insights_payload(
        sample_analysis_report, task.product_description
    )
    sanitized_communities = _sanitize_communities(
        sample_analysis_report.communities_scanned
    )
    sources_payload = _build_sources_payload(
        sample_analysis_report, sanitized_communities
    )
    html_content = _render_report_html(
        str(task.id), task.product_description, insights_payload, market_metrics
    )

    analysis = Analysis(
        task_id=task.id,
        insights=insights_payload,
        sources=sources_payload,
        confidence_score=Decimal(str(sample_analysis_report.confidence_score)),
    )
    session.add(analysis)
    session.flush()

    report_record = Report(
        analysis_id=analysis.id,
        html_content=html_content,
        status="active",
    )
    session.add(report_record)
    session.commit()

    jwt_handler = get_jwt_handler()
    access_token = jwt_handler.create_access_token(
        user_id=str(user_id),
        tenant_id=str(tenant_id),
        email="report-example@example.com",
        permissions=["reports:read"],
    )

    stored_insights = session.execute(
        sa_text("SELECT insights FROM analyses WHERE task_id = :task_id"),
        {"task_id": str(task.id)},
    ).scalar_one()
    stored_sources = session.execute(
        sa_text("SELECT sources FROM analyses WHERE task_id = :task_id"),
        {"task_id": str(task.id)},
    ).scalar_one()
    assert stored_insights.get("pain_points"), "落库后应包含 pain_points"
    assert stored_sources.get("communities"), stored_sources
    assert (
        stored_insights.get("executive_summary", {}).get("confidence_score")
        is not None
    ), stored_insights.get("executive_summary")

    formatter = ReportFormatterService(session)
    raw_payload = formatter.get_complete_report(str(task.id))
    raw_exec_summary = raw_payload["data"]["executive_summary"]
    assert raw_exec_summary["confidence_score"] is not None, raw_exec_summary

    formatted_report = get_formatted_report(session, str(task.id), "full")
    assert (
        formatted_report.executive_summary.confidence_score is not None
    ), formatted_report.executive_summary

    engine = session.get_bind()
    SessionFactory = sessionmaker(bind=engine)

    def _override_get_session_sync() -> Session:
        return SessionFactory()

    monkeypatch.setattr("app.api.v1.endpoints.report.get_session_sync", _override_get_session_sync)

    response = client.get(
        f"/api/v1/report/{task.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if response.status_code != 200:
        pytest.fail(f"unexpected status {response.status_code}: {response.json()}")

    payload = response.json()
    assert payload["status"] == "success"
    data = payload.get("data")
    assert data, "响应中缺少 data 字段"
    assert data["task_id"] == str(task.id)
    assert data["market_metrics"]["total_mentions"] > 0
    if not data.get("pain_points"):
        pytest.fail(f"pain_points empty, payload keys: {list(data.keys())}")
    assert (
        data["executive_summary"]["confidence_score"] is not None
    ), data["executive_summary"]
    assert data["html_content"], "报告应包含 html_content"
    assert data["confidence_score"] >= 0
    assert data["data_coverage"]["communities"] >= 1

    assert isinstance(data["executive_summary"], dict)
    assert isinstance(data["executive_summary"].get("summary_points"), list)
    assert isinstance(data["market_metrics"], dict)
    assert isinstance(data["market_metrics"]["total_mentions"], int)
    assert data["market_metrics"]["total_mentions"] >= 0
    assert isinstance(data["market_metrics"]["sentiment_score"], float)
    assert isinstance(data["market_metrics"]["trending_keywords"], list)
    assert all(
        isinstance(keyword, str) for keyword in data["market_metrics"]["trending_keywords"]
    )
    assert isinstance(data["market_metrics"].get("sample_size"), int)
    sentiment_keys = set(data.get("sentiment_summary", {}).keys())
    assert {"positive", "neutral", "negative"}.issubset(sentiment_keys)

    assert isinstance(data["pain_points"], list)
    first_pain_point = data["pain_points"][0]
    assert first_pain_point["description"]
    assert first_pain_point["frequency"] >= 1
    assert isinstance(first_pain_point["sentiment_score"], float)

    assert isinstance(data["competitors"], list)
    first_competitor = data["competitors"][0]
    assert first_competitor["name"]
    assert isinstance(first_competitor["mention_count"], int)

    assert isinstance(data["opportunities"], list)
    first_opportunity = data["opportunities"][0]
    assert first_opportunity["title"]
    assert first_opportunity["description"].strip()
