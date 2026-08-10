"""Entities for the Workflow Authoring context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.shared.identifiers import TenantId, WorkflowId, WorkflowVersionId
from app.domain.workflows.errors import InvalidWorkflowStateError
from app.domain.workflows.value_objects import (
    VersionStatus,
    WorkflowDefinition,
    WorkflowStatus,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class Workflow:
    id: WorkflowId
    tenant_id: TenantId
    name: str
    description: str
    status: WorkflowStatus
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(cls, tenant_id: TenantId, name: str, description: str = "") -> Workflow:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("workflow name must not be empty")
        now = _utcnow()
        return cls(
            id=WorkflowId.new(),
            tenant_id=tenant_id,
            name=cleaned,
            description=description,
            status=WorkflowStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )

    def archive(self) -> None:
        if self.status is WorkflowStatus.ARCHIVED:
            raise InvalidWorkflowStateError("workflow is already archived")
        self.status = WorkflowStatus.ARCHIVED
        self.updated_at = _utcnow()


@dataclass
class WorkflowVersion:
    id: WorkflowVersionId
    workflow_id: WorkflowId
    tenant_id: TenantId
    version: int
    status: VersionStatus
    definition: WorkflowDefinition
    created_at: datetime
    published_at: datetime | None = None

    @classmethod
    def draft(
        cls,
        workflow_id: WorkflowId,
        tenant_id: TenantId,
        version: int,
        definition: WorkflowDefinition | None = None,
    ) -> WorkflowVersion:
        return cls(
            id=WorkflowVersionId.new(),
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            version=version,
            status=VersionStatus.DRAFT,
            definition=definition or WorkflowDefinition.empty(),
            created_at=_utcnow(),
        )

    def update_definition(self, definition: WorkflowDefinition) -> None:
        if self.status is not VersionStatus.DRAFT:
            raise InvalidWorkflowStateError("only a draft version can be edited")
        self.definition = definition

    def publish(self) -> None:
        if self.status is not VersionStatus.DRAFT:
            raise InvalidWorkflowStateError("only a draft version can be published")
        self.status = VersionStatus.PUBLISHED
        self.published_at = _utcnow()

    @property
    def is_published(self) -> bool:
        return self.status is VersionStatus.PUBLISHED
