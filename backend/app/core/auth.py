"""
认证中间件和依赖注入 - FastAPI集成

Linus原则：
- 简化认证流程：一个函数解决所有认证需求
- 消除特殊情况：租户ID总是存在，无需特殊处理
- 错误处理统一：所有认证错误统一格式
- 性能优先：Token验证结果缓存
"""

import logging
from typing import Optional, List, Annotated, Callable
from datetime import datetime

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
import jwt

from .jwt_handler import get_jwt_handler, TokenPayload
from .config import get_settings
from ..database import get_db_session

# 初始化logger
logger = logging.getLogger(__name__)


class CurrentUser(BaseModel):
    """当前认证用户信息 - 统一数据结构"""

    user_id: str
    tenant_id: str
    email: str
    permissions: List[str]
    token_type: str = "access"

    # 额外上下文信息
    is_authenticated: bool = True
    auth_time: datetime

    def has_permission(self, permission: str) -> bool:
        """检查权限"""
        return permission in self.permissions

    def has_any_permission(self, permissions: List[str]) -> bool:
        """检查是否有任一权限"""
        return any(p in self.permissions for p in permissions)

    def has_all_permissions(self, permissions: List[str]) -> bool:
        """检查是否有所有权限"""
        return all(p in self.permissions for p in permissions)


