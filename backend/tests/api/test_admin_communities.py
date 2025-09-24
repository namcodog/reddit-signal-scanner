from __future__ import annotations


def test_admin_communities_summary_requires_auth(client: "object") -> None:
    resp = client.get("/api/v1/admin/communities/summary")
    assert resp.status_code in (401, 403)


def test_admin_community_decision_requires_auth(client: "object") -> None:
    payload = {
        "community": "r/startups",
        "action": "approve",
        "labels": ["状态:核心"],
        "reason": "高质量社区"
    }
    resp = client.post("/api/v1/admin/communities/decisions/community", json=payload)
    assert resp.status_code in (401, 403)


def test_admin_decisions_endpoint_requires_auth(client: "object") -> None:
    payload = {
        "community": "r/startups",
        "action": "approve",
        "labels": [],
    }
    resp = client.post("/api/v1/admin/decisions/community", json=payload)
    assert resp.status_code in (401, 403)
