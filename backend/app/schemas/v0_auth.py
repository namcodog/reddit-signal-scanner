"""
V0认证配置Schema - 数据结构优先设计

Linus原则：
- 数据结构驱动设计，消除所有条件分支
- 100%类型覆盖，零Any使用
- 单一数据模型解决所有认证场景
"""

from datetime import datetime
from typing import Dict, List, Literal, Optional, Set, Union

from pydantic import BaseModel, Field
from ..core.config import get_settings
from typing import Set, List


def _default_guest_allowed_paths() -> Set[str]:
    prefix = get_settings().api_prefix
    return {f"{prefix}/analysis/demo", f"{prefix}/reports/public"}


def _default_optional_auth_paths() -> Set[str]:
    prefix = get_settings().api_prefix
    return {f"{prefix}/analysis/tasks"}


class V0AuthConfig(BaseModel):
    """V0认证配置 - 统一所有认证场景的数据结构"""

    enable_guest_mode: bool = True
    guest_allowed_paths: Set[str] = Field(default_factory=_default_guest_allowed_paths)
    cors_origins: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:3001",
        ]
    )
    optional_auth_paths: Set[str] = Field(default_factory=_default_optional_auth_paths)
    dev_mode_enabled: bool = False
    max_auth_time_ms: float = 10.0


class AuthContextV0(BaseModel):
    """V0认证上下文 - 消除用户类型分支的统一数据结构"""

    user_id: Optional[str] = None
    email: Optional[str] = None
    tenant_id: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)
    is_guest: bool = False
    access_level: Literal["full", "limited", "guest"] = "guest"
    auth_time: Optional[datetime] = None
    v0_features: Dict[str, bool] = Field(default_factory=dict)

    @property
    def is_authenticated(self) -> bool:
        return self.user_id is not None

    @property
    def has_full_access(self) -> bool:
        return self.access_level == "full"


class AuthResponseSchema(BaseModel):
    """统一认证响应格式 - 前后端一致的数据结构"""

    success: bool
    user: Optional[Dict[str, Union[str, List[str]]]] = None
    access_level: Literal["full", "limited", "guest"]
    expires_at: Optional[datetime] = None
    error: Optional[str] = None
    frontend_action: Optional[Literal["redirect_login", "show_dialog", "retry"]] = None


class V0AuthError(BaseModel):
    """V0认证错误 - 类型安全的错误处理"""

    type: Literal[
        "token_missing", "token_invalid", "token_expired", "permission_denied"
    ]
    message: str
    code: int
    frontend_action: Optional[Literal["redirect_login", "show_dialog", "retry"]] = None


class PathMatchRule(BaseModel):
    """路径匹配规则 - 消除路径判断的if-else分支"""

    exact_paths: Set[str] = Field(default_factory=set)
    prefix_patterns: List[str] = Field(default_factory=list)
    guest_allowed: Set[str] = Field(default_factory=set)
    auth_required: Set[str] = Field(default_factory=set)
    optional_auth: Set[str] = Field(default_factory=set)

    def matches(self, path: str) -> Literal["guest", "optional", "required", "skip"]:
        if path in self.exact_paths or path in self.guest_allowed:
            return "guest"
        if path in self.optional_auth:
            return "optional"
        if path in self.auth_required:
            return "required"
        for prefix in self.prefix_patterns:
            if path.startswith(prefix):
                return "skip"
        return "required"


class MiddlewareConfigSchema(BaseModel):
    """中间件配置 - 数据驱动的中间件行为"""

    skip_auth_paths: Set[str] = Field(
        default_factory=lambda: {
            "/",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/api/auth/login",
            "/api/auth/register",
            "/api/auth/refresh",
        }
    )
    v0_config: V0AuthConfig = Field(default_factory=V0AuthConfig)
    cache_ttl_seconds: int = 300
    enable_performance_logging: bool = True
    max_auth_time_ms: float = 10.0
