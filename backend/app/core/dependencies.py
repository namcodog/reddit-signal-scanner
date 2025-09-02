"""
依赖注入系统 - JWT认证集成

Linus原则：
- 统一接口：所有认证依赖通过统一接口
- 向后兼容：保持现有API接口不变
- 消除特殊情况：统一的用户获取逻辑
- 性能优先：从request.state直接获取，零开销
"""

from typing import Optional, List, Annotated, Callable
from fastapi import Depends, Request
from ..core.auth import (
    CurrentUser,
    AuthenticationError,
    PermissionError,
    TenantAccessError,
)


# ===== 核心依赖注入函数 =====


async def get_current_user(request: Request) -> CurrentUser:
    """
    获取当前认证用户 - 中间件注入版本

    这是新版本的用户获取方式，从中间件注入的request.state获取
    性能优势：零开销，直接内存访问
    """
    auth_user = getattr(request.state, "auth", None)
    if not auth_user:
        raise AuthenticationError("用户未认证或认证已过期")
    return auth_user  # type: ignore


async def get_optional_user(request: Request) -> Optional[CurrentUser]:
    """获取可选的当前用户 - 可能为None"""
    return getattr(request.state, "auth", None)


# ===== 权限检查依赖 =====


def require_permissions(*required_permissions: str) -> Callable:
    """
    权限检查装饰器工厂 - 简化版本

    使用方法:
        @app.get(
            "/admin/users",
            dependencies=[Depends(require_permissions("admin", "user:read"))]
        )
        async def get_users():
            pass
    """

    async def permission_dependency(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        missing_permissions = [
            perm
            for perm in required_permissions
            if perm not in current_user.permissions
        ]

        if missing_permissions:
            raise PermissionError(f"缺少权限: {', '.join(missing_permissions)}")

        return current_user

    return permission_dependency


def require_any_permission(*required_permissions: str) -> Callable:
    """
    任一权限检查装饰器工厂

    用户只需要具备其中任意一个权限即可
    """

    async def permission_dependency(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        has_any_permission = any(
            perm in current_user.permissions for perm in required_permissions
        )

        if not has_any_permission:
            raise PermissionError(
                f"需要以下权限之一: {', '.join(required_permissions)}"
            )

        return current_user

    return permission_dependency


# ===== 租户访问控制 =====


def require_tenant_access(tenant_id_param: str = "tenant_id") -> Callable:
    """
    租户访问控制装饰器工厂

    Args:
        tenant_id_param: 路径参数中租户ID的参数名

    使用方法:
        @app.get(
            "/tenants/{tenant_id}/data",
            dependencies=[Depends(require_tenant_access())]
        )
        async def get_tenant_data(tenant_id: str):
            pass
    """

    async def tenant_dependency(
        request: Request, current_user: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        # 从路径参数获取租户ID
        path_tenant_id = request.path_params.get(tenant_id_param)
        if not path_tenant_id:
            raise TenantAccessError(f"路径中缺少租户ID参数: {tenant_id_param}")

        # 验证租户访问权限
        if current_user.tenant_id != path_tenant_id:
            raise TenantAccessError(
                f"无权访问租户 {path_tenant_id}，当前用户属于租户 {current_user.tenant_id}"
            )

        return current_user

    return tenant_dependency


async def verify_tenant_match(
    tenant_id: str, current_user: CurrentUser = Depends(get_current_user)
) -> CurrentUser:
    """
    直接验证租户匹配 - 用于函数参数中的租户ID

    使用方法:
        async def create_data(
            tenant_id: str,
            data: CreateDataRequest,
            user: CurrentUser = Depends(verify_tenant_match)
        ):
            pass
    """
    if current_user.tenant_id != tenant_id:
        raise TenantAccessError(f"无权访问租户 {tenant_id}")
    return current_user


# ===== 角色和权限预定义依赖 =====


async def require_admin(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """要求管理员权限"""
    if not current_user.has_permission("admin"):
        raise PermissionError("需要管理员权限")
    return current_user


async def require_superuser(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """要求超级用户权限"""
    if not current_user.has_permission("superuser"):
        raise PermissionError("需要超级用户权限")
    return current_user


async def require_read_permission(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """要求读取权限"""
    if not current_user.has_any_permission(["read", "admin", "superuser"]):
        raise PermissionError("需要读取权限")
    return current_user


async def require_write_permission(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """要求写入权限"""
    if not current_user.has_any_permission(["write", "admin", "superuser"]):
        raise PermissionError("需要写入权限")
    return current_user


# ===== 便捷类型别名 - 保持向后兼容 =====

# 必需认证用户
AuthUser = Annotated[CurrentUser, Depends(get_current_user)]

# 可选认证用户
OptionalAuthUser = Annotated[Optional[CurrentUser], Depends(get_optional_user)]

# 管理员用户
AdminUser = Annotated[CurrentUser, Depends(require_admin)]

# 超级用户
SuperUser = Annotated[CurrentUser, Depends(require_superuser)]

# 具有读取权限的用户
ReadUser = Annotated[CurrentUser, Depends(require_read_permission)]

# 具有写入权限的用户
WriteUser = Annotated[CurrentUser, Depends(require_write_permission)]


# ===== 高级依赖组合 =====


def require_permissions_and_tenant(*permissions: str) -> Callable:
    """
    同时要求权限和租户访问控制的组合依赖

    这是一个高效的组合依赖，避免重复的用户认证
    """

    async def combined_dependency(
        request: Request, current_user: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        # 权限检查
        missing_permissions = [
            perm for perm in permissions if perm not in current_user.permissions
        ]
        if missing_permissions:
            raise PermissionError(f"缺少权限: {', '.join(missing_permissions)}")

        # 租户检查（从路径参数）
        tenant_id = request.path_params.get("tenant_id")
        if tenant_id and current_user.tenant_id != tenant_id:
            raise TenantAccessError(f"无权访问租户 {tenant_id}")

        return current_user

    return combined_dependency


# ===== 便捷的权限检查函数 =====


def check_user_permission(user: CurrentUser, permission: str) -> bool:
    """检查用户是否有指定权限"""
    return user.has_permission(permission)


def check_user_any_permission(user: CurrentUser, permissions: List[str]) -> bool:
    """检查用户是否有任意指定权限"""
    return user.has_any_permission(permissions)


def check_user_all_permissions(user: CurrentUser, permissions: List[str]) -> bool:
    """检查用户是否有所有指定权限"""
    return user.has_all_permissions(permissions)


def check_tenant_access(user: CurrentUser, tenant_id: str) -> bool:
    """检查用户是否能访问指定租户"""
    return user.tenant_id == tenant_id


# ===== 依赖注入调试工具 =====


async def get_auth_debug_dependencies(request: Request) -> dict:
    """
    获取认证依赖的调试信息

    使用方法:
        @app.get("/debug/auth")
        async def debug_auth(
            debug_info: dict = Depends(get_auth_debug_dependencies)
        ):
            return debug_info
    """
    current_user = getattr(request.state, "auth", None)

    return {
        "authenticated": current_user is not None,
        "user_info": current_user.dict() if current_user else None,
        "request_state": {
            "user_id": getattr(request.state, "user_id", None),
            "tenant_id": getattr(request.state, "tenant_id", None),
            "permissions": getattr(request.state, "permissions", []),
        },
        "request_details": {
            "path": request.url.path,
            "method": request.method,
            "path_params": dict(request.path_params),
            "query_params": dict(request.query_params),
        },
    }


# ===== 迁移助手函数 =====


def migrate_from_old_auth() -> Callable:
    """
    从旧的认证系统迁移的助手函数

    这个函数帮助现有代码从旧的认证依赖平滑迁移到新系统
    """
    import warnings

    def deprecated_auth_dependency() -> Callable:
        warnings.warn(
            "使用了已废弃的认证依赖，请迁移到 get_current_user",
            DeprecationWarning,
            stacklevel=2,
        )
        return get_current_user

    return deprecated_auth_dependency


# ===== 配置和设置 =====


class DependencyConfig:
    """依赖注入配置"""

    # 是否启用权限缓存
    ENABLE_PERMISSION_CACHE: bool = True

    # 权限缓存TTL（秒）
    PERMISSION_CACHE_TTL: int = 60

    # 是否记录权限检查日志
    LOG_PERMISSION_CHECKS: bool = False

    # 租户访问日志级别
    TENANT_ACCESS_LOG_LEVEL: str = "INFO"


# 全局配置实例
dependency_config = DependencyConfig()
