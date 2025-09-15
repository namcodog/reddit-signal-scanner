"""
认证相关响应模型 - 替代认证场景中的Dict[str, Any]
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..common.base import BaseResponse


class UnifiedAuthContextResponse(BaseModel):
    """统一认证上下文响应

    替代: get_unified_auth_context() -> Dict[str, Any]
    """

    user_id: Optional[str] = Field(default=None, description="用户ID")
    tenant_id: Optional[str] = Field(default=None, description="租户ID")
    permissions: List[str] = Field(default_factory=list, description="用户权限列表")
    access_level: str = Field(default="guest", description="访问级别")
    is_guest: bool = Field(default=False, description="是否为访客用户")
    v0_auth: Optional[Any] = Field(default=None, description="V0认证信息（过渡期保留）")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_123",
                "tenant_id": "tenant_456",
                "permissions": ["read:posts", "write:comments"],
                "access_level": "authenticated",
                "is_guest": False,
                "v0_auth": None,
            }
        }


class AuthenticationResponse(BaseResponse):
    """认证响应"""

    access_token: Optional[str] = Field(default=None, description="访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: Optional[int] = Field(default=None, description="令牌过期时间（秒）")
    user_info: Optional[UnifiedAuthContextResponse] = Field(
        default=None, description="用户信息"
    )


class AuthorizationResponse(BaseResponse):
    """授权检查响应"""

    authorized: bool = Field(..., description="是否已授权")
    missing_permissions: List[str] = Field(default_factory=list, description="缺失的权限")
    reason: Optional[str] = Field(default=None, description="授权失败原因")


# 健康检查响应（统一到schemas层）
class HealthCheckItem(BaseModel):
    status: str
    message: str


class AuthHealthResponse(BaseModel):
    status: str
    timestamp: str
    checks: Dict[str, HealthCheckItem]
    error: Optional[str] = None
