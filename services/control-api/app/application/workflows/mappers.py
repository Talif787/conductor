from __future__ import annotations

from collections.abc import Iterable

from app.application.workflows.dtos import (
    WorkflowDTO,
    WorkflowVersionDTO,
    WorkflowVersionSummaryDTO,
)
from app.domain.workflows.entities import Workflow, WorkflowVersion


def to_version_dto(version: WorkflowVersion) -> WorkflowVersionDTO:
    return WorkflowVersionDTO(
        id=str(version.id),
        workflow_id=str(version.workflow_id),
        version=version.version,
        status=version.status.value,
        definition=version.definition.to_dict(),
        created_at=version.created_at.isoformat(),
        published_at=version.published_at.isoformat() if version.published_at else None,
    )


def to_version_summary(version: WorkflowVersion) -> WorkflowVersionSummaryDTO:
    return WorkflowVersionSummaryDTO(
        version=version.version,
        status=version.status.value,
        published_at=version.published_at.isoformat() if version.published_at else None,
    )


def to_workflow_dto(workflow: Workflow, versions: Iterable[WorkflowVersion]) -> WorkflowDTO:
    ordered = sorted(versions, key=lambda v: v.version)
    return WorkflowDTO(
        id=str(workflow.id),
        name=workflow.name,
        description=workflow.description,
        status=workflow.status.value,
        created_at=workflow.created_at.isoformat(),
        updated_at=workflow.updated_at.isoformat(),
        versions=[to_version_summary(v) for v in ordered],
    )
