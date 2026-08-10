"""Mapping between ORM rows and the Run aggregate / domain events."""

from __future__ import annotations

import dataclasses

from app.domain.run.entities import Run
from app.domain.run.events import DomainEvent
from app.domain.run.value_objects import Goal, Priority, RunId, RunStatus, TenantId
from app.infrastructure.persistence.models import RunEventModel, RunModel

_BASE_EVENT_FIELDS = {"tenant_id", "run_id", "event_id", "occurred_at"}


def run_to_model(run: Run) -> RunModel:
    return RunModel(
        id=run.id.value,
        tenant_id=run.tenant_id.value,
        goal=run.goal.text,
        status=run.status.value,
        priority=run.priority.value,
        parameters=run.parameters,
        workflow_id=run.workflow_id,
        workflow_version=run.workflow_version,
        idempotency_key=run.idempotency_key,
        error=run.error,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def model_to_run(model: RunModel) -> Run:
    return Run(
        id=RunId(model.id),
        tenant_id=TenantId(model.tenant_id),
        goal=Goal(model.goal),
        priority=Priority(model.priority),
        status=RunStatus(model.status),
        parameters=dict(model.parameters or {}),
        workflow_id=model.workflow_id,
        workflow_version=model.workflow_version,
        idempotency_key=model.idempotency_key,
        error=model.error,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def event_to_model(event: DomainEvent) -> RunEventModel:
    payload = {
        key: value
        for key, value in dataclasses.asdict(event).items()
        if key not in _BASE_EVENT_FIELDS
    }
    return RunEventModel(
        id=event.event_id,
        tenant_id=event.tenant_id,
        run_id=event.run_id,
        name=event.name,
        payload=payload,
        occurred_at=event.occurred_at,
        published=False,
    )
