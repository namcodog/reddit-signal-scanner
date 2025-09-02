"""
简化依赖注入 - Linus式实用主义

原则：
- 最小化抽象层
- 直接使用request.state
- 权限检查用位掩码
- 无复杂的装饰器工厂
"""

from typing import Annotated
from fastapi import Depends, Request

from .auth_context import AuthContext, PermissionMask, AuthError, TenantError


# ===== 核心依赖函数 =====


def get_current_user(request: Request) -> AuthContext:
    """获取当前认证用户"""
    auth = getattr(request.state, "auth", None)
    if not auth:
        raise AuthError("用户未认证")
    return auth


def get_optional_user(request: Request) -> AuthContext | None:
    """获取可选用户"""
    return getattr(request.state, "auth", None)


# ===== 权限检查依赖 =====


def get_admin_user(request: Request) -> AuthContext:
    """获取管理员用户"""
    auth = get_current_user(request)
    if not auth.has_permission(PermissionMask.ADMIN):
        raise AuthError("需要管理员权限")
    return auth


def get_write_user(request: Request) -> AuthContext:
    """获取写权限用户"""
    auth = get_current_user(request)
    if not auth.has_permission(PermissionMask.WRITE):
        raise AuthError("需要写入权限")
    return auth


def get_read_user(request: Request) -> AuthContext:
    """获取读权限用户"""
    auth = get_current_user(request)
    if not auth.has_permission(PermissionMask.READ):
        raise AuthError("需要读取权限")
    return auth


# ===== 租户访问控制 =====


def verify_tenant_access(tenant_id: str, request: Request) -> AuthContext:
    """验证租户访问权限"""
    auth = get_current_user(request)
    if not auth.belongs_to_tenant(tenant_id):
        raise TenantError(f"无权访问租户: {tenant_id}")
    return auth


# ===== 类型别名 - 向后兼容 =====

# 基础用户类型
AuthUser = Annotated[AuthContext, Depends(get_current_user)]
OptionalAuthUser = Annotated[AuthContext | None, Depends(get_optional_user)]

# 权限用户类型
AdminUser = Annotated[AuthContext, Depends(get_admin_user)]
WriteUser = Annotated[AuthContext, Depends(get_write_user)]
ReadUser = Annotated[AuthContext, Depends(get_read_user)]

# 为了完全向后兼容，保留旧名称
CurrentUser = AuthContext  # 类型别名
SuperUser = AdminUser  # 超级用户就是管理员


# ===== 便捷检查函数 =====


def check_permission(auth: AuthContext, perm_mask: int) -> None:
    """权限检查"""
    if not auth.has_permission(perm_mask):
        raise AuthError(f"权限不足，需要权限码: {perm_mask}")


def check_admin(auth: AuthContext) -> None:
    """管理员检查"""
    if not auth.is_admin():
        raise AuthError("需要管理员权限")


def check_tenant(auth: AuthContext, tenant_id: str) -> None:
    """租户访问检查"""
    if not auth.belongs_to_tenant(tenant_id):
        raise TenantError(f"无权访问租户: {tenant_id}")


# ===== 权限位掩码工具 =====


def create_permission_mask(*permissions: str) -> int:
    """创建权限位掩码"""
    mask_map = {
        "read": PermissionMask.READ,
        "write": PermissionMask.WRITE,
        "delete": PermissionMask.DELETE,
        "admin": PermissionMask.ADMIN,
    }

    mask = 0
    for perm in permissions:
        mask |= mask_map.get(perm.lower(), 0)

    return mask


def permission_names(mask: int) -> list[str]:
    """从位掩码获取权限名称列表"""
    names = []
    if mask & PermissionMask.READ:
        names.append("read")
    if mask & PermissionMask.WRITE:
        names.append("write")
    if mask & PermissionMask.DELETE:
        names.append("delete")
    if mask & PermissionMask.ADMIN:
        names.append("admin")
    return names
