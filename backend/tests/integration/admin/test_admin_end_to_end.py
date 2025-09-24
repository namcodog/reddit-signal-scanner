from __future__ import annotations

import io
import yaml


def test_decision_to_patch_and_feedback_summary(monkeypatch: "object", client: "object") -> None:
    # 允许访问（跳过权限）
    import app.middleware.jwt_middleware as jm
    import app.api.v1.endpoints.admin_decisions as dec_mod
    import app.api.v1.endpoints.admin_patch as patch_mod
    import app.api.v1.endpoints.admin_feedback as fb_mod

    for mod in (jm, dec_mod, patch_mod, fb_mod):
        monkeypatch.setattr(mod, "has_permission_in_request", lambda *a, **k: True, raising=False)

    # 1) 社区决策两条
    r1 = client.post(
        "/api/v1/admin/decisions/community",
        json={"community": "r/startups", "action": "approve", "labels": ["状态:核心"]},
    )
    assert r1.status_code == 200 and r1.json().get("code") == 0
    r2 = client.post(
        "/api/v1/admin/decisions/community",
        json={"community": "r/technology", "action": "blacklist", "labels": ["状态:黑名单"]},
    )
    assert r2.status_code == 200 and r2.json().get("code") == 0

    # 2) 导出 Patch（YAML）
    y = client.get("/api/v1/admin/config/patch")
    assert y.status_code == 200 and y.headers.get("content-type", "").startswith("text/yaml")
    data = yaml.safe_load(io.StringIO(y.text))
    assert "core" in data and "blacklist" in data and "labels" in data
    assert "r/startups" in data["core"] and "r/technology" in data["blacklist"]

    # 3) 写入算法反馈并汇总
    rf = client.post(
        "/api/v1/admin/feedback/analysis",
        json={"task_id": "tsk_e2e", "satisfied": False, "reasons": ["coverage_low"], "notes": "e2e"},
    )
    assert rf.status_code == 200 and rf.json().get("code") == 0
    sf = client.get("/api/v1/admin/feedback/summary?days=30")
    assert sf.status_code == 200
    body = sf.json()
    assert body.get("code") == 0 and "data" in body
    assert isinstance(body["data"].get("total", 0), int)
