from __future__ import annotations


def test_admin_feedback_export_requires_auth(client: "object") -> None:
    # 未携带JWT时，应被鉴权层拦截（401）或权限层拒绝（403）
    resp = client.get("/api/v1/admin/feedback/export")
    assert resp.status_code in (401, 403)
