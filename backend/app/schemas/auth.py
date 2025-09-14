"""
Reddit Signal Scanner - 认证数据模式

Linus原则："数据结构决定一切"
- 统一的请求/响应模型，消除特殊情况
- 强类型验证，防止输入攻击
- 与现有JWT系统完美集成
- 明确的错误信息和验证规则
"""

import re
from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator

from ..core.types import JsonValue

# ===== 用户注册请求模式 =====


class UserRegisterRequest(BaseModel):
    """用户注册请求模型

    统一处理个人用户和企业用户注册，通过tenant_id自动生成
    实现多租户架构下的一致性体验
    """

    email: str = Field(
        description="用户邮箱地址",
        min_length=5,
        max_length=320,  # RFC 5321 标准
        examples=["user@example.com"],
    )

    password: str = Field(
        description="用户密码，需要满足强度要求",
        min_length=8,
        max_length=128,
        examples=["MySecurePassword123!"],
    )

    confirm_password: str = Field(
        description="确认密码，必须与密码一致",
        min_length=8,
        max_length=128,
        examples=["MySecurePassword123!"],
    )

    @validator("email")
    def validate_email_format(cls, v: str) -> str:
        """验证邮箱格式

        使用与数据库约束相同的正则表达式，确保一致性
        """
        v = v.strip().lower()
        email_pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

        if not re.match(email_pattern, v):
            raise ValueError("邮箱格式无效")

        return v

    @validator("password")
    def validate_password_strength(cls, v: str) -> str:
        """验证密码强度

        密码要求：
        - 至少8个字符
        - 包含大写字母
        - 包含小写字母
        - 包含数字
        - 包含特殊字符
        """
        if len(v) < 8:
            raise ValueError("密码长度至少8个字符")

        if not re.search(r"[A-Z]", v):
            raise ValueError("密码必须包含至少一个大写字母")

        if not re.search(r"[a-z]", v):
            raise ValueError("密码必须包含至少一个小写字母")

        if not re.search(r"[0-9]", v):
            raise ValueError("密码必须包含至少一个数字")

        if not re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'",.<>?/|\\`~]', v):
            raise ValueError("密码必须包含至少一个特殊字符")

        # 检查常见弱密码模式
        weak_patterns = [
            r"123456",
            r"password",
            r"qwerty",
            r"abc123",
        ]

        v_lower = v.lower()
        for pattern in weak_patterns:
            if pattern in v_lower:
                raise ValueError("密码不能包含常见弱密码模式")

        return v

    @validator("confirm_password")
    def validate_passwords_match(cls, v: str, values: dict[str, JsonValue]) -> str:
        """验证确认密码匹配"""
        if "password" in values and v != values["password"]:
            raise ValueError("确认密码与密码不匹配")
        return v

    class Config:
        """Pydantic配置"""

        json_schema_extra = {
            "example": {
                "email": "john.doe@example.com",
                "password": "MySecurePassword123!",
                "confirm_password": "MySecurePassword123!",
            }
        }


# ===== 用户登录模式 =====


class UserLoginRequest(BaseModel):
    """用户登录请求模型

    统一的登录接口，支持邮箱密码认证
    """

    email: str = Field(
        description="用户邮箱地址",
        min_length=5,
        max_length=320,
        examples=["user@example.com"],
    )

    password: str = Field(
        description="用户密码",
        min_length=1,
        max_length=128,
        examples=["MySecurePassword123!"],
    )

    @validator("email")
    def normalize_email(cls, v: str) -> str:
        """标准化邮箱格式"""
        return v.strip().lower()

    class Config:
        """Pydantic配置"""

        json_schema_extra = {
            "example": {
                "email": "john.doe@example.com",
                "password": "MySecurePassword123!",
            }
        }


# ===== 用户注册响应模式 =====


class UserRegisterResponse(BaseModel):
    """用户注册成功响应模型

    返回用户基本信息和JWT tokens，实现即注册即登录的用户体验
    """

    user_id: UUID = Field(..., description="用户唯一标识符")
    tenant_id: UUID = Field(..., description="租户标识符")
    email: str = Field(..., description="用户邮箱地址")
    email_verified: bool = Field(..., description="邮箱验证状态")
    is_active: bool = Field(..., description="用户激活状态")
    created_at: str = Field(..., description="账户创建时间")

    # JWT tokens - 即注册即登录
    access_token: str = Field(..., description="访问token")
    refresh_token: str = Field(..., description="刷新token")
    token_type: str = Field(default="bearer", description="token类型")
    expires_in: int = Field(..., description="访问token过期时间（秒）")

    class Config:
        """Pydantic配置"""

        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "tenant_id": "987fcdeb-51d2-43a8-b456-426614174001",
                "email": "john.doe@example.com",
                "email_verified": False,
                "is_active": True,
                "created_at": "2025-01-14T10:30:00Z",
                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                "token_type": "bearer",
                "expires_in": 3600,
            }
        }


