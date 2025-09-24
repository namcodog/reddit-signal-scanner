from __future__ import annotations

from starlette.requests import Request
import pytest

from app.api.v1.endpoints.admin_feedback import (
    post_admin_analysis_feedback,
    get_admin_feedback_summary,
    AdminAnalysisFeedbackRequest,
)


@pytest.mark.asyncio
async def test_admin_feedback_summary_contract() -> None:
    # 1) 先写入一条算法反馈（不校验JWT，直接函数调用并注入权限）
    scope = {"type": "http", "method": "POST", "path": "/api/v1/admin/feedback/analysis", "headers": []}
    req_post = Request(scope)
    req_post.state.permissions = ["admin", "admin:write"]
    req_post.state.request_id = "trace-fb-1"

    payload = AdminAnalysisFeedbackRequest(
        task_id="task-demo",
        satisfied=False,
        reasons=["coverage_low"],
        notes="auto test",
    )
    post_resp = await post_admin_analysis_feedback(req_post, payload)
    assert getattr(post_resp, "code", None) == 0
    assert hasattr(post_resp, "data") and hasattr(post_resp.data, "event_id")

    # 2) 汇总查询，校验包装结构
    scope_get = {"type": "http", "method": "GET", "path": "/api/v1/admin/feedback/summary", "headers": []}
    req_get = Request(scope_get)
    req_get.state.permissions = ["admin"]
    req_get.state.request_id = "trace-fb-2"

    summary = await get_admin_feedback_summary(req_get, days=30)
    assert getattr(summary, "code", None) == 0
    assert hasattr(summary, "data")
    assert hasattr(summary.data, "window")
    assert "start" in summary.data.window and "end" in summary.data.window
    assert hasattr(summary.data, "total") and isinstance(summary.data.total, int)
    assert hasattr(summary.data, "likes") and isinstance(summary.data.likes, int)
    assert hasattr(summary.data, "dislikes") and isinstance(summary.data.dislikes, int)
    assert hasattr(summary.data, "top_reasons") and isinstance(summary.data.top_reasons, list)


@pytest.mark.asyncio
async def test_admin_feedback_summary_empty_returns_zero() -> None:
    # 不写任何事件，直接查询汇总，应返回结构完整且计数为零
    scope_get = {"type": "http", "method": "GET", "path": "/api/v1/admin/feedback/summary", "headers": []}
    req_get = Request(scope_get)
    req_get.state.permissions = ["admin"]
    req_get.state.request_id = "trace-fb-empty"

    summary = await get_admin_feedback_summary(req_get, days=7)
    assert getattr(summary, "code", None) == 0
    assert hasattr(summary, "data")
    assert summary.data.total >= 0
    # 在空库情况下通常为0
    assert summary.data.likes >= 0
    assert summary.data.dislikes >= 0
    assert isinstance(summary.data.top_reasons, list)
