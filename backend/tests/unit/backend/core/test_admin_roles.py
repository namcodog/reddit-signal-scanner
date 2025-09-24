from __future__ import annotations

from app.core.admin_roles import (
    AdminRole,
    derive_admin_roles,
    has_read_permission,
    has_role,
    has_write_permission,
)


def test_operations_role_from_write_permission() -> None:
    roles = derive_admin_roles(["admin", "admin:write"])
    assert AdminRole.OPERATIONS in roles
    assert AdminRole.TECHNICAL in roles  # inherit baseline technical context


def test_support_role_from_read_permission() -> None:
    roles = derive_admin_roles(["admin:read"])
    assert roles == (AdminRole.SUPPORT,)


def test_technical_role_from_admin_only() -> None:
    roles = derive_admin_roles(["admin"])
    assert roles == (AdminRole.TECHNICAL,)


def test_no_roles_when_permissions_empty() -> None:
    roles = derive_admin_roles([])
    assert roles == tuple()


def test_has_role_helper() -> None:
    assert has_role(["admin", "admin:write"], AdminRole.OPERATIONS)
    assert not has_role(["admin:read"], AdminRole.OPERATIONS)


def test_read_and_write_permission_helpers() -> None:
    assert has_read_permission(["admin:write"])
    assert has_read_permission(["admin:read"])
    assert not has_write_permission(["admin:read"])
    assert has_write_permission(["admin:write"])
