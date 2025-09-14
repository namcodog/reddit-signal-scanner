"""
统一认证中间件 - 数据结构驱动的认证处理

Linus原则：
- 数据结构优先：MiddlewareConfigSchema统一配置
- 消除特殊情况：单一dispatch()处理所有请求
- 配置驱动：通过配置切换认证模式，零硬编码
- 向后兼容：保持现有JWT中间件功能不变
"""

import logging
import time
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Optional, Set, Union, Protocol, Type

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..core.auth import AuthenticationError, TenantAccessError
from ..core.v0_auth import V0AuthMiddleware
from ..middleware.jwt_middleware import JWTMiddleware
from ..schemas.responses.auth import UnifiedAuthContextResponse
from ..schemas.v0_auth import MiddlewareConfigSchema, V0AuthConfig
from ..core.config import get_settings

logger = logging.getLogger(__name__)


class UnifiedAuthMiddleware(BaseHTTPMiddleware):
    """
    统一认证中间件 - 零分支的认证处理架构

    核心设计：
    1. 配置驱动：通过MiddlewareConfigSchema决定行为
    2. 委托模式：复用现有JWTMiddleware逻辑
    3. 扩展支持：集成V0AuthMiddleware处理v0界面
    4. 统一响应：标准化的错误和成功响应格式
    """

    def __init__(self, app: ASGIApp, config: MiddlewareConfigSchema) -> None:
        super().__init__(app)
        self.config = config
        self.jwt_middleware = JWTMiddleware(app)
        self.v0_middleware = V0AuthMiddleware(config.v0_config)

        # 构建路径处理映射表 - 消除if-else判断
        self.path_handlers = self._build_path_handlers()

        logger.info(f"统一认证中间件已初始化: v0_enabled={config.v0_config.enable_guest_mode}")

    def _build_path_handlers(self) -> Dict[str, str]:
        """构建路径处理器映射 - 配置驱动的路径分发"""
        handlers = {}

        # JWT标准路径
        for path in self.config.skip_auth_paths:
            handlers[path] = "skip"

        # V0特殊路径
        if self.config.v0_config.enable_guest_mode:
            for path in self.config.v0_config.guest_allowed_paths:
                handlers[path] = "v0"
            for path in self.config.v0_config.optional_auth_paths:
                handlers[path] = "v0"

        return handlers

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """
        统一请求分发 - 表驱动的中间件处理
        """
        start_time = time.time()
        path = request.url.path

        # 确定处理模式 - 配置查表，零条件判断
        handler_type = self._determine_handler_type(path)

        # 委托处理 - 表驱动分发
        handler_map = {
            "skip": self._handle_skip_auth,
            "jwt": self._handle_jwt_auth,
            "v0": self._handle_v0_auth,
        }

        try:
            handler = handler_map[handler_type]
            response = await handler(request, call_next)

            self._log_request_performance(start_time, path, handler_type, "success")
            return response

        except Exception as e:
            response = self._handle_auth_exception(e, request)
            self._log_request_performance(start_time, path, handler_type, "error")
            return response

    def _determine_handler_type(self, path: str) -> str:
        """确定处理器类型 - 配置驱动判断"""
        # 精确匹配
        if path in self.path_handlers:
            return self.path_handlers[path]

        # 前缀匹配 - 系统路径
        system_prefixes = ["/docs", "/redoc", "/static", "/health"]
        if any(path.startswith(prefix) for prefix in system_prefixes):
            return "skip"

        # V0路径前缀匹配
        if self.config.v0_config.enable_guest_mode:
            settings = get_settings()
            v0_prefixes = [
                f"{settings.api_prefix}/analysis",
                f"{settings.api_prefix}/reports",
            ]
            if any(path.startswith(prefix) for prefix in v0_prefixes):
                return "v0"

        # 默认JWT认证
        return "jwt"

    async def _handle_skip_auth(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """处理跳过认证的请求"""
        return await call_next(request)

    async def _handle_jwt_auth(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """处理JWT认证请求 - 统一错误响应封装"""
        try:
            # 直接使用 JWTAuthenticator，失败时返回统一结构
            auth = await self.jwt_middleware.authenticator.authenticate(request)
            request.state.auth = auth
            request.state.user_id = auth.user_id
            request.state.tenant_id = auth.tenant_id
            request.state.permissions = auth.permissions
            return await call_next(request)
        except (AuthenticationError, TenantAccessError) as e:
            status = 401 if isinstance(e, AuthenticationError) else 403
            return self._create_auth_error_response(e, request, status)

    async def _handle_v0_auth(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """处理V0认证请求"""
        auth_result = await self.v0_middleware.process_request(request)

        # 注入标准认证状态供后续使用
        if auth_result.get("success") and auth_result.get("user"):
            user_data = auth_result["user"]
            request.state.user_id = user_data.get("user_id")
            request.state.tenant_id = user_data.get("tenant_id")
            request.state.permissions = user_data.get("permissions", [])

        return await call_next(request)

    def _handle_auth_exception(
        self, error: Exception, request: Request
    ) -> JSONResponse:
        """统一异常处理 - 标准化错误响应"""
        if isinstance(error, AuthenticationError):
            return self._create_auth_error_response(error, request, 401)

        if isinstance(error, TenantAccessError):
            return self._create_auth_error_response(error, request, 403)

        logger.error(f"未知认证异常: {error}", exc_info=True)
        return self._create_internal_error_response(request)

    def _create_auth_error_response(
        self, error: Exception, request: Request, status_code: int
    ) -> JSONResponse:
        """创建认证错误响应"""
        response_data = {
            "success": False,
            "access_level": "guest",
            "error": str(error),
            "path": request.url.path,
            "timestamp": datetime.now().isoformat(),
            "frontend_action": (
                "redirect_login" if status_code == 401 else "show_dialog"
            ),
        }

        headers = {}
        if status_code == 401:
            headers["WWW-Authenticate"] = "Bearer"

        return JSONResponse(
            status_code=status_code, content=response_data, headers=headers
        )

    def _create_internal_error_response(self, request: Request) -> JSONResponse:
        """创建内部错误响应"""
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "access_level": "guest",
                "error": "内部服务器错误",
                "path": request.url.path,
                "timestamp": datetime.now().isoformat(),
            },
        )

    def _log_request_performance(
        self, start_time: float, path: str, handler_type: str, result: str
    ) -> None:
        """记录请求性能"""
        if not self.config.enable_performance_logging:
            return

        duration_ms = (time.time() - start_time) * 1000

        if duration_ms > self.config.max_auth_time_ms:
            logger.warning(
                f"认证处理耗时过长: {duration_ms:.2f}ms, "
                f"path: {path}, handler: {handler_type}, result: {result}"
            )

        logger.debug(
            f"认证处理完成: {duration_ms:.2f}ms, "
            f"path: {path}, handler: {handler_type}, result: {result}"
        )


# ===== 中间件安装和配置工具 =====


def create_unified_auth_config(
    enable_v0: bool = True,
    v0_guest_paths: Optional[Set[str]] = None,
    additional_skip_paths: Optional[Set[str]] = None,
) -> MiddlewareConfigSchema:
    """创建统一认证中间件配置"""
    settings = get_settings()
    v0_config = V0AuthConfig(
        enable_guest_mode=enable_v0,
        guest_allowed_paths=v0_guest_paths
        or {
            f"{settings.api_prefix}/analysis/demo",
            f"{settings.api_prefix}/reports/public",
        },
    )

    config = MiddlewareConfigSchema(v0_config=v0_config)

    if additional_skip_paths:
        config.skip_auth_paths.update(additional_skip_paths)

    return config


class _MiddlewareCapableApp(Protocol):
    def add_middleware(self, middleware_class: Type[Any], **kwargs: Any) -> None:
        ...


def install_unified_auth_middleware(
    app: _MiddlewareCapableApp, config: Optional[MiddlewareConfigSchema] = None
) -> None:
    """
    安装统一认证中间件

    使用示例:
        config = create_unified_auth_config(enable_v0=True)
        install_unified_auth_middleware(app, config)
    """
    actual_config = config or create_unified_auth_config()

    # Starlette/FASTAPI: add_middleware expects a class and kwargs; ASGIApp ensures type safety
    app.add_middleware(UnifiedAuthMiddleware, config=actual_config)
    logger.info("统一认证中间件已安装")


# ===== 便捷函数 =====


def get_unified_auth_context(request: Request) -> UnifiedAuthContextResponse:
    """获取统一认证上下文信息 - 类型安全实现

    基于Context7最佳实践：middleware中使用Pydantic模型提供类型安全和自动文档生成
    FastAPI自动处理Pydantic模型的JSON序列化，无需手动转换
    """
    return UnifiedAuthContextResponse(
        user_id=getattr(request.state, "user_id", None),
        tenant_id=getattr(request.state, "tenant_id", None),
        permissions=getattr(request.state, "permissions", []),
        access_level=getattr(request.state, "access_level", "guest"),
        is_guest=getattr(request.state, "is_guest", False),
        v0_auth=getattr(request.state, "v0_auth", None),
    )


def is_authenticated_request(request: Request) -> bool:
    """判断请求是否已认证"""
    return getattr(request.state, "user_id", None) is not None


def has_permission_in_unified_request(request: Request, permission: str) -> bool:
    """检查统一认证请求中的权限"""
    permissions = getattr(request.state, "permissions", [])
    return permission in permissions
