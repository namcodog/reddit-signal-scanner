from __future__ import annotations

import io
import yaml


def test_system_admin_patch_flow(monkeypatch: "object", client: "object") -> None:
    # 跳过鉴权
    import app.middleware.jwt_middleware as jm
    import app.api.v1.endpoints.admin_decisions as dec_mod
    import app.api.v1.endpoints.admin_patch as patch_mod
    for mod in (jm, dec_mod, patch_mod):
        monkeypatch.setattr(mod, "has_permission_in_request", lambda *a, **k: True, raising=False)

    # 做一次 approve + blacklist
    client.post("/api/v1/admin/decisions/community", json={"community": "r/sys_flow", "action": "approve"})
    client.post("/api/v1/admin/decisions/community", json={"community": "r/sys_black", "action": "blacklist"})

    resp = client.get("/api/v1/admin/config/patch")
    assert resp.status_code == 200
    y = yaml.safe_load(io.StringIO(resp.text))
    assert "r/sys_flow" in y.get("core", [])
    assert "r/sys_black" in y.get("blacklist", [])
