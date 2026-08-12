"""Event bus adapters. NullEventBus is the default (logs only)."""

from __future__ import annotations

from collections.abc import Sequence

import structlog

from app.application.eventing.ports import EventBus
from app.application.eventing.records import EventRecord

logger = structlog.get_logger("eventing")


class NullEventBus(EventBus):
    """Default bus: records are projected locally but not shipped anywhere.

    Publishing is logged so the relay's activity is observable without a broker.
    """

    async def publish(self, records: Sequence[EventRecord]) -> None:
        for record in records:
            logger.info(
                "event.published",
                bus="null",
                event_name=record.event_name,
                event_id=record.event_id,
                run_id=record.run_id,
            )
