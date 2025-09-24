from __future__ import annotations

import time


def test_analyze_create_and_query_paths(client: "object") -> None:
    # 创建分析任务（最小请求体，容错 200/201）
    payload = {"product_description": "A demo product for integration tests"}
    resp = client.post("/api/v1/analyze", json=payload)
    assert resp.status_code in (200, 201)

    data = resp.json()
    task_id = data.get("task_id") or data.get("id") or data.get("taskId")
    assert task_id is not None

    # 尝试查询报告草路径（可能未完成，允许 200/409/404）
    r = client.get(f"/api/v1/report/{task_id}")
    assert r.status_code in (200, 404, 409)
