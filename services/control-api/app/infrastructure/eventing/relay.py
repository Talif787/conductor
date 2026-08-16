"""Transactional outbox relay: python -m app.infrastructure.eventing.relay

Drains unpublished run_events in order, applies each to the read-model
projector, marks them published (all in one transaction), then publishes them
to the configured event bus. The local projection and the outbox marking commit
atomically, so the read model is exactly-once; external publication happens
after commit and is best-effort (at-most-once on relay crash). A stricter
at-least-once external guarantee would publish before marking, accepting
possible re-delivery.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

import structlog

from app.application.eventing.ports import EventBus
from app.application.ports import UnitOfWork
from app.application.projections.run_view import RunViewProjector
from app.infrastructure.eventing.bus import NullEventBus
from app.infrastructure.observability.metrics import EVENTS_PUBLISHED_TOTAL

if TYPE_CHECKING:
    from app.config.settings import EventingSettings

logger = structlog.get_logger("relay")


def build_event_bus(settings: EventingSettings) -> EventBus:
    if settings.bus == "kafka":
        # Imported lazily so the default path never imports aiokafka.
        from app.infrastructure.eventing.kafka_bus import KafkaEventBus

        return KafkaEventBus(
            bootstrap_servers=settings.kafka_bootstrap_servers, topic=settings.topic
        )
    return NullEventBus()


class OutboxRelay:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        bus: EventBus,
        projector: RunViewProjector,
        *,
        batch_size: int = 100,
        poll_interval: float = 1.0,
    ) -> None:
        self._uow_factory = uow_factory
        self._bus = bus
        self._projector = projector
        self._batch_size = batch_size
        self._poll_interval = poll_interval

    async def run_once(self) -> int:
        async with self._uow_factory() as uow:
            records = await uow.outbox.fetch_unpublished(self._batch_size)
            if not records:
                return 0
            for record in records:
                await self._projector.apply(uow.run_view, record)
            await uow.outbox.mark_published([r.event_id for r in records])
            await uow.commit()

        try:
            await self._bus.publish(records)
        except Exception as exc:  # noqa: BLE001
            # Read models are already committed; log and keep draining rather
            # than crash the loop on a transient broker failure.
            logger.error("relay.publish_failed", error=str(exc), count=len(records))
        else:
            for record in records:
                EVENTS_PUBLISHED_TOTAL.labels(event_name=record.event_name).inc()
        return len(records)

    async def run(self, stop: asyncio.Event | None = None) -> None:
        while stop is None or not stop.is_set():
            processed = await self.run_once()
            if processed == 0:
                await asyncio.sleep(self._poll_interval)

    async def drain_all(self, max_batches: int = 10_000) -> int:
        """Drain every currently-pending event, then return. Used by the
        one-shot entrypoint (a scheduled `--once` run) so the process exits
        instead of looping."""
        total = 0
        for _ in range(max_batches):
            processed = await self.run_once()
            if processed == 0:
                break
            total += processed
        return total


async def main(*, once: bool = False) -> None:
    logging.basicConfig(level=logging.INFO)
    from app.config.settings import get_settings
    from app.infrastructure.persistence.session import (
        create_engine,
        create_session_factory,
    )
    from app.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    settings = get_settings()
    engine = create_engine(settings.database)
    session_factory = create_session_factory(engine)

    def uow_factory() -> UnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    bus = build_event_bus(settings.events)
    relay = OutboxRelay(
        uow_factory,
        bus,
        RunViewProjector(),
        batch_size=settings.events.relay_batch_size,
        poll_interval=settings.events.relay_poll_interval_seconds,
    )
    logger.info("relay.starting", bus=settings.events.bus, topic=settings.events.topic, once=once)
    try:
        if once:
            processed = await relay.drain_all()
            logger.info("relay.drained", processed=processed)
        else:
            await relay.run()
    finally:
        aclose = getattr(bus, "aclose", None)
        if aclose is not None:
            await aclose()
        await engine.dispose()


if __name__ == "__main__":
    import sys

    asyncio.run(main(once="--once" in sys.argv))
