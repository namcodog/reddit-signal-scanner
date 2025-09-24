"""Admin role derivation helpers.

Defines canonical admin roles (operations/support/technical) and utility functions
for deriving roles from permission tokens injected by the JWT middleware.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from typing import Iterable, Sequence, Tuple


class AdminRole(str, Enum):
    """Canonical admin roles exposed to downstream services."""

    OPERATIONS = "operations"
    SUPPORT = "support"
    TECHNICAL = "technical"


# Permission tokens that imply the corresponding admin role.
# NOTE: operations/support roles also inherit read access privileges.
_ROLE_TOKENS: dict[AdminRole, frozenset[str]] = {
    AdminRole.OPERATIONS: frozenset({"admin:write", "admin:ops"}),
    AdminRole.SUPPORT: frozenset({"admin:read", "admin:support"}),
    AdminRole.TECHNICAL: frozenset({"admin:tech", "admin"}),
}


def _normalise_permissions(permissions: Sequence[str]) -> Tuple[str, ...]:
    """Return a deterministic tuple of unique permission tokens."""

    unique = {perm for perm in permissions if isinstance(perm, str) and perm}
    return tuple(sorted(unique))


@lru_cache(maxsize=512)
def _derive_roles_cached(permissions_key: Tuple[str, ...]) -> Tuple[AdminRole, ...]:
    perms = set(permissions_key)
    roles: set[AdminRole] = set()
    for role, tokens in _ROLE_TOKENS.items():
        if perms.intersection(tokens):
            roles.add(role)
    # operations and support imply baseline technical context when admin token exists
    if AdminRole.TECHNICAL not in roles and "admin" in perms:
        roles.add(AdminRole.TECHNICAL)
    return tuple(sorted(roles, key=lambda item: item.value))


def derive_admin_roles(permissions: Sequence[str]) -> Tuple[AdminRole, ...]:
    """Derive admin roles from a list of permission strings."""

    permissions_key = _normalise_permissions(permissions)
    if not permissions_key:
        return tuple()
    return _derive_roles_cached(permissions_key)


def has_any_role(permissions: Sequence[str], roles: Iterable[AdminRole]) -> bool:
    """Return True when any of the requested roles can be derived."""

    derived = set(derive_admin_roles(permissions))
    return any(role in derived for role in roles)


def has_role(permissions: Sequence[str], role: AdminRole) -> bool:
    """Lightweight helper for single-role lookups."""

    return role in derive_admin_roles(permissions)


READ_ACCESS_TOKENS = frozenset({"admin", "admin:read", "admin:write", "admin:tech"})
WRITE_ACCESS_TOKENS = frozenset({"admin:write"})


def has_read_permission(permissions: Sequence[str]) -> bool:
    """Whether the permission set grants read access to admin resources."""

    return bool(READ_ACCESS_TOKENS.intersection(permissions))


def has_write_permission(permissions: Sequence[str]) -> bool:
    """Whether the permission set grants write/decision making access."""

    return bool(WRITE_ACCESS_TOKENS.intersection(permissions))