class AuthenticationError(HTTPException):
    """认证错误 - 统一异常格式"""

    def __init__(self, detail: str = "身份验证失败"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class PermissionError(HTTPException):
    """权限错误"""

    def __init__(self, detail: str = "权限不足"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class TenantAccessError(HTTPException):
    """租户访问错误"""

    def __init__(self, detail: str = "租户访问被拒绝"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


# ===== JWT Bearer Token提取器 =====

security = HTTPBearer(auto_error=False)


async def get_optional_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Optional[str]:
    """获取可选Token - 不强制要求认证"""
    if credentials:
        return credentials.credentials
    return None


async def get_required_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """获取必需Token - 强制要求认证"""
    if not credentials:
        raise AuthenticationError("缺少认证令牌")

    if not credentials.credentials:
        raise AuthenticationError("认证令牌为空")

    return credentials.credentials


# ===== 核心认证依赖 =====


async def authenticate_user(
    token: str = Depends(get_required_token), db: AsyncSession = Depends(get_db_session)
) -> CurrentUser:
    """核心用户认证 - 验证Token并返回用户信息"""
    jwt_handler = get_jwt_handler()

    try:
        # 验证Token
        payload = jwt_handler.verify_access_token(token)

        # TODO: 从数据库验证用户状态（可选）
        # user = await verify_user_in_database(db, payload.user_id, payload.tenant_id)
        # if not user or not user.is_active:
        #     raise AuthenticationError("用户不存在或已禁用")

        # 构造认证用户对象
        current_user = CurrentUser(
            user_id=payload.user_id,
            tenant_id=payload.tenant_id,
            email=payload.email,
            permissions=payload.permissions,
            token_type=payload.token_type,
            auth_time=datetime.now(),
        )

        return current_user

    except jwt.ExpiredSignatureError:
        raise AuthenticationError("认证令牌已过期")
    except jwt.InvalidTokenError as e:
        # 记录详细错误但不暴露给用户
        logger.error(f"JWT验证失败: {e}", exc_info=True)
        raise AuthenticationError("认证令牌无效")
    except Exception as e:
        # 记录详细错误，但不暴露给用户
        logger.error(f"认证错误: {e}", exc_info=True)
        raise AuthenticationError("身份验证失败")


async def authenticate_optional_user(
    token: Optional[str] = Depends(get_optional_token),
    db: AsyncSession = Depends(get_db_session),
) -> Optional[CurrentUser]:
    """可选用户认证 - Token可能不存在"""
    if not token:
        return None

    try:
        # 复用核心认证逻辑
        jwt_handler = get_jwt_handler()
        payload = jwt_handler.verify_access_token(token)

        return CurrentUser(
            user_id=payload.user_id,
            tenant_id=payload.tenant_id,
            email=payload.email,
            permissions=payload.permissions,
            token_type=payload.token_type,
            auth_time=datetime.now(),
        )

    except Exception:
        # 可选认证失败时返回None，不抛出异常
        return None


# ===== 权限检查依赖 =====


def require_permissions(*required_permissions: str) -> Callable:
    """权限检查装饰器工厂"""

    async def permission_dependency(
        current_user: CurrentUser = Depends(authenticate_user),
    ) -> CurrentUser:
        if not current_user.has_all_permissions(list(required_permissions)):
            missing = [
                p for p in required_permissions if p not in current_user.permissions
            ]
            raise PermissionError(f"缺少权限: {', '.join(missing)}")
        return current_user

    return permission_dependency


def require_any_permission(*required_permissions: str) -> Callable:
    """任一权限检查装饰器工厂"""

    async def permission_dependency(
        current_user: CurrentUser = Depends(authenticate_user),
    ) -> CurrentUser:
        if not current_user.has_any_permission(list(required_permissions)):
            raise PermissionError(
                f"需要以下权限之一: {', '.join(required_permissions)}"
            )
        return current_user

    return permission_dependency


# ===== 租户访问控制 =====


async def verify_tenant_access(
    tenant_id: str, current_user: CurrentUser = Depends(authenticate_user)
) -> CurrentUser:
    """验证租户访问权限"""
    if current_user.tenant_id != tenant_id:
        raise TenantAccessError(f"无权访问租户 {tenant_id}")
    return current_user


def require_tenant_access(tenant_id_param: str = "tenant_id") -> Callable:
    """租户访问检查装饰器工厂

    Args:
        tenant_id_param: 路径参数中租户ID的名称
    """

    async def tenant_dependency(
        request: Request, current_user: CurrentUser = Depends(authenticate_user)
    ) -> CurrentUser:
        # 从路径参数获取租户ID
        path_tenant_id = request.path_params.get(tenant_id_param)
        if not path_tenant_id:
            raise TenantAccessError("路径中缺少租户ID")

        # 验证租户访问权限
        if current_user.tenant_id != path_tenant_id:
            raise TenantAccessError(f"无权访问租户 {path_tenant_id}")

        return current_user

    return tenant_dependency


# ===== 管理员权限 =====


async def require_admin(
    current_user: CurrentUser = Depends(authenticate_user),
) -> CurrentUser:
    """要求管理员权限"""
    if not current_user.has_permission("admin"):
        raise PermissionError("需要管理员权限")
    return current_user


async def require_superuser(
    current_user: CurrentUser = Depends(authenticate_user),
) -> CurrentUser:
    """要求超级用户权限"""
    if not current_user.has_permission("superuser"):
        raise PermissionError("需要超级用户权限")
    return current_user


# ===== 便捷类型别名 =====

# 必需认证用户
AuthUser = Annotated[CurrentUser, Depends(authenticate_user)]

# 可选认证用户
OptionalAuthUser = Annotated[Optional[CurrentUser], Depends(authenticate_optional_user)]

# 管理员用户
AdminUser = Annotated[CurrentUser, Depends(require_admin)]

# 超级用户
SuperUser = Annotated[CurrentUser, Depends(require_superuser)]


# ===== 中间件支持函数 =====


async def extract_tenant_from_header(request: Request) -> Optional[str]:
    """从请求头提取租户ID"""
    return request.headers.get("X-Tenant-ID")


async def extract_tenant_from_token(request: Request) -> Optional[str]:
    """从Token提取租户ID（不验证Token有效性）"""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    try:
        token = auth_header.split(" ")[1]
        jwt_handler = get_jwt_handler()

        # 获取Token信息（不验证签名）
        token_info = jwt_handler.get_token_info(token)
        return token_info.get("tenant_id")

    except Exception:
        return None


# ===== 工具函数 =====


def create_auth_response_headers(
    access_token: str, refresh_token: Optional[str] = None
) -> dict:
    """创建认证响应头"""
    headers = {
        "X-Token-Type": "Bearer",
        "X-Token-Expires": str(get_settings().jwt_access_token_expire_seconds),
    }

    if refresh_token:
        headers["X-Refresh-Token-Expires"] = str(
            get_settings().jwt_refresh_token_expire_seconds
        )

    return headers


def get_token_from_request(request: Request) -> Optional[str]:
    """从请求中提取Token"""
    # Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ")[1]

    # Query parameter (不推荐，但支持)
    # 为了安全考虑，不支持通过查询参数传递Token
    # 查询参数可能被记录在日志中，存在安全风险
    return None


# ===== 认证信息缓存 =====


class AuthCache:
    """认证信息缓存 - 提升性能"""

    def __init__(self) -> None:
        self._cache: dict[str, CurrentUser] = {}  # 简单内存缓存，生产环境建议用Redis
        self._cache_ttl = 300  # 5分钟缓存

    async def get_user_info(self, token_hash: str) -> Optional[CurrentUser]:
        """获取缓存的用户信息"""
        # TODO: 实现Redis缓存
        return self._cache.get(token_hash)

    async def set_user_info(self, token_hash: str, user_info: CurrentUser) -> None:
        """缓存用户信息"""
        # TODO: 实现Redis缓存
        self._cache[token_hash] = user_info

    async def remove_user_info(self, token_hash: str) -> None:
        """移除缓存的用户信息"""
        self._cache.pop(token_hash, None)


# 全局缓存实例
auth_cache = AuthCache()


# ===== 调试和诊断工具 =====


async def get_auth_debug_info(request: Request) -> dict:
    """获取认证调试信息"""
    return {
        "headers": dict(request.headers),
        "token": get_token_from_request(request),
        "tenant_header": extract_tenant_from_header(request),
        "tenant_token": await extract_tenant_from_token(request),
        "path": request.url.path,
        "method": request.method,
    }
