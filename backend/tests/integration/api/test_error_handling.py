from __future__ import annotations


def test_protected_endpoint_without_auth_returns_401_or_403(client: "object") -> None:
    r = client.get("/api/v1/admin/communities/summary")
    assert r.status_code in (401, 403)


def test_invalid_endpoint_returns_404(client: "object") -> None:
    r = client.get("/api/v1/does-not-exist")
    assert r.status_code == 404
