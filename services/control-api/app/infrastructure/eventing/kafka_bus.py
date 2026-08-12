"""Kafka event bus (opt-in). aiokafka is imported lazily so the default path
never requires it."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from app.application.eventing.ports import EventBus
from app.application.eventing.records import EventRecord


class KafkaEventBus(EventBus):
    def __init__(self, *, bootstrap_servers: str, topic: str) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._topic = topic
        self._producer: Any | None = None

    async def _ensure_producer(self) -> Any:
        if self._producer is None:
            from aiokafka import AIOKafkaProducer

            self._producer = AIOKafkaProducer(bootstrap_servers=self._bootstrap_servers)
            await self._producer.start()
        return self._producer

    async def publish(self, records: Sequence[EventRecord]) -> None:
        producer = await self._ensure_producer()
        for record in records:
            await producer.send_and_wait(
                self._topic,
                key=record.run_id.encode("utf-8"),
                value=json.dumps(record.to_dict()).encode("utf-8"),
            )

    async def aclose(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None
