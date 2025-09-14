"""
JWT认证中间件 - 全局请求认证处理

Linus原则实现：
- 简化认证流程：单一中间件处理所有认证逻辑
- 消除特殊情况：统一的认证上下文注入
- 无状态设计：不依赖外部状态，零副作用
- 性能优先：最小化处理时间，<5ms目标
"""

import logging
import os
import time
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..core.auth import (
    AuthenticationError,
    CurrentUser,
    TenantAccessError,
    auth_cache,
    get_token_from_request,
)
from ..core.config import get_settings
from ..core.jwt_handler import TokenPayload, get_jwt_handler
from ..schemas.contracts.auth_contract import UserContext as ContractUserContext

logger = logging.getLogger(__name__)


class JWTAuthenticator:
    """
    JWT认证器 - Linus式简洁设计

    核心理念：
    1. 单个authenticate()函数处理所有情况
    2. 统一AuthContext替代多种用户类型
    3. 消除所有if-else分支的特殊情况处理
    """

    def __init__(self) -> None:
        self.jwt_handler = get_jwt_handler()
        self.settings = get_settings()

    async def authenticate(
        self,
        request: Request,
        required_permissions: Optional[Set[str]] = None,
        tenant_id: Optional[str] = None,
    ) -> CurrentUser:
        """
        统一认证函数 - Linus式线性逻辑，零特殊情况

        重构原则：
        1. 单一职责：每个步骤独立函数
        2. 线性逻辑：无嵌套，直线处理
        3. 统一出口：所有路径汇聚到同一返回点
        """
        start_time = time.time()

        try:
            # 第1步：提取和验证Token（单一职责）
            token = self._extract_and_validate_token(request)

            # 第2步：缓存检查或Token验证（统一路径）
            auth_context = await self._get_user_from_cache_or_verify(token)

            # 第3步：权限验证（无条件分支）
            self._validate_permissions_and_tenant(
                auth_context, required_permissions, tenant_id
            )

            self._log_auth_performance(start_time, "success")
            return auth_context

        except Exception as e:
            self._handle_auth_error(e, start_time, getattr(locals(), "token", None))
            raise  # 确保函数有return路径，虽然_handle_auth_error会抛异常

    def _extract_and_validate_token(self, request: Request) -> str:
        """提取并验证Token - 单一出口，无嵌套"""
        token = get_token_from_request(request)
        if not token:
            raise AuthenticationError("缺少认证令牌")
        return token

    async def _get_user_from_cache_or_verify(self, token: str) -> CurrentUser:
        """缓存或验证 - 消除if-else分支"""
        token_hash = self._get_token_hash(token)

        # 尝试缓存命中
        cached_user = await auth_cache.get_user_info(token_hash)
        if cached_user and not self._is_token_expired(cached_user):
            # Context7安全检查：即使缓存命中，也要检查黑名单
            await self._check_token_blacklist(cached_user.user_id, token)
            return cached_user

        # 验证Token并创建用户上下文
        payload = self.jwt_handler.verify_access_token(token)

        # Context7核心安全检查：验证token是否在黑名单中
        await self._check_token_revoked(payload.jti)

        # 检查用户是否被全局撤销
        await self._check_user_globally_revoked(payload.user_id)

        auth_context = self._create_user_from_payload(payload)

        # 缓存结果
        await auth_cache.set_user_info(token_hash, auth_context)
        return auth_context

    def _get_token_hash(self, token: str) -> str:
        """生成Token哈希 - 安全加固版本"""
        import hashlib

        # 使用环境变量配置的安全Salt
        salt_hex = os.environ.get("JWT_CACHE_SALT")
        if not salt_hex:
            # 生产环境必须配置Salt
            if getattr(self.settings, "is_production", False):
                raise RuntimeError("生产环境必须设置JWT_CACHE_SALT环境变量")
            # 开发环境使用默认值（仅用于测试）
            salt_hex = (
                "a1b2c3d4e5f6789012345678901234567890abcdef" "1234567890abcdef123456"
            )

        try:
            salt = bytes.fromhex(salt_hex)
        except ValueError:
            raise RuntimeError("JWT_CACHE_SALT必须是有效的16进制字符串")

        # 使用600000次迭代，符合2025年OWASP安全标准
        return hashlib.pbkdf2_hmac("sha256", token.encode(), salt, 600000)[:32].hex()

    def _create_user_from_payload(self, payload: TokenPayload) -> CurrentUser:
        """从JWT Payload创建用户上下文"""
        return CurrentUser(
            user_id=payload.user_id,
            tenant_id=payload.tenant_id,
            email=payload.email,
            permissions=payload.permissions,
            token_type=payload.token_type,
            auth_time=datetime.now(),
        )

    def _is_token_expired(self, user: CurrentUser) -> bool:
        """检查Token是否过期"""
        # 简化逻辑：基于认证时间判断
        auth_age = (datetime.now() - user.auth_time).total_seconds()
        return auth_age > self.settings.jwt_access_token_expire_seconds

    def _validate_permissions_and_tenant(
        self,
        auth_context: CurrentUser,
        required_permissions: Optional[Set[str]] = None,
        tenant_id: Optional[str] = None,
    ) -> None:
        """权限和租户验证 - 线性逻辑，无嵌套"""
        self._check_permissions(auth_context.permissions, required_permissions)
        self._check_tenant_access(auth_context.tenant_id, tenant_id)

    def _check_permissions(
        self,
        user_permissions: List[str],
        required_permissions: Optional[Set[str]],
    ) -> None:
        """权限检查 - 单一职责"""
        if not required_permissions:
            return

        missing_perms = required_permissions - set(user_permissions)
        if missing_perms:
            raise AuthenticationError(f"缺少权限: {', '.join(missing_perms)}")

    def _check_tenant_access(
        self, user_tenant_id: str, required_tenant_id: Optional[str]
    ) -> None:
        """租户访问检查 - 单一职责"""
        if required_tenant_id and user_tenant_id != required_tenant_id:
            raise TenantAccessError(f"无权访问租户 {required_tenant_id}")

    def _handle_auth_error(
        self, error: Exception, start_time: float, token: Optional[str]
    ) -> None:
        """统一错误处理 - 表驱动替代嵌套if-else"""
        self._log_auth_performance(start_time, "error", str(error))

        # 已知异常直接抛出
        if isinstance(error, (AuthenticationError, TenantAccessError)):
            raise error

        # 未知异常的安全处理
        self._log_unknown_error(error, token)
        raise AuthenticationError("身份验证失败")

    def _log_unknown_error(self, error: Exception, token: Optional[str]) -> None:
        """记录未知错误 - 简化逻辑"""
        if getattr(self.settings, "is_production", False):
            logger.error(
                "认证失败",
                extra={"token_hash": self._safe_get_token_hash(token)},
            )
        else:
            logger.error(f"认证异常: {error}", exc_info=True)

    def _safe_get_token_hash(self, token: Optional[str]) -> str:
        """安全获取Token哈希"""
        return self._get_token_hash(token) if token else "none"

    def _log_auth_performance(
        self, start_time: float, result: str, error: Optional[str] = None
    ) -> None:
        """记录认证性能指标"""
        duration_ms = (time.time() - start_time) * 1000

        if duration_ms > 5.0:
            logger.warning(f"认证耗时过长: {duration_ms:.2f}ms, result: {result}")

        logger.debug(f"认证性能: {duration_ms:.2f}ms, result: {result}, error: {error}")

    # ===== Context7安全检查方法 =====

    async def _check_token_revoked(self, jti: str) -> None:
        """检查token是否在黑名单中 - Context7核心安全机制"""
        try:
            from ..services.token_blacklist_service import get_token_blacklist_service

            blacklist_service = get_token_blacklist_service()

            if await blacklist_service.is_token_revoked(jti):
                raise AuthenticationError("Token已被撤销")
        except AuthenticationError:
            raise
        except Exception as e:
            # Context7模式：黑名单服务错误时记录但允许通过
            logger.warning(f"黑名单检查失败: {e}")

    async def _check_user_globally_revoked(self, user_id: str) -> None:
        """检查用户是否被全局撤销 - Context7全局撤销机制"""
        try:
            from ..services.token_blacklist_service import get_token_blacklist_service

            blacklist_service = get_token_blacklist_service()

            if await blacklist_service.is_user_globally_revoked(user_id):
                raise AuthenticationError("用户所有token已被撤销")
        except AuthenticationError:
            raise
        except Exception as e:
            # Context7模式：全局撤销检查失败时记录但允许通过
            logger.warning(f"全局撤销检查失败: {e}")

    async def _check_token_blacklist(self, user_id: str, token: str) -> None:
        """缓存命中时的黑名单检查 - 确保撤销的token立即失效"""
        try:
            # 从token中提取JTI进行检查
            payload = self.jwt_handler.verify_access_token(token)
            await self._check_token_revoked(payload.jti)
            await self._check_user_globally_revoked(user_id)
        except Exception as e:
            # 黑名单检查失败时使缓存失效，强制重新验证
            logger.warning(f"缓存token黑名单检查失败: {e}")
            raise AuthenticationError("Token状态验证失败")


