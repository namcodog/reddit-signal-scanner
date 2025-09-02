"""
JWT认证上下文 - Linus式简洁设计

核心理念：
- 数据结构决定一切
- 权限用位掩码，O(1)复杂度
- 最小化内存使用
- 去除所有废话字段
"""

from dataclasses import dataclass
import time


# 权限位掩码常量
class PermissionMask:
    """权限位掩码定义"""

    READ = 1 << 0  # 0001
    WRITE = 1 << 1  # 0010
    DELETE = 1 << 2  # 0100
    ADMIN = 1 << 3  # 1000

    # 组合权限
    USER = READ | WRITE  # 0011
    MODERATOR = USER | DELETE  # 0111
    SUPERUSER = MODERATOR | ADMIN  # 1111


@dataclass(frozen=True, slots=True)  # 性能优化：不可变+__slots__
class AuthContext:
    """
    认证上下文 - Linus式极简设计

    只包含绝对必要的字段：
    - user_id: 用户标识
    - tenant_id: 租户标识
    - permissions_mask: 权限位掩码
    - token_exp: Token过期时间
    """

    user_id: str
    tenant_id: str
    permissions_mask: int
    token_exp: int

    @classmethod
    def from_jwt_payload(cls, payload: dict) -> "AuthContext":
        """从JWT载荷创建认证上下文"""
        return cls(
            user_id=payload["sub"],
            tenant_id=payload["tenant_id"],
            permissions_mask=payload.get("perms", 0),
            token_exp=payload["exp"],
        )

    def has_permission(self, perm_mask: int) -> bool:
        """O(1)权限检查"""
        return (self.permissions_mask & perm_mask) == perm_mask

    def has_any_permission(self, perm_mask: int) -> bool:
        """检查是否有任意权限"""
        return bool(self.permissions_mask & perm_mask)

    def is_expired(self) -> bool:
        """检查Token是否过期"""
        return int(time.time()) >= self.token_exp

    def belongs_to_tenant(self, tenant_id: str) -> bool:
        """检查租户访问权限"""
        return self.tenant_id == tenant_id

    def is_admin(self) -> bool:
        """检查是否管理员"""
        return self.has_permission(PermissionMask.ADMIN)


# 认证异常
class AuthError(Exception):
    """统一认证异常"""

    def __init__(self, message: str, status_code: int = 401):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class TenantError(AuthError):
    """租户访问异常"""

    def __init__(self, message: str):
        super().__init__(message, 403)


# 权限检查便捷函数
def check_permission(auth: AuthContext, required: int) -> None:
    """权限检查，失败抛异常"""
    if not auth.has_permission(required):
        raise AuthError(f"权限不足，需要权限码: {required}")


def check_tenant_access(auth: AuthContext, tenant_id: str) -> None:
    """租户访问检查，失败抛异常"""
    if not auth.belongs_to_tenant(tenant_id):
        raise TenantError(f"无权访问租户: {tenant_id}")


def check_admin(auth: AuthContext) -> None:
    """管理员权限检查"""
    if not auth.is_admin():
        raise AuthError("需要管理员权限")


# 为向后兼容保留的CurrentUser类型别名
CurrentUser = AuthContext
