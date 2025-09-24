from __future__ import annotations

import uuid


def test_auth_register_and_health(client: "object") -> None:
    # auth health should be public
    h = client.get("/api/v1/auth/health")
    assert h.status_code in (200, 204)

    # register may return 200/201 or be a stub; tolerate both
    email = f"tester_{uuid.uuid4().hex[:8]}@example.com"
    payload = {"email": email, "password": "P@ssw0rd!"}
    r = client.post("/api/v1/auth/register", json=payload)
    assert r.status_code in (200, 201, 409)  # 409 already exists is acceptable in CI re-runs
