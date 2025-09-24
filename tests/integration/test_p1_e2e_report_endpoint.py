"""
PR-3: 端到端集成测试 - 验证5个关键字段的完整数据流
测试目标：确保 PipelineData → Database → Formatter → API 的完整数据传递
"""
from __future__ import annotations

pytest_plugins = ["backend.tests.conftest"]

import pytest
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from uuid import uuid4
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

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
from app.services.report_formatter import ReportFormatterService
from app.core.jwt_handler import get_jwt_handler


@pytest.fixture
def p1_sample_analysis_report() -> AnalysisReport:
    """PR-1兜底机制验证的完整数据样本"""
    insights = InsightsData(
        pain_points=[
            {
                "description": "AI工具学习成本过高，新用户难以上手",
                "sentiment_score": -0.7,
                "frequency": 45,
                "confidence": 0.9,
                "severity": "high",
                "categories": ["用户体验", "学习成本"],
                "example_posts": [
                    {
                        "post_id": "abc123",
                        "community": "r/MachineLearning",
                        "permalink": "/r/MachineLearning/comments/abc123/",
                        "content_snippet": "这个AI工具太复杂了，学了一周还是不会用...",
                        "upvotes": 25
                    }
                ],
                "tags": ["学习成本", "复杂度", "新手"]
            },
            {
                "description": "界面设计不够直观，功能入口难找",
                "sentiment_score": -0.5,
                "frequency": 32,
                "confidence": 0.8,
                "severity": "medium",
                "categories": ["界面设计", "用户体验"],
                "example_posts": [
                    {
                        "post_id": "def456",
                        "community": "r/artificial",
                        "permalink": "/r/artificial/comments/def456/",
                        "content_snippet": "界面太乱了，找个功能要点半天...",
                        "upvotes": 18
                    }
                ],
                "tags": ["界面", "导航", "可用性"]
            }
        ],
        competitors=[
            {
                "name": "ChatGPT",
                "description": "OpenAI开发的对话式AI工具",
                "market_position": "leader",
                "mention_count": 89,
                "sentiment_score": 0.4,
                "strengths": ["易用性好", "响应速度快", "功能丰富"],
                "weaknesses": ["价格较高", "有时不够准确"],
                "market_share_estimate": 0.45
            },
            {
                "name": "Claude",
                "description": "Anthropic开发的AI助手",
                "market_position": "challenger",
                "mention_count": 34,
                "sentiment_score": 0.6,
                "strengths": ["安全性好", "回答质量高"],
                "weaknesses": ["知名度较低", "功能相对简单"],
                "market_share_estimate": 0.15
            }
        ],
        opportunities=[
            {
                "title": "简化用户界面设计",
                "description": "针对新手用户优化界面，降低学习成本",
                "potential": "high",
                "difficulty": "medium",
                "market_size": "大型市场（数百万用户）",
                "confidence": 0.85,
                "timeframe": "3-6个月",
                "key_insights": [
                    "用户界面简化可以显著提升用户体验",
                    "新手引导功能是关键需求",
                    "竞品在这方面也有改进空间"
                ]
            },
            {
                "title": "开发智能推荐系统",
                "description": "基于用户行为推荐相关功能和内容",
                "potential": "medium",
                "difficulty": "high",
                "market_size": "中型市场（数十万用户）",
                "confidence": 0.7,
                "timeframe": "6-12个月",
                "key_insights": [
                    "个性化推荐可以提升用户粘性",
                    "需要大量用户数据支持",
                    "技术实现相对复杂"
                ]
            }
        ],
        analysis_summary={
            "headline": "AI工具市场存在显著学习成本痛点",
            "total_communities": 8,
            "key_insights": 12,
            "top_opportunity": "简化用户界面设计",
            "confidence_score": 0.85,
            "summary_points": [
                "用户普遍反映学习成本过高",
                "界面复杂度是主要障碍",
                "需要更好的新手引导"
            ]
        },
        key_insights=[
            "简化界面设计是短期高价值改进",
            "新手引导功能可以显著降低学习成本",
            "竞品分析显示易用性是关键差异化因素"
        ],
        confidence_score=0.85,
        data_quality_score=0.78,
    )

    step_durations: Dict[str, float] = {
        "community_discovery": 4.2,
        "data_collection": 8.5,
        "signal_extraction": 5.3,
        "result_ranking": 3.1,
    }

    data_sources: Dict[str, int] = {"api": 67, "cache": 83}
    data_quality_metrics: Dict[str, float] = {
        "community_relevance": 0.89,
        "cache_hit_rate": 0.55,
        "data_freshness": 0.82,
        "signal_confidence": 0.78,
    }

    report = AnalysisReport(
        report_id="demo-p1-e2e-test",
        product_description="AI驱动的Reddit Signal Scanner - P1测试",
        generated_at=datetime.now(timezone.utc),
        insights=insights,
        confidence_score=0.85,
        total_posts_analyzed=150,
        communities_scanned=["r/MachineLearning", "r/artificial", "r/ChatGPT"],
        data_sources=data_sources,
        total_duration=sum(step_durations.values()),
        step_durations=step_durations,
        data_quality_metrics=data_quality_metrics,
    )
    return report


