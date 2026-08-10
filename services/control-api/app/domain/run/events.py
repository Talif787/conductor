"""Domain events emitted by the Run aggregate."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    tenant_id: uuid.UUID
    run_id: uuid.UUID
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    occurred_at: datetime = field(default_factory=_utcnow)

    @property
    def name(self) -> str:
        return type(self).__name__


@dataclass(frozen=True, kw_only=True)
class RunCreated(DomainEvent):
    goal: str
    priority: str


@dataclass(frozen=True, kw_only=True)
class RunPlanningStarted(DomainEvent):
    pass


@dataclass(frozen=True, kw_only=True)
class RunRunningStarted(DomainEvent):
    pass


@dataclass(frozen=True, kw_only=True)
class RunCompleted(DomainEvent):
    pass


@dataclass(frozen=True, kw_only=True)
class RunFailed(DomainEvent):
    reason: str


@dataclass(frozen=True, kw_only=True)
class RunCancelled(DomainEvent):
    pass
