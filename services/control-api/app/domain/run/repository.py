"""Repository port for the Run aggregate (implemented in infrastructure)."""

from __future__ import annotations

import abc
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.run.entities import Run
from app.domain.run.events import DomainEvent
from app.domain.run.value_objects import RunId, RunStatus, TenantId


@dataclass(frozen=True, slots=True)
class Page:
    limit: int
    cursor: str | None = None


@dataclass(frozen=True, slots=True)
class RunFilter:
    status: RunStatus | None = None


@dataclass(frozen=True, slots=True)
class PagedRuns:
    runs: list[Run]
    next_cursor: str | None


class RunRepository(abc.ABC):
    @abc.abstractmethod
    async def add(self, run: Run, events: Sequence[DomainEvent]) -> None: ...

    @abc.abstractmethod
    async def save(self, run: Run, events: Sequence[DomainEvent]) -> None: ...

    @abc.abstractmethod
    async def get(self, tenant_id: TenantId, run_id: RunId) -> Run | None: ...

    @abc.abstractmethod
    async def find_by_idempotency_key(
        self, tenant_id: TenantId, idempotency_key: str
    ) -> Run | None: ...

    @abc.abstractmethod
    async def list(self, tenant_id: TenantId, run_filter: RunFilter, page: Page) -> PagedRuns: ...