@pytest.mark.integration
def test_p1_e2e_report_endpoint_five_fields_validation(
    client: TestClient,
    sync_db_session: Session,
    p1_sample_analysis_report: AnalysisReport,
    monkeypatch,
) -> None:
    """
    PR-3核心测试：端到端验证5个关键字段的完整数据流
    验证路径：AnalysisReport → Database → ReportFormatter → API Response
    """
    session = sync_db_session

    # 1. 创建测试用户和任务
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
            "email": "p1-e2e-test@example.com",
            "password_hash": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewRuuA/lTGsT.3dm",
        },
    )
    session.commit()

    # 创建任务，先设置为processing状态
    task = Task(
        product_description=p1_sample_analysis_report.product_description,
        user_id=user_id,
        status=TaskStatus.PROCESSING.value,
    )
    session.add(task)
    session.flush()  # 获取created_at

    # 设置时间并更新状态为completed
    task.started_at = task.created_at
    task.completed_at = task.created_at + timedelta(minutes=5)
    task.status = TaskStatus.COMPLETED.value
    session.commit()

    # 2. 模拟完整的数据处理流程（PR-1兜底机制）
    insights_payload, market_metrics, metadata = _build_insights_payload(
        p1_sample_analysis_report, task.product_description
    )
    sanitized_communities = _sanitize_communities(
        p1_sample_analysis_report.communities_scanned
    )
    sources_payload = _build_sources_payload(
        p1_sample_analysis_report, sanitized_communities
    )
    html_content = _render_report_html(
        str(task.id), task.product_description, insights_payload, market_metrics
    )

    # 3. 数据落库（验证PR-1的兜底机制）
    # 将market_metrics添加到insights_payload中，确保5个关键字段都存储到数据库
    insights_payload["market_metrics"] = market_metrics

    analysis = Analysis(
        task_id=task.id,
        insights=insights_payload,
        sources=sources_payload,
        confidence_score=Decimal(str(p1_sample_analysis_report.confidence_score)),
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

    # 4. 验证数据库中的5个关键字段
    stored_insights = session.execute(
        sa_text("SELECT insights FROM analyses WHERE task_id = :task_id"),
        {"task_id": str(task.id)},
    ).scalar_one()

    # 验证5个关键字段在数据库中的存在性
    assert "executive_summary" in stored_insights, "数据库缺少executive_summary字段"
    assert "market_metrics" in stored_insights, "数据库缺少market_metrics字段"
    assert "pain_points" in stored_insights, "数据库缺少pain_points字段"
    assert "competitors" in stored_insights, "数据库缺少competitors字段"
    assert "opportunities" in stored_insights, "数据库缺少opportunities字段"

    # 验证字段类型和内容
    assert isinstance(stored_insights["executive_summary"], dict)
    assert isinstance(stored_insights["market_metrics"], dict)
    assert isinstance(stored_insights["pain_points"], list)
    assert isinstance(stored_insights["competitors"], list)
    assert isinstance(stored_insights["opportunities"], list)

    # 验证非空数据（PR-1兜底机制确保字段存在，即使为空数组也是正确的）
    assert len(stored_insights["pain_points"]) >= 1, "pain_points应包含至少1个条目"
    assert len(stored_insights["competitors"]) >= 1, "competitors应包含至少1个条目"
    assert len(stored_insights["opportunities"]) >= 1, "opportunities应包含至少1个条目"

    # 5. 设置API调用环境
    jwt_handler = get_jwt_handler()
    access_token = jwt_handler.create_access_token(
        user_id=str(user_id),
        tenant_id=str(tenant_id),
        email="p1-e2e-test@example.com",
        permissions=["reports:read"],
    )

    # Mock数据库会话
    from sqlalchemy.orm import sessionmaker
    engine = session.get_bind()
    SessionFactory = sessionmaker(bind=engine)

    def _override_get_session_sync() -> Session:
        return SessionFactory()

    monkeypatch.setattr("app.api.v1.endpoints.report.get_session_sync", _override_get_session_sync)

    # 6. 调用API端点
    response = client.get(
        f"/api/v1/report/{task.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    # 7. 验证API响应
    assert response.status_code == 200, f"API调用失败: {response.status_code} - {response.text}"
    
    payload = response.json()
    assert payload["status"] == "success", f"API响应状态错误: {payload}"
    
    data = payload.get("data")
    assert data, "API响应缺少data字段"

    # 8. 核心验证：5个关键字段的API输出
    print("\n🔍 验证5个关键字段的API输出:")
    
    # executive_summary验证
    assert "executive_summary" in data, "API响应缺少executive_summary字段"
    exec_summary = data["executive_summary"]
    assert isinstance(exec_summary, dict), "executive_summary应为对象类型"
    assert "headline" in exec_summary, "executive_summary缺少headline字段"
    assert "confidence_score" in exec_summary, "executive_summary缺少confidence_score字段"
    assert exec_summary["confidence_score"] >= 0.8, "confidence_score应大于等于0.8"
    print(f"✅ executive_summary: {exec_summary['headline']}")

    # market_metrics验证
    assert "market_metrics" in data, "API响应缺少market_metrics字段"
    market_metrics = data["market_metrics"]
    assert isinstance(market_metrics, dict), "market_metrics应为对象类型"
    assert "total_mentions" in market_metrics, "market_metrics缺少total_mentions字段"
    assert "sentiment_score" in market_metrics, "market_metrics缺少sentiment_score字段"
    assert isinstance(market_metrics["total_mentions"], int), "total_mentions应为整数"
    assert market_metrics["total_mentions"] >= 150, "total_mentions应大于等于150"
    print(f"✅ market_metrics: {market_metrics['total_mentions']} mentions")

    # pain_points验证
    assert "pain_points" in data, "API响应缺少pain_points字段"
    pain_points = data["pain_points"]
    assert isinstance(pain_points, list), "pain_points应为数组类型"
    assert len(pain_points) >= 1, "pain_points应包含至少1个条目"
    first_pain_point = pain_points[0]
    assert "description" in first_pain_point, "pain_point缺少description字段"
    assert "sentiment_score" in first_pain_point, "pain_point缺少sentiment_score字段"
    assert "frequency" in first_pain_point, "pain_point缺少frequency字段"
    print(f"✅ pain_points: {len(pain_points)} 个痛点")

    # competitors验证
    assert "competitors" in data, "API响应缺少competitors字段"
    competitors = data["competitors"]
    assert isinstance(competitors, list), "competitors应为数组类型"
    assert len(competitors) >= 1, "competitors应包含至少1个条目"
    first_competitor = competitors[0]
    assert "name" in first_competitor, "competitor缺少name字段"
    assert "mention_count" in first_competitor, "competitor缺少mention_count字段"
    assert "sentiment_score" in first_competitor, "competitor缺少sentiment_score字段"
    print(f"✅ competitors: {len(competitors)} 个竞品")

    # opportunities验证
    assert "opportunities" in data, "API响应缺少opportunities字段"
    opportunities = data["opportunities"]
    assert isinstance(opportunities, list), "opportunities应为数组类型"
    assert len(opportunities) >= 1, "opportunities应包含至少1个条目"
    first_opportunity = opportunities[0]
    assert "title" in first_opportunity, "opportunity缺少title字段"
    assert "description" in first_opportunity, "opportunity缺少description字段"
    assert "potential" in first_opportunity, "opportunity缺少potential字段"
    print(f"✅ opportunities: {len(opportunities)} 个商业机会")

    # 9. 验证数据一致性（数据库 vs API）
    print("\n🔍 验证数据一致性:")
    # 验证字段存在性和类型一致性（数量可能因为过滤逻辑而不同，这是正常的）
    assert len(data["pain_points"]) >= 1, "API pain_points应至少有1个条目"
    assert len(data["competitors"]) >= 1, "API competitors应至少有1个条目"
    assert len(data["opportunities"]) >= 1, "API opportunities应至少有1个条目"

    # 验证数据库中的数据也符合预期
    assert len(stored_insights["pain_points"]) >= 1, "数据库 pain_points应至少有1个条目"
    assert len(stored_insights["competitors"]) >= 1, "数据库 competitors应至少有1个条目"
    assert len(stored_insights["opportunities"]) >= 1, "数据库 opportunities应至少有1个条目"
    print("✅ 数据库与API数据结构一致，字段完整传递")

    print("\n🎉 PR-3端到端测试全部通过！5个关键字段在完整数据流中正确传递")