# ===== 登录会话追踪模式 =====


class LoginSession(BaseModel):
    """统一的登录会话模型

    Linus原则：消除特殊情况，统一数据结构
    合并了SecurityContext、AuditLog和AttemptTracker的职责
    """

    session_id: UUID = Field(default_factory=uuid4, description="会话唯一标识")
    user_id: Optional[UUID] = Field(None, description="用户ID（成功时）")
    email: str = Field(..., description="登录邮箱")
    ip_address: str = Field(..., description="客户端IP地址")
    user_agent: Optional[str] = Field(None, description="用户代理")
    login_time: datetime = Field(default_factory=datetime.utcnow, description="登录时间")
    success: bool = Field(..., description="登录是否成功")
    failure_reason: Optional[str] = Field(None, description="失败原因")
    attempt_count: int = Field(default=1, description="尝试次数")
    locked_until: Optional[datetime] = Field(None, description="账户锁定到期时间")

    class Config:
        """Pydantic配置"""

        json_schema_extra = {
            "example": {
                "session_id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "john.doe@example.com",
                "ip_address": "192.168.1.1",
                "success": True,
                "attempt_count": 1,
            }
        }


# ===== JWT Token响应模式 =====


class AuthTokenResponse(BaseModel):
    """JWT Token统一响应格式

    用于登录、刷新token等场景的统一响应模型
    """

    access_token: str = Field(..., description="访问token")
    refresh_token: Optional[str] = Field(default=None, description="刷新token（可选）")
    token_type: str = Field(default="bearer", description="token类型")
    expires_in: int = Field(..., description="访问token过期时间（秒）")

    # 用户上下文信息
    user_id: UUID = Field(..., description="用户ID")
    tenant_id: UUID = Field(..., description="租户ID")
    email: str = Field(..., description="用户邮箱")

    class Config:
        """Pydantic配置"""

        json_schema_extra = {
            "example": {
                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                "token_type": "bearer",
                "expires_in": 3600,
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "tenant_id": "987fcdeb-51d2-43a8-b456-426614174001",
                "email": "john.doe@example.com",
            }
        }


# ===== 认证错误响应模式 =====


class AuthErrorResponse(BaseModel):
    """认证相关错误响应模型

    统一的错误响应格式，提供明确的错误信息和建议
    """

    error: str = Field(..., description="错误类型标识")
    error_description: str = Field(..., description="详细错误描述")
    error_code: int = Field(..., description="内部错误代码")

    # 用户友好的建议信息
    suggestion: Optional[str] = Field(default=None, description="解决建议")
    retry_after: Optional[int] = Field(default=None, description="重试间隔（秒）")

    class Config:
        """Pydantic配置"""

        json_schema_extra = {
            "example": {
                "error": "invalid_credentials",
                "error_description": "邮箱或密码错误",
                "error_code": 4001,
                "suggestion": "请检查邮箱和密码是否正确",
                "retry_after": None,
            }
        }


# ===== Token刷新和注销模式 =====
# 注意：Token刷新遵循Context7最佳实践，使用Security dependency而非request body


class BasicTokenResponse(BaseModel):
    """基础Token响应模型

    符合Context7简洁模式：返回token对的最小必要信息
    用于登录和刷新等场景的统一响应格式
    """

    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(..., description="访问令牌过期时间（秒）")

    # 可选的用户上下文信息（我们的扩展）
    user_id: Optional[UUID] = Field(default=None, description="用户ID")
    email: Optional[str] = Field(default=None, description="用户邮箱")

    class Config:
        """Pydantic配置"""

        json_schema_extra = {
            "example": {
                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                "token_type": "bearer",
                "expires_in": 3600,
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "user@example.com",
            }
        }


class LogoutRequest(BaseModel):
    """注销请求模型

    支持单点注销和全设备注销
    """

    refresh_token: Optional[str] = Field(
        default=None,
        description="可选的刷新令牌，用于撤销特定会话",
        min_length=1,  # 放宽最小长度限制
        max_length=2000,
    )

    logout_all_devices: bool = Field(default=False, description="是否注销所有设备")

    class Config:
        """Pydantic配置"""

        json_schema_extra = {
            "example": {
                "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                "logout_all_devices": False,
            }
        }


