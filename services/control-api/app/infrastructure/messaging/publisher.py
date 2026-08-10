"""Event publisher adapters.

Phase 1 ships a logging publisher. Phase 6 replaces this with a Kafka producer
that reads the outbox (run_events) and publishes with at-least-once delivery.
"""

from __future__ import annotations

from collections.abc import Sequence

import structlog

from app.application.ports import EventPublisher
from app.domain.run.events import DomainEvent

logger = structlog.get_logger("domain_events")


class LoggingEventPublisher(EventPublisher):
    async def publish(self, events: Sequence[DomainEvent]) -> None:
        for event in events:
            logger.info(
                "domain_event.published",
                event_name=event.name,
                event_id=str(event.event_id),
                run_id=str(event.run_id),
                tenant_id=str(event.tenant_id),
            )
