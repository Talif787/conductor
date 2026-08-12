"""Unit tests for the transactional outbox relay."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from app.application.eventing.records import EventRecord
from app.application.projections.run_view import RunViewProjector
from app.infrastructure.eventing.relay import OutboxRelay
from app.infrastructure.persistence.in_memory import InMemoryDatabase, InMemoryUnitOfWork

_BASE = datetime(2026, 8, 11, tzinfo=UTC)


class _FakeBus:
    def __init__(self) -> None:
        self.published: list[EventRecord] = []

    async def publish(self, records: Sequence[EventRecord]) -> None:
        self.published.extend(records)


class _FailingBus:
    async def publish(self, records: Sequence[EventRecord]) -> None:
        raise RuntimeError("broker down")


def _record(name: str, run_id: str, offset: int, **payload: object) -> EventRecord:
    return EventRecord(
        event_id=f"{name}:{run_id}",
        event_name=name,
        tenant_id="ten",
        run_id=run_id,
        occurred_at=_BASE + timedelta(seconds=offset),
        payload=dict(payload),
    )


def _seed() -> InMemoryDatabase:
    db = InMemoryDatabase()
    db.outbox_events = [
        _record("RunRunningStarted", "r1", 2),
        _record("RunCreated", "r1", 0, goal="summarize", priority="normal"),
        _record("RunPlanningStarted", "r1", 1),
        _record("RunCompleted", "r1", 3),
        _record("RunCreated", "r2", 0, goal="deploy", priority="high"),
        _record("RunFailed", "r2", 1, reason="boom"),
    ]
    return db


async def test_relay_drains_projects_and_marks_published() -> None:
    db = _seed()

    def uow_factory() -> InMemoryUnitOfWork:
        return InMemoryUnitOfWork(db)

    bus = _FakeBus()
    relay = OutboxRelay(uow_factory, bus, RunViewProjector(), batch_size=100)

    processed = await relay.run_once()
    assert processed == 6
    assert len(db.outbox_published) == 6

    async with uow_factory() as uow:
        v1 = await uow.run_view.get("ten", "r1")
        v2 = await uow.run_view.get("ten", "r2")
        counts = await uow.run_view.status_counts("ten")
    assert v1 is not None and v1.status == "completed" and v1.event_count == 4
    assert v2 is not None and v2.status == "failed" and v2.event_count == 2
    assert counts == {"completed": 1, "failed": 1}

    # The bus receives every event, ordered globally by occurred_at.
    assert {r.event_id for r in bus.published} == {e.event_id for e in db.outbox_events}
    assert [r.occurred_at for r in bus.published] == sorted(r.occurred_at for r in bus.published)


async def test_relay_returns_zero_when_empty() -> None:
    db = InMemoryDatabase()
    relay = OutboxRelay(lambda: InMemoryUnitOfWork(db), _FakeBus(), RunViewProjector())
    assert await relay.run_once() == 0


async def test_relay_respects_batch_size() -> None:
    db = InMemoryDatabase()
    db.outbox_events = [
        _record("RunCreated", f"b{i}", i, goal="g", priority="low") for i in range(3)
    ]
    relay = OutboxRelay(
        lambda: InMemoryUnitOfWork(db), _FakeBus(), RunViewProjector(), batch_size=2
    )
    assert await relay.run_once() == 2
    assert await relay.run_once() == 1
    assert await relay.run_once() == 0


async def test_relay_survives_bus_failure() -> None:
    # A broker failure must not crash the loop; local projection is already
    # committed, so events stay marked published (at-most-once external).
    db = _seed()

    def uow_factory() -> InMemoryUnitOfWork:
        return InMemoryUnitOfWork(db)

    relay = OutboxRelay(uow_factory, _FailingBus(), RunViewProjector(), batch_size=100)
    processed = await relay.run_once()
    assert processed == 6
    assert len(db.outbox_published) == 6
    async with uow_factory() as uow:
        v1 = await uow.run_view.get("ten", "r1")
    assert v1 is not None and v1.status == "completed"
