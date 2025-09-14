"""
JWT认证中间件 - Linus式极简实现

核心理念：
- 100行代码搞定认证
- 无缓存层，JWT本就无状态
- 直线逻辑，无深层嵌套
- 数据结构优先，性能第一
"""

import logging
from typing import Any, Awaitable, Callable, Optional, Set, cast

import jwt
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..core.auth_context import AuthContext, AuthError, TenantError
from ..core.config import get_settings

logger = logging.getLogger(__name__)


class JWTMiddleware(BaseHTTPMiddleware):
    """
    JWT认证中间件 - Linus式简洁实现

    设计原则：
    1. 一个函数搞定认证
    2. 无缓存，JWT就是无状态的
    3. 直线逻辑，不超过2层嵌套
    """

    # 跳过认证的路径 - 静态集合，O(1)查找
    SKIP_PATHS: Set[str] = {
        "/",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/api",  # 冒烟用途：临时放行API根路径
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/refresh",
    }

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.settings = get_settings()
        self.secret_key = self.settings.jwt_secret_key
        logger.info("JWT中间件已初始化 - Linus简化版")

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """中间件核心 - 20行搞定所有逻辑"""

        # 跳过无需认证的路径
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        # 认证逻辑 - 成功则注入，失败则返回错误
        auth = self._authenticate(request)
        if auth is None:
            return self._auth_error_response("认证失败")

        if auth.is_expired():
            return self._auth_error_response("Token已过期")

        # 注入认证上下文
        request.state.auth = auth
        request.state.user_id = auth.user_id
        request.state.tenant_id = auth.tenant_id

        return await call_next(request)

    def _authenticate(self, request: Request) -> Optional[AuthContext]:
        """
        核心认证函数 - Linus式直线逻辑

        返回 AuthContext 或 None，无异常抛出
        """
        # 提取Token
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return None

        token = auth_header.removeprefix("Bearer ")
        if not token:
            return None

        # 验证Token并创建上下文
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            return AuthContext.from_jwt_payload(payload)

        except jwt.InvalidTokenError:
            return None

    def _auth_error_response(self, message: str) -> JSONResponse:
        """统一认证错误响应"""
        return JSONResponse(
            status_code=401,
            content={"detail": message},
            headers={"WWW-Authenticate": "Bearer"},
        )


# 便捷的认证检查函数 - 替代复杂的依赖注入
def get_auth(request: Request) -> AuthContext:
    """获取认证上下文，失败抛异常"""
    auth = cast(Optional[AuthContext], getattr(request.state, "auth", None))
    if auth is None:
        raise AuthError("用户未认证")
    return auth


def require_permission(request: Request, perm_mask: int) -> AuthContext:
    """要求特定权限"""
    auth = get_auth(request)
    if not auth.has_permission(perm_mask):
        raise AuthError(f"权限不足，需要权限码: {perm_mask}")
    return auth


def require_tenant_access(request: Request, tenant_id: str) -> AuthContext:
    """要求租户访问权限"""
    auth = get_auth(request)
    if not auth.belongs_to_tenant(tenant_id):
        raise TenantError(f"无权访问租户: {tenant_id}")
    return auth


def require_admin(request: Request) -> AuthContext:
    """要求管理员权限"""
    auth = get_auth(request)
    if not auth.is_admin():
        raise AuthError("需要管理员权限")
    return auth


# 安装函数
def install_jwt_middleware(app: FastAPI) -> None:
    """安装JWT中间件"""
    app.add_middleware(JWTMiddleware)
    logger.info("JWT中间件已安装 - Linus极简版")
