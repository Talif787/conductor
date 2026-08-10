"""Roles, permissions, and the role-to-permission map (RBAC)."""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    AUTHOR = "author"
    OPERATOR = "operator"
    VIEWER = "viewer"


class Permission(StrEnum):
    RUNS_READ = "runs:read"
    RUNS_CREATE = "runs:create"
    RUNS_CANCEL = "runs:cancel"
    MEMBERS_READ = "members:read"
    MEMBERS_WRITE = "members:write"


_ALL: frozenset[Permission] = frozenset(Permission)
_OPERATOR: frozenset[Permission] = frozenset(
    {Permission.RUNS_READ, Permission.RUNS_CREATE, Permission.RUNS_CANCEL}
)

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.OWNER: _ALL,
    Role.ADMIN: _ALL,
    Role.AUTHOR: _OPERATOR | frozenset({Permission.MEMBERS_READ}),
    Role.OPERATOR: _OPERATOR,
    Role.VIEWER: frozenset({Permission.RUNS_READ}),
}


def permissions_for(roles: Iterable[Role]) -> frozenset[Permission]:
    granted: set[Permission] = set()
    for role in roles:
        granted |= ROLE_PERMISSIONS.get(role, frozenset())
    return frozenset(granted)
