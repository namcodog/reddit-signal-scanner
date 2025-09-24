"""Schemas for admin session/guard responses."""

from __future__ import annotations

from typing import Tuple

from pydantic import BaseModel, Field

from ...core.admin_roles import AdminRole


class AdminSessionData(BaseModel):
    user_id: str = Field(..., description="当前管理员的用户ID")
    tenant_id: str = Field(..., description="所属租户ID")
    email: str | None = Field(default=None, description="管理员邮箱，用于展示")
    roles: Tuple[AdminRole, ...] = Field(..., description="推导出的管理员角色列表")
    permissions: Tuple[str, ...] = Field(..., description="JWT 权限原始列表")


class AdminSessionResponse(BaseModel):
    code: int = Field(default=0, description="状态码，0 表示成功")
    data: AdminSessionData
    trace_id: str | None = Field(default=None, description="请求追踪ID")
