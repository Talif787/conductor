from __future__ import annotations

import uuid

import pytest

from app.domain.run.entities import Run
from app.domain.run.repository import Page, RunFilter
from app.domain.run.value_objects import Goal, RunStatus, TenantId
from app.infrastructure.persistence.in_memory import InMemoryRunRepository


@pytest.mark.asyncio
async def test_add_get_and_isolation_by_tenant() -> None:
    store: dict[uuid.UUID, Run] = {}
    repo = InMemoryRunRepository(store)
    tenant_a = TenantId(uuid.uuid4())
    tenant_b = TenantId(uuid.uuid4())

    run = Run.create(tenant_id=tenant_a, goal=Goal("Task"))
    await repo.add(run, run.pull_events())

    assert await repo.get(tenant_a, run.id) is not None
    assert await repo.get(tenant_b, run.id) is None


@pytest.mark.asyncio
async def test_list_filters_by_status() -> None:
    store: dict[uuid.UUID, Run] = {}
    repo = InMemoryRunRepository(store)
    tenant = TenantId(uuid.uuid4())

    queued = Run.create(tenant_id=tenant, goal=Goal("A"))
    cancelled = Run.create(tenant_id=tenant, goal=Goal("B"))
    cancelled.cancel()
    await repo.add(queued, [])
    await repo.add(cancelled, [])

    result = await repo.list(tenant, RunFilter(status=RunStatus.CANCELLED), Page(limit=10))
    assert len(result.runs) == 1
    assert result.runs[0].id == cancelled.id


@pytest.mark.asyncio
async def test_idempotency_lookup() -> None:
    store: dict[uuid.UUID, Run] = {}
    repo = InMemoryRunRepository(store)
    tenant = TenantId(uuid.uuid4())
    run = Run.create(tenant_id=tenant, goal=Goal("A"), idempotency_key="key-1")
    await repo.add(run, [])

    found = await repo.find_by_idempotency_key(tenant, "key-1")
    assert found is not None and found.id == run.id
