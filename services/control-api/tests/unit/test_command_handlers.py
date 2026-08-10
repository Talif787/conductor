from __future__ import annotations

import uuid

import pytest

from app.application.run.command_handlers import CancelRunHandler, CreateRunHandler
from app.application.run.commands import CancelRun, CreateRun
from app.domain.run.errors import RunNotFound
from app.infrastructure.persistence.in_memory import InMemoryUnitOfWork


class _CapturingPublisher:
    def __init__(self) -> None:
        self.published: list = []

    async def publish(self, events) -> None:
        self.published.extend(events)


@pytest.fixture
def store() -> dict:
    return {}


@pytest.fixture
def uow_factory(store):
    return lambda: InMemoryUnitOfWork(store)


@pytest.mark.asyncio
async def test_create_run_persists_and_publishes(uow_factory, store) -> None:
    publisher = _CapturingPublisher()
    handler = CreateRunHandler(uow_factory, publisher)
    tenant_id = str(uuid.uuid4())

    dto = await handler.handle(CreateRun(tenant_id=tenant_id, goal="Draft release notes"))

    assert dto.status == "queued"
    assert len(store) == 1
    assert len(publisher.published) == 1


@pytest.mark.asyncio
async def test_create_run_is_idempotent(uow_factory) -> None:
    publisher = _CapturingPublisher()
    handler = CreateRunHandler(uow_factory, publisher)
    tenant_id = str(uuid.uuid4())
    command = CreateRun(tenant_id=tenant_id, goal="Reconcile invoices", idempotency_key="abc-123")

    first = await handler.handle(command)
    second = await handler.handle(command)

    assert first.id == second.id
    assert len(publisher.published) == 1


@pytest.mark.asyncio
async def test_cancel_run(uow_factory) -> None:
    publisher = _CapturingPublisher()
    tenant_id = str(uuid.uuid4())
    created = await CreateRunHandler(uow_factory, publisher).handle(
        CreateRun(tenant_id=tenant_id, goal="Backfill data")
    )

    cancelled = await CancelRunHandler(uow_factory, publisher).handle(
        CancelRun(tenant_id=tenant_id, run_id=created.id)
    )

    assert cancelled.status == "cancelled"


@pytest.mark.asyncio
async def test_cancel_missing_run_raises(uow_factory) -> None:
    publisher = _CapturingPublisher()
    handler = CancelRunHandler(uow_factory, publisher)
    with pytest.raises(RunNotFound):
        await handler.handle(
            CancelRun(tenant_id=str(uuid.uuid4()), run_id=str(uuid.uuid4()))
        )
