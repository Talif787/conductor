"""In-memory adapters used by unit and API tests (no database required)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from types import TracebackType

from app.application.ports import UnitOfWork
from app.domain.identity.entities import Membership, RefreshToken, Tenant, User
from app.domain.identity.repository import (
    MembershipRepository,
    RefreshTokenRepository,
    TenantRepository,
    UserRepository,
)
from app.domain.identity.value_objects import Email
from app.domain.run.entities import Run
from app.domain.run.events import DomainEvent
from app.domain.run.repository import Page, PagedRuns, RunFilter, RunRepository
from app.domain.run.value_objects import RunId
from app.domain.shared.identifiers import TenantId, UserId


@dataclass
class InMemoryDatabase:
    runs: dict[uuid.UUID, Run] = field(default_factory=dict)
    tenants: dict[uuid.UUID, Tenant] = field(default_factory=dict)
    users: dict[uuid.UUID, User] = field(default_factory=dict)
    memberships: dict[uuid.UUID, Membership] = field(default_factory=dict)
    refresh_tokens: dict[uuid.UUID, RefreshToken] = field(default_factory=dict)


class InMemoryRunRepository(RunRepository):
    def __init__(self, store: dict[uuid.UUID, Run]) -> None:
        self._store = store
        self.published_events: list[DomainEvent] = []

    async def add(self, run: Run, events: Sequence[DomainEvent]) -> None:
        self._store[run.id.value] = run
        self.published_events.extend(events)

    async def save(self, run: Run, events: Sequence[DomainEvent]) -> None:
        self._store[run.id.value] = run
        self.published_events.extend(events)

    async def get(self, tenant_id: TenantId, run_id: RunId) -> Run | None:
        run = self._store.get(run_id.value)
        if run is not None and run.tenant_id == tenant_id:
            return run
        return None

    async def find_by_idempotency_key(
        self, tenant_id: TenantId, idempotency_key: str
    ) -> Run | None:
        for run in self._store.values():
            if run.tenant_id == tenant_id and run.idempotency_key == idempotency_key:
                return run
        return None

    async def list(self, tenant_id: TenantId, run_filter: RunFilter, page: Page) -> PagedRuns:
        runs = [run for run in self._store.values() if run.tenant_id == tenant_id]
        if run_filter.status is not None:
            runs = [run for run in runs if run.status == run_filter.status]
        runs.sort(key=lambda r: (r.created_at, r.id.value), reverse=True)
        return PagedRuns(runs=runs[: page.limit], next_cursor=None)


class InMemoryTenantRepository(TenantRepository):
    def __init__(self, store: dict[uuid.UUID, Tenant]) -> None:
        self._store = store

    async def add(self, tenant: Tenant) -> None:
        self._store[tenant.id.value] = tenant

    async def get(self, tenant_id: TenantId) -> Tenant | None:
        return self._store.get(tenant_id.value)


class InMemoryUserRepository(UserRepository):
    def __init__(self, store: dict[uuid.UUID, User]) -> None:
        self._store = store

    async def add(self, user: User) -> None:
        self._store[user.id.value] = user

    async def get(self, user_id: UserId) -> User | None:
        return self._store.get(user_id.value)

    async def find_by_email(self, email: Email) -> User | None:
        for user in self._store.values():
            if user.email == email:
                return user
        return None


class InMemoryMembershipRepository(MembershipRepository):
    def __init__(self, store: dict[uuid.UUID, Membership]) -> None:
        self._store = store

    async def add(self, membership: Membership) -> None:
        self._store[membership.id.value] = membership

    async def find_by_user(self, user_id: UserId) -> list[Membership]:
        return [m for m in self._store.values() if m.user_id == user_id]


class InMemoryRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self, store: dict[uuid.UUID, RefreshToken]) -> None:
        self._store = store

    async def add(self, token: RefreshToken) -> None:
        self._store[token.id.value] = token

    async def find_by_hash(self, token_hash: str) -> RefreshToken | None:
        for token in self._store.values():
            if token.token_hash == token_hash:
                return token
        return None

    async def mark_used(self, token_id: uuid.UUID) -> None:
        token = self._store.get(token_id)
        if token is not None:
            token.used = True

    async def revoke_family(self, family_id: uuid.UUID) -> None:
        for token in self._store.values():
            if token.family_id == family_id:
                token.revoked = True


class InMemoryUnitOfWork(UnitOfWork):
    def __init__(self, db: InMemoryDatabase) -> None:
        self._db = db
        self.committed = False

    async def __aenter__(self) -> InMemoryUnitOfWork:
        self.runs = InMemoryRunRepository(self._db.runs)
        self.tenants = InMemoryTenantRepository(self._db.tenants)
        self.users = InMemoryUserRepository(self._db.users)
        self.memberships = InMemoryMembershipRepository(self._db.memberships)
        self.refresh_tokens = InMemoryRefreshTokenRepository(self._db.refresh_tokens)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        return None
