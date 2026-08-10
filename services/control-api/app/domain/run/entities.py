"""The Run aggregate root and its state machine."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.domain.run.errors import InvalidStateTransitionError
from app.domain.run.events import (
    DomainEvent,
    RunCancelled,
    RunCompleted,
    RunCreated,
    RunFailed,
    RunPlanningStarted,
    RunRunningStarted,
)
from app.domain.run.value_objects import Goal, Priority, RunId, RunStatus, TenantId

_ALLOWED_TRANSITIONS: dict[RunStatus, set[RunStatus]] = {
    RunStatus.QUEUED: {RunStatus.PLANNING, RunStatus.CANCELLED, RunStatus.FAILED},
    RunStatus.PLANNING: {RunStatus.RUNNING, RunStatus.CANCELLED, RunStatus.FAILED},
    RunStatus.RUNNING: {
        RunStatus.PAUSED,
        RunStatus.COMPLETED,
        RunStatus.CANCELLED,
        RunStatus.FAILED,
    },
    RunStatus.PAUSED: {RunStatus.RUNNING, RunStatus.CANCELLED, RunStatus.FAILED},
    RunStatus.COMPLETED: set(),
    RunStatus.FAILED: set(),
    RunStatus.CANCELLED: set(),
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Run:
    """Aggregate root guarding all run lifecycle invariants.

    State changes are only permitted through the transition methods, which
    enforce the allowed state machine and record domain events for the outbox.
    """

    def __init__(
        self,
        *,
        id: RunId,
        tenant_id: TenantId,
        goal: Goal,
        priority: Priority,
        status: RunStatus,
        parameters: dict[str, Any],
        workflow_id: str | None,
        workflow_version: str | None,
        idempotency_key: str | None,
        error: str | None,
        created_at: datetime,
        updated_at: datetime,
    ) -> None:
        self.id = id
        self.tenant_id = tenant_id
        self.goal = goal
        self.priority = priority
        self.status = status
        self.parameters = parameters
        self.workflow_id = workflow_id
        self.workflow_version = workflow_version
        self.idempotency_key = idempotency_key
        self.error = error
        self.created_at = created_at
        self.updated_at = updated_at
        self._events: list[DomainEvent] = []

    @classmethod
    def create(
        cls,
        *,
        tenant_id: TenantId,
        goal: Goal,
        priority: Priority = Priority.NORMAL,
        parameters: dict[str, Any] | None = None,
        workflow_id: str | None = None,
        workflow_version: str | None = None,
        idempotency_key: str | None = None,
    ) -> Run:
        now = _utcnow()
        run = cls(
            id=RunId.new(),
            tenant_id=tenant_id,
            goal=goal,
            priority=priority,
            status=RunStatus.QUEUED,
            parameters=parameters or {},
            workflow_id=workflow_id,
            workflow_version=workflow_version,
            idempotency_key=idempotency_key,
            error=None,
            created_at=now,
            updated_at=now,
        )
        run._record(
            RunCreated(
                tenant_id=tenant_id.value,
                run_id=run.id.value,
                goal=goal.text,
                priority=priority.value,
            )
        )
        return run

    def _record(self, event: DomainEvent) -> None:
        self._events.append(event)

    def pull_events(self) -> list[DomainEvent]:
        events = list(self._events)
        self._events.clear()
        return events

    def _transition(self, target: RunStatus) -> None:
        if target not in _ALLOWED_TRANSITIONS[self.status]:
            raise InvalidStateTransitionError(self.status.value, target.value)
        self.status = target
        self.updated_at = _utcnow()

    def start_planning(self) -> None:
        self._transition(RunStatus.PLANNING)
        self._record(RunPlanningStarted(tenant_id=self.tenant_id.value, run_id=self.id.value))

    def start_running(self) -> None:
        self._transition(RunStatus.RUNNING)
        self._record(RunRunningStarted(tenant_id=self.tenant_id.value, run_id=self.id.value))

    def complete(self) -> None:
        self._transition(RunStatus.COMPLETED)
        self._record(RunCompleted(tenant_id=self.tenant_id.value, run_id=self.id.value))

    def fail(self, reason: str) -> None:
        self._transition(RunStatus.FAILED)
        self.error = reason
        self._record(RunFailed(tenant_id=self.tenant_id.value, run_id=self.id.value, reason=reason))

    def cancel(self) -> None:
        self._transition(RunStatus.CANCELLED)
        self._record(RunCancelled(tenant_id=self.tenant_id.value, run_id=self.id.value))
