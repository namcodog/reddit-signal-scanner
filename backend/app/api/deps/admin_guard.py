"""Helpers for protecting admin endpoints with consistent policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

from fastapi import HTTPException, Request

from ...core.admin_roles import (
    AdminRole,
    derive_admin_roles,
    has_read_permission,
    has_write_permission,
)


@dataclass(frozen=True)
class AdminGuardContext:
    roles: Tuple[AdminRole, ...]
    permissions: Tuple[str, ...]


def _extract_permissions(request: Request) -> Tuple[str, ...]:
    raw: Sequence[str] = tuple(getattr(request.state, "permissions", tuple()))
    permissions = tuple(p for p in raw if isinstance(p, str) and p)
    if not permissions:
        return tuple()
    return permissions


def _ensure_roles(request: Request, permissions: Tuple[str, ...]) -> Tuple[AdminRole, ...]:
    cached = getattr(request.state, "admin_roles", None)
    if cached is not None:
        return tuple(cached)
    roles = derive_admin_roles(permissions)
    request.state.admin_roles = roles
    return roles


def ensure_admin_read_access(request: Request) -> AdminGuardContext:
    """Ensure the current request has admin read permissions."""

    permissions = _extract_permissions(request)
    if not has_read_permission(permissions):
        raise HTTPException(status_code=403, detail="admin access required")
    roles = _ensure_roles(request, permissions)
    if not roles:
        raise HTTPException(status_code=403, detail="admin role missing")
    return AdminGuardContext(roles=roles, permissions=permissions)


def ensure_admin_write_access(request: Request) -> AdminGuardContext:
    """Ensure the current request has admin write permissions."""

    ctx = ensure_admin_read_access(request)
    if not has_write_permission(ctx.permissions):
        raise HTTPException(status_code=403, detail="admin write access required")
    return ctx


def require_specific_role(request: Request, role: AdminRole) -> AdminGuardContext:
    """Ensure a particular admin role is present."""

    ctx = ensure_admin_read_access(request)
    if role not in ctx.roles:
        raise HTTPException(status_code=403, detail=f"{role.value} role required")
    return ctx
