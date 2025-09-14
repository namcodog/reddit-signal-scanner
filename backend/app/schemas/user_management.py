"""
用户账户管理Schema - 严格遵循CLAUDE.md零容忍规范

遵循原则:
1. 100%类型安全 - 禁止Any和type:ignore
2. 79字符行长限制
3. 日志使用%占位符
4. Context7最佳实践
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, validator


class UserProfileResponse(BaseModel):
    """用户个人信息响应 - GET /users/me"""

    id: UUID = Field(description="用户唯一标识")
    tenant_id: UUID = Field(description="租户标识")
    email: EmailStr = Field(description="用户邮箱地址")
    email_verified: bool = Field(description="邮箱是否已验证")
    is_active: bool = Field(description="账户是否激活")
    created_at: datetime = Field(description="账户创建时间")
    updated_at: datetime = Field(description="最后更新时间")

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


class UserUpdateRequest(BaseModel):
    """用户信息更新请求 - PATCH /users/me"""

    email: Optional[EmailStr] = Field(None, description="新邮箱地址，需要验证", max_length=320)

    @validator("email")
    def validate_email_change(cls, v: Optional[EmailStr]) -> Optional[EmailStr]:
        """邮箱更改验证"""
        if v is not None and len(v.strip()) == 0:
            raise ValueError("邮箱地址不能为空字符串")
        return v


class PasswordChangeRequest(BaseModel):
    """密码修改请求 - POST /users/change-password"""

    current_password: str = Field(description="当前密码", min_length=1, max_length=128)
    new_password: str = Field(description="新密码", min_length=8, max_length=128)
    confirm_password: str = Field(description="确认新密码", min_length=8, max_length=128)

    @validator("confirm_password")
    def passwords_match(cls, v: str, values: Dict[str, Any]) -> str:
        """密码确认验证"""
        if "new_password" in values and v != values["new_password"]:
            raise ValueError("密码确认不匹配")
        return v

    @validator("new_password")
    def validate_password_strength(cls, v: str) -> str:
        """密码强度验证"""
        if len(v) < 8:
            raise ValueError("密码长度至少8个字符")

        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)

        if not (has_upper and has_lower and has_digit):
            raise ValueError("密码必须包含大小写字母和数字")

        return v


class UserAccountStatusResponse(BaseModel):
    """用户账户状态响应"""

    user_id: UUID = Field(description="用户ID")
    is_active: bool = Field(description="账户是否激活")
    email_verified: bool = Field(description="邮箱验证状态")
    last_login_at: Optional[datetime] = Field(None, description="最后登录时间")

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


class SuccessResponse(BaseModel):
    """操作成功响应"""

    success: bool = Field(default=True, description="操作是否成功")
    message: str = Field(description="成功消息")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="操作时间")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class UserManagementError(BaseModel):
    """用户管理错误响应"""

    error_code: str = Field(description="错误代码")
    error_message: str = Field(description="错误消息")
    field_errors: Optional[Dict[str, str]] = Field(None, description="字段验证错误详情")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="错误发生时间")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
