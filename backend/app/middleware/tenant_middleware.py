"""Reddit Signal Scanner - 多租户中间件

Linus设计原则："统一的责任链 + 自动化管理"
- 请求级别的租户上下文管理
- 从认证信息自动获取用户ID
- 无缝集成现有认证系统
- 异常情况下的防御性设计
"""

import logging
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..core.auth import AuthenticationError
from ..core.tenant_isolation import (
    TenantContext,
    create_tenant_context_from_user,
    get_current_tenant_context,
    set_tenant_context,
)
from ..core.user_context import get_current_user_context

if TYPE_CHECKING:
    from ..core.user_context import UserContext

# 日志记录器
_logger = logging.getLogger(__name__)


class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """
    多租户数据隔离中间件

    负责在请求处理过程中设置和管理租户上下文，
    确保数据库查询自动应用租户过滤。
    """

    def __init__(
        self,
        app: ASGIApp,
        skip_paths: Optional[list[str]] = None,
        require_tenant: bool = True,
    ) -> None:
        """
        初始化租户中间件

        Args:
            app: ASGI应用
            skip_paths: 跳过租户检查的路径列表
            require_tenant: 是否强制要求租户上下文
        """
        super().__init__(app)
        self.skip_paths = skip_paths or [
            "/health",
            "/metrics",
            "/docs",
            "/openapi.json",
            "/favicon.ico",
            "/",
        ]
        self.require_tenant = require_tenant

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """
        中间件核心逻辑：设置租户上下文后处理请求
        """
        # 检查是否跳过租户检查
        if self._should_skip_path(request.url.path):
            return await call_next(request)

        # 初始化租户上下文
        tenant_context = None
        try:
            tenant_context = await self._setup_tenant_context(request)
            _logger.debug("租户上下文已设置: %s", tenant_context)

        except AuthenticationError as e:
            _logger.warning(f"认证失败: {e}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required for tenant access"},
            )
        except TenantAccessError as e:
            _logger.warning(f"租户访问被拒绝: {e}")
            return JSONResponse(
                status_code=403,
                content={"detail": str(e)},
            )
        except Exception as e:
            _logger.error(f"租户上下文设置失败: {e}")
            if self.require_tenant:
                return JSONResponse(
                    status_code=500,
                    content={"detail": "Tenant context setup failed"},
                )

        try:
            # 处理请求
            response = await call_next(request)
            return response

        finally:
            # 清理租户上下文
            set_tenant_context(None)
            if tenant_context:
                _logger.debug("租户上下文已清理: %s", tenant_context.user_id)

    def _should_skip_path(self, path: str) -> bool:
        """判断是否跳过指定路径"""
        return any(path.startswith(skip_path) for skip_path in self.skip_paths)

    async def _setup_tenant_context(self, request: Request) -> Optional[TenantContext]:
        """
        设置租户上下文

        从请求中获取用户信息，然后创建和设置租户上下文
        """
        # 获取当前用户上下文（始终返回一个上下文，匿名或认证）
        user_context = get_current_user_context()

        # 若为匿名且需要强制认证，尝试从请求提取用户信息
        if user_context.is_anonymous:
            extracted = await self._extract_user_from_request(request)
            if extracted is not None:
                user_context = extracted

        # 若仍匿名且要求租户，则报错
        if self.require_tenant and user_context.is_anonymous:
            raise AuthenticationError("缺少用户认证信息")

        # 创建租户上下文
        tenant_context = create_tenant_context_from_user(user_context)

        # 设置全局租户上下文
        set_tenant_context(tenant_context)

        return tenant_context

    async def _extract_user_from_request(
        self, request: Request
    ) -> Optional["UserContext"]:
        """
        从请求中提取用户信息

        集成现有的认证系统，从 JWT token 或其他认证方式中
        获取用户信息。
        """
        try:
            # 尝试使用现有的JWT中间件的功能
            from ..middleware.jwt_middleware import get_user_context_contract

            # 尝试获取用户上下文合约
            # jwt_middleware.get_user_context_contract 是同步函数
            user_contract = get_user_context_contract(request)
            if user_contract and getattr(user_contract, "user_id", None):
                # 从 UserContext 创建
                from ..core.user_context import UserContext

                return UserContext(
                    user_id=user_contract.user_id,
                    is_anonymous=False,
                    user_data={},
                )
        except Exception as e:
            _logger.debug(f"从 JWT获取用户信息失败: {e}")

        # 如果没有JWT，尝试从 Header 获取用户ID
        user_id = request.headers.get("X-User-ID")
        if user_id:
            from ..core.user_context import UserContext

            return UserContext(user_id=user_id, is_anonymous=False, user_data={})

        # 如果都没有，返回匿名用户（仅在非强制模式下）
        if not self.require_tenant:
            from ..core.user_context import UserContext

            return UserContext(is_anonymous=True)

        return None


class TenantAccessError(Exception):
    """租户访问错误"""

    pass


# 便捷函数用于验证租户访问权限
async def require_tenant_access(
    request: Request, required_user_id: Optional[str] = None
) -> TenantContext:
    """
    要求租户访问权限，用于路由处理函数

    Args:
        request: FastAPI请求对象
        required_user_id: 要求的用户ID（可选）

    Returns:
        TenantContext: 当前租户上下文

    Raises:
        TenantAccessError: 如果没有租户访问权限
    """
    tenant_context = get_current_tenant_context()

    if tenant_context is None:
        raise TenantAccessError("缺少租户上下文")

    # 系统用户可以访问所有数据
    if tenant_context.is_system:
        return tenant_context

    # 检查用户ID是否匹配
    if required_user_id and tenant_context.user_id != required_user_id:
        raise TenantAccessError(f"无法访问用户 {required_user_id} 的数据")

    return tenant_context


# 装饰器版本 - 用于路由函数
def require_tenant(required_user_id: Optional[str] = None) -> Callable[[Any], Any]:
    """
    租户访问权限装饰器

    Usage:
        @router.get("/tasks")
        @require_tenant()
        async def get_user_tasks():
            # 此时会自动应用租户过滤
            return await session.execute(select(Task))
    """

    def decorator(func: Any) -> Any:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # 从参数中找到Request对象
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if request:
                await require_tenant_access(request, required_user_id)

            return await func(*args, **kwargs)

        return wrapper

    return decorator


# ====================================================================
# 公开API
# ====================================================================

__all__ = [
    "TenantIsolationMiddleware",
    "TenantAccessError",
    "require_tenant_access",
    "require_tenant",
]
