"""Mapping between the Run aggregate and application DTOs."""
from __future__ import annotations

from app.application.run.dtos import RunDTO, RunSummaryDTO
from app.domain.run.entities import Run


def to_run_dto(run: Run) -> RunDTO:
    return RunDTO(
        id=str(run.id),
        tenant_id=str(run.tenant_id),
        goal=run.goal.text,
        status=run.status.value,
        priority=run.priority.value,
        parameters=run.parameters,
        workflow_id=run.workflow_id,
        workflow_version=run.workflow_version,
        error=run.error,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def to_run_summary_dto(run: Run) -> RunSummaryDTO:
    return RunSummaryDTO(
        id=str(run.id),
        goal=run.goal.text,
        status=run.status.value,
        priority=run.priority.value,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )
