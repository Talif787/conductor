"""In-memory adapters used by unit and API tests (no database required)."""
from __future__ import annotations

import uuid
from collections.abc import Sequence
from types import TracebackType

from app.application.ports import UnitOfWork
from app.domain.run.entities import Run
from app.domain.run.events import DomainEvent
from app.domain.run.repository import Page, PagedRuns, RunFilter, RunRepository
from app.domain.run.value_objects import RunId, TenantId


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
        window = runs[: page.limit]
        return PagedRuns(runs=window, next_cursor=None)


class InMemoryUnitOfWork(UnitOfWork):
    def __init__(self, store: dict[uuid.UUID, Run]) -> None:
        self._store = store
        self.committed = False

    async def __aenter__(self) -> "InMemoryUnitOfWork":
        self.runs = InMemoryRunRepository(self._store)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        return None
