"""The serializable envelope carried from the outbox to the bus and projectors."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class EventRecord:
    event_id: str
    event_name: str
    tenant_id: str
    run_id: str
    occurred_at: datetime
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable form used when publishing to an external bus."""
        return {
            "event_id": self.event_id,
            "event_name": self.event_name,
            "tenant_id": self.tenant_id,
            "run_id": self.run_id,
            "occurred_at": self.occurred_at.isoformat(),
            "payload": self.payload,
        }