class JWTMiddleware(BaseHTTPMiddleware):
    """
    JWT认证中间件 - Linus式清晰实现

    设计原则：
    1. 无状态：不依赖外部状态
    2. 无嵌套：直线处理逻辑
    3. 统一注入：所有请求统一处理
    """

    # 无需认证的路径
    SKIP_AUTH_PATHS = {
        "/",
        "/api",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/dev/test-error",
        "/dev/config",
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/refresh",
        # 版本化API的公开端点
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/refresh",
        "/api/v1/auth/health",
        "/api/v1/auth/reset-password",
    }

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.authenticator = JWTAuthenticator()
        logger.info("JWT中间件已初始化")

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """
        中间件核心处理 - 无状态、无嵌套、直线逻辑
        """
        # 跳过无需认证的路径
        if self._should_skip_auth(request.url.path):
            return await call_next(request)

        try:
            # 执行认证并注入上下文
            auth_context = await self.authenticator.authenticate(request)
            request.state.auth = auth_context

            # 注入便捷访问属性
            request.state.user_id = auth_context.user_id
            request.state.tenant_id = auth_context.tenant_id
            request.state.permissions = auth_context.permissions

            logger.debug(f"认证成功: {auth_context.user_id}@{auth_context.tenant_id}")

        except AuthenticationError as e:
            return self._handle_auth_error(e, request)

        except TenantAccessError as e:
            return self._handle_tenant_error(e, request)

        except Exception as e:
            return self._handle_internal_error(e, request)

        # 继续处理请求
        return await call_next(request)

    def _should_skip_auth(self, path: str) -> bool:
        """
        判断是否跳过认证 - 简化逻辑

        跳过认证的情况：
        1. 明确的免认证路径
        2. OPTIONS请求（CORS预检）
        3. 健康检查等系统路径
        """
        # 精确匹配
        if path in self.SKIP_AUTH_PATHS:
            return True

        # 前缀匹配
        skip_prefixes = [
            "/docs",
            "/redoc",
            "/static",
            "/health",
            "/api/v1/status",
            "/api/v1/stream",
            # 版本化认证路由整体免认证（注册/登录/健康/重置密码等）
            "/api/v1/auth",
        ]
        return any(path.startswith(prefix) for prefix in skip_prefixes)

    def _handle_auth_error(
        self, error: AuthenticationError, request: Request
    ) -> JSONResponse:
        """处理认证错误 - Linus式单一职责"""
        logger.info(f"认证失败: {error.detail}, path: {request.url.path}")
        return JSONResponse(
            status_code=401,
            content={
                "detail": error.detail,
                "type": "authentication_error",
                "path": request.url.path,
                "timestamp": datetime.now().isoformat(),
                "frontend_action": "redirect_login",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    def _handle_tenant_error(
        self, error: TenantAccessError, request: Request
    ) -> JSONResponse:
        """处理租户访问错误 - Linus式单一职责"""
        logger.warning(f"租户访问被拒绝: {error.detail}, path: {request.url.path}")
        return JSONResponse(
            status_code=403,
            content={
                "detail": error.detail,
                "type": "tenant_access_error",
                "path": request.url.path,
                "timestamp": datetime.now().isoformat(),
            },
        )

    def _handle_internal_error(
        self, error: Exception, request: Request
    ) -> JSONResponse:
        """处理内部错误 - Linus式单一职责"""
        logger.error(f"中间件异常: {error}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "内部服务器错误",
                "type": "internal_error",
                "path": request.url.path,
                "timestamp": datetime.now().isoformat(),
            },
        )


# ===== 中间件配置工具 =====


def create_jwt_middleware_config() -> Dict[str, Any]:
    """创建JWT中间件配置"""
    return {
        "cache_ttl": 300,  # 5分钟缓存
        "max_token_age": 3600,  # 1小时最大Token生命周期
        "log_performance": True,  # 启用性能日志
        "skip_auth_paths": list(JWTMiddleware.SKIP_AUTH_PATHS),
    }


def install_jwt_middleware(
    app: FastAPI, config: Optional[Dict[str, Any]] = None
) -> None:
    """
    安装JWT中间件到FastAPI应用

    使用方法:
        from app.middleware.jwt_middleware import install_jwt_middleware
        install_jwt_middleware(app)
    """
    if config:
        # 动态配置跳过认证路径
        if "skip_auth_paths" in config:
            JWTMiddleware.SKIP_AUTH_PATHS.update(config["skip_auth_paths"])

    app.add_middleware(JWTMiddleware)
    logger.info("JWT中间件已安装到FastAPI应用")


# ===== 便捷的认证检查函数 =====


def get_current_user_from_request(request: Request) -> Optional[CurrentUser]:
    """从请求中获取当前认证用户"""
    return getattr(request.state, "auth", None)


def get_user_id_from_request(request: Request) -> Optional[str]:
    """从请求中获取用户ID"""
    return getattr(request.state, "user_id", None)


def get_tenant_id_from_request(request: Request) -> Optional[str]:
    """从请求中获取租户ID"""
    return getattr(request.state, "tenant_id", None)


def has_permission_in_request(request: Request, permission: str) -> bool:
    """检查请求是否有指定权限"""
    permissions = getattr(request.state, "permissions", [])
    return permission in permissions


# ===== 调试和诊断 =====


async def get_middleware_debug_info(request: Request) -> Dict[str, Any]:
    """获取中间件调试信息"""
    return {
        "auth_user": get_current_user_from_request(request),
        "user_context_contract": get_user_context_contract(request),
        "user_id": get_user_id_from_request(request),
        "tenant_id": get_tenant_id_from_request(request),
        "permissions": getattr(request.state, "permissions", []),
        "skip_auth": False,  # 简化调试函数
        "path": request.url.path,
        "method": request.method,
        "headers": dict(request.headers),
    }


def get_user_context_contract(
    request: Request,
) -> Optional[ContractUserContext]:
    """从请求构造契约化的用户上下文（用于跨模块/多租户边界）。"""
    user = get_current_user_from_request(request)
    if not user:
        return None
    session_id = getattr(request.state, "request_id", None) or "session"
    return user.to_contract(session_id=session_id)