class LogoutResponse(BaseModel):
    """注销响应模型"""

    message: str = Field(..., description="注销结果消息")
    logged_out_sessions: int = Field(..., description="注销的会话数量")

    class Config:
        """Pydantic配置"""

        json_schema_extra = {"example": {"message": "注销成功", "logged_out_sessions": 1}}


class TokenError(AuthErrorResponse):
    """Token相关错误响应模型"""

    error_type: str = Field(
        ...,
        description="具体错误类型",
        examples=["invalid_token", "expired_token", "blacklisted_token"],
    )
    jti: Optional[str] = Field(default=None, description="相关的JWT ID")


class RefreshTokenError(TokenError):
    """刷新Token特定错误响应模型"""

    error_type: str = Field(
        ...,
        description="刷新令牌错误类型",
        examples=[
            "invalid_refresh_token",
            "refresh_token_expired",
            "refresh_token_blacklisted",
        ],
    )


# ===== Token黑名单管理模式 =====


class BlacklistedToken(BaseModel):
    """黑名单Token模型

    用于Redis存储的Token撤销记录
    """

    jti: str = Field(..., description="JWT唯一标识符")
    token_type: str = Field(..., description="令牌类型", examples=["access", "refresh"])
    user_id: UUID = Field(..., description="用户ID")
    tenant_id: UUID = Field(..., description="租户ID")
    blacklisted_at: datetime = Field(..., description="加入黑名单时间")
    expires_at: datetime = Field(..., description="原始令牌过期时间")
    reason: Optional[str] = Field(
        default=None,
        description="加入黑名单原因",
        examples=["user_logout", "security_breach", "token_refresh"],
    )

    class Config:
        """Pydantic配置"""

        json_schema_extra = {
            "example": {
                "jti": "123e4567-e89b-12d3-a456-426614174000",
                "token_type": "access",
                "user_id": "987fcdeb-51d2-43a8-b456-426614174001",
                "tenant_id": "123fcdeb-51d2-43a8-b456-426614174002",
                "blacklisted_at": "2025-01-14T10:30:00Z",
                "expires_at": "2025-01-14T11:30:00Z",
                "reason": "user_logout",
            }
        }


# ===== 密码重置模式（预留） =====


class PasswordResetRequest(BaseModel):
    """密码重置请求模型（预留给后续任务）"""

    email: str = Field(..., description="用户邮箱地址", min_length=5, max_length=320)

    @validator("email")
    def validate_email_format(cls, v: str) -> str:
        """验证邮箱格式"""
        v = v.strip().lower()
        email_pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

        if not re.match(email_pattern, v):
            raise ValueError("邮箱格式无效")

        return v


# ===== 工具函数 =====


def validate_password_strength_standalone(
    password: str,
) -> Tuple[bool, List[str]]:
    """独立的密码强度验证函数

    Args:
        password: 待验证的密码

    Returns:
        tuple[bool, list[str]]: (是否通过验证, 错误信息列表)
    """
    errors = []

    if len(password) < 8:
        errors.append("密码长度至少8个字符")

    if not re.search(r"[A-Z]", password):
        errors.append("密码必须包含至少一个大写字母")

    if not re.search(r"[a-z]", password):
        errors.append("密码必须包含至少一个小写字母")

    if not re.search(r"[0-9]", password):
        errors.append("密码必须包含至少一个数字")

    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'",.<>?/|\\`~]', password):
        errors.append("密码必须包含至少一个特殊字符")

    # 检查常见弱密码
    weak_patterns = ["123456", "password", "qwerty", "abc123"]
    password_lower = password.lower()

    for pattern in weak_patterns:
        if pattern in password_lower:
            errors.append("密码不能包含常见弱密码模式")
            break

    return len(errors) == 0, errors


def validate_email_format_standalone(email: str) -> Tuple[bool, str]:
    """独立的邮箱格式验证函数

    Args:
        email: 待验证的邮箱地址

    Returns:
        tuple[bool, str]: (是否通过验证, 错误信息)
    """
    email = email.strip().lower()
    email_pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

    if not re.match(email_pattern, email):
        return False, "邮箱格式无效"

    return True, ""


# ===== Context7兼容的便捷类型 =====


class RefreshTokenSubject(BaseModel):
    """Refresh Token的Subject结构

    符合Context7的credentials.subject格式
    用于JWT payload中的用户信息
    """

    user_id: str = Field(..., description="用户ID")
    tenant_id: str = Field(..., description="租户ID")
    email: str = Field(..., description="用户邮箱")
    token_type: str = Field(default="refresh", description="令牌类型")

    class Config:
        """Pydantic配置"""

        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "tenant_id": "987fcdeb-51d2-43a8-b456-426614174001",
                "email": "user@example.com",
                "token_type": "refresh",
            }
        }
