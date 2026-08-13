"""Repository ports for the Identity bounded context."""

from __future__ import annotations

import abc
import uuid

from app.domain.identity.entities import Membership, RefreshToken, Tenant, User
from app.domain.identity.value_objects import Email
from app.domain.shared.identifiers import TenantId, UserId


class TenantRepository(abc.ABC):
    @abc.abstractmethod
    async def add(self, tenant: Tenant) -> None: ...

    @abc.abstractmethod
    async def get(self, tenant_id: TenantId) -> Tenant | None: ...


class UserRepository(abc.ABC):
    @abc.abstractmethod
    async def add(self, user: User) -> None: ...

    @abc.abstractmethod
    async def get(self, user_id: UserId) -> User | None: ...

    @abc.abstractmethod
    async def find_by_email(self, email: Email) -> User | None: ...


class MembershipRepository(abc.ABC):
    @abc.abstractmethod
    async def add(self, membership: Membership) -> None: ...

    @abc.abstractmethod
    async def find_by_user(self, user_id: UserId) -> list[Membership]: ...

    @abc.abstractmethod
    async def find_by_tenant(self, tenant_id: TenantId) -> list[Membership]: ...


class RefreshTokenRepository(abc.ABC):
    @abc.abstractmethod
    async def add(self, token: RefreshToken) -> None: ...

    @abc.abstractmethod
    async def find_by_hash(self, token_hash: str) -> RefreshToken | None: ...

    @abc.abstractmethod
    async def mark_used(self, token_id: uuid.UUID) -> None: ...

    @abc.abstractmethod
    async def revoke_family(self, family_id: uuid.UUID) -> None: ...
