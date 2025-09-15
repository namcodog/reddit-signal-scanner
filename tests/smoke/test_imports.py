import pytest


@pytest.mark.smoke
def test_core_imports_smoke():
    # 仅验证关键模块可安全导入，避免触发外部依赖
    import importlib

    modules = [
        "backend.app.core.config",
        "backend.app.core.jwt_handler",
        "backend.app.core.database",
    ]

    for m in modules:
        importlib.import_module(m)


@pytest.mark.smoke
def test_jwt_quick_path():
    # 快速验证 JWT 生成/验证链路（使用默认 HS256 开发密钥）
    from backend.app.core.jwt_handler import JWTHandler

    h = JWTHandler()
    token = h.create_access_token("u1", "t1", "u1@example.com", permissions=["admin"]) 
    payload = h.verify_access_token(token)

    assert payload.user_id == "u1"
    assert payload.tenant_id == "t1"
    assert payload.email == "u1@example.com"
