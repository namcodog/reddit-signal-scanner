from __future__ import annotations


def test_admin_analysis_summary_requires_auth(client: "object") -> None:
    resp = client.get("/api/v1/admin/analysis/summary")
    assert resp.status_code in (401, 403)


def test_admin_analysis_detail_requires_auth(client: "object") -> None:
    resp = client.get("/api/v1/admin/analysis/00000000-0000-0000-0000-000000000000")
    assert resp.status_code in (401, 403)
