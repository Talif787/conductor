"""The run_view read model and the projector that maintains it from events.

run_view is a denormalized, read-optimized view of each run's current state,
rebuilt from the run lifecycle events rather than written by the command side.
The projector is pure logic over a repository port, so it is fully testable
without a database.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from datetime import datetime

from app.application.eventing.records import EventRecord

# Maps a run lifecycle event to the status it drives the read model into.
_STATUS_BY_EVENT: dict[str, str] = {
    "RunCreated": "queued",
    "RunPlanningStarted": "planning",
    "RunRunningStarted": "running",
    "RunAwaitingApproval": "awaiting_approval",
    "RunCompleted": "completed",
    "RunFailed": "failed",
    "RunCancelled": "cancelled",
}


@dataclass(slots=True)
class RunView:
    run_id: str
    tenant_id: str
    status: str
    goal: str
    priority: str
    created_at: datetime
    updated_at: datetime
    event_count: int


class RunViewRepository(abc.ABC):
    @abc.abstractmethod
    async def get(self, tenant_id: str, run_id: str) -> RunView | None: ...

    @abc.abstractmethod
    async def upsert(self, view: RunView) -> None: ...

    @abc.abstractmethod
    async def list(self, tenant_id: str, limit: int) -> list[RunView]: ...

    @abc.abstractmethod
    async def status_counts(self, tenant_id: str) -> dict[str, int]: ...


class RunViewProjector:
    """Applies one event to the run_view read model."""

    async def apply(self, views: RunViewRepository, record: EventRecord) -> None:
        status = _STATUS_BY_EVENT.get(record.event_name)
        if status is None:
            # An event the read model does not track; ignore it safely.
            return

        if record.event_name == "RunCreated":
            await views.upsert(
                RunView(
                    run_id=record.run_id,
                    tenant_id=record.tenant_id,
                    status="queued",
                    goal=str(record.payload.get("goal", "")),
                    priority=str(record.payload.get("priority", "normal")),
                    created_at=record.occurred_at,
                    updated_at=record.occurred_at,
                    event_count=1,
                )
            )
            return

        existing = await views.get(record.tenant_id, record.run_id)
        if existing is None:
            # A status event arrived before its RunCreated (out of order or
            # pruned): materialize a minimal row so the view stays consistent.
            await views.upsert(
                RunView(
                    run_id=record.run_id,
                    tenant_id=record.tenant_id,
                    status=status,
                    goal="",
                    priority="normal",
                    created_at=record.occurred_at,
                    updated_at=record.occurred_at,
                    event_count=1,
                )
            )
            return

        existing.status = status
        existing.updated_at = record.occurred_at
        existing.event_count += 1
        await views.upsert(existing)
