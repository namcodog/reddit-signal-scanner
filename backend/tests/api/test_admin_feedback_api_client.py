from __future__ import annotations

def test_admin_feedback_api_with_testclient(monkeypatch: "object", client: "object", sync_db_session: "object") -> None:
    # 绕过权限：同时猴补中间件模块与端点模块内的引用
    import app.middleware.jwt_middleware as jm
    import app.api.v1.endpoints.admin_feedback as mod

    monkeypatch.setattr(jm, "has_permission_in_request", lambda *args, **kwargs: True, raising=False)
    monkeypatch.setattr(mod, "has_permission_in_request", lambda *args, **kwargs: True, raising=False)

    # 1) 写入一条算法反馈
    resp_post = client.post(
        "/api/v1/admin/feedback/analysis",
        json={
            "task_id": "task-demo-client",
            "satisfied": False,
            "reasons": ["coverage_low", "dup_high"],
            "notes": "client test",
        },
    )
    assert resp_post.status_code == 200
    body_post = resp_post.json()
    assert body_post.get("code") == 0
    assert "data" in body_post and "event_id" in body_post["data"]

    # 2) 查询汇总，校验包装结构
    resp_get = client.get("/api/v1/admin/feedback/summary?days=30")
    assert resp_get.status_code == 200
    body_get = resp_get.json()
    assert body_get.get("code") == 0
    assert "data" in body_get
    data = body_get["data"]
    assert "window" in data and "start" in data["window"] and "end" in data["window"]
    assert isinstance(data.get("total", 0), int)
    assert isinstance(data.get("likes", 0), int)
    assert isinstance(data.get("dislikes", 0), int)
    assert isinstance(data.get("top_reasons", []), list)
