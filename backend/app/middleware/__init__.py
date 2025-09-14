"""
中间件模块 - FastAPI认证和请求处理中间件

包含:
- JWT认证中间件
- 租户隔离中间件
- 性能监控中间件
- 错误处理中间件
"""

from .jwt_middleware import (
    JWTAuthenticator,
    JWTMiddleware,
    create_jwt_middleware_config,
    get_current_user_from_request,
    get_tenant_id_from_request,
    get_user_id_from_request,
    has_permission_in_request,
    install_jwt_middleware,
)

__all__ = [
    "JWTMiddleware",
    "JWTAuthenticator",
    "install_jwt_middleware",
    "create_jwt_middleware_config",
    "get_current_user_from_request",
    "get_user_id_from_request",
    "get_tenant_id_from_request",
    "has_permission_in_request",
]
