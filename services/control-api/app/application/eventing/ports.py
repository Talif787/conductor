"""Ports for eventing: the outbox reader and the external event bus.

Both are provider agnostic. The outbox is drained by the relay; the bus has a
NullEventBus default and an opt-in KafkaEventBus. Neither is required for the
control API to serve requests, only for the relay worker to run.
"""

from __future__ import annotations

import abc
from collections.abc import Sequence

from app.application.eventing.records import EventRecord


class OutboxRepository(abc.ABC):
    @abc.abstractmethod
    async def fetch_unpublished(self, limit: int) -> list[EventRecord]: ...

    @abc.abstractmethod
    async def mark_published(self, event_ids: Sequence[str]) -> None: ...


class EventBus(abc.ABC):
    @abc.abstractmethod
    async def publish(self, records: Sequence[EventRecord]) -> None: ...
