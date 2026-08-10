"""The authenticated subject of a request."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.identity.roles import Permission, Role, permissions_for
from app.domain.shared.identifiers import TenantId, UserId


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: UserId
    tenant_id: TenantId
    roles: frozenset[Role]

    @property
    def permissions(self) -> frozenset[Permission]:
        return permissions_for(self.roles)

    def has_permission(self, permission: Permission) -> bool:
        return permission in self.permissions
