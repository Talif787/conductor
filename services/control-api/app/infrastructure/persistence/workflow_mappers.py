from __future__ import annotations

from app.domain.shared.identifiers import TenantId, WorkflowId, WorkflowVersionId
from app.domain.workflows.entities import Workflow, WorkflowVersion
from app.domain.workflows.value_objects import (
    VersionStatus,
    WorkflowDefinition,
    WorkflowStatus,
)
from app.infrastructure.persistence.models import WorkflowModel, WorkflowVersionModel


def workflow_to_model(workflow: Workflow) -> WorkflowModel:
    return WorkflowModel(
        id=workflow.id.value,
        tenant_id=workflow.tenant_id.value,
        name=workflow.name,
        description=workflow.description,
        status=workflow.status.value,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
    )


def model_to_workflow(model: WorkflowModel) -> Workflow:
    return Workflow(
        id=WorkflowId(model.id),
        tenant_id=TenantId(model.tenant_id),
        name=model.name,
        description=model.description,
        status=WorkflowStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def version_to_model(version: WorkflowVersion) -> WorkflowVersionModel:
    return WorkflowVersionModel(
        id=version.id.value,
        workflow_id=version.workflow_id.value,
        tenant_id=version.tenant_id.value,
        version=version.version,
        status=version.status.value,
        definition=version.definition.to_dict(),
        created_at=version.created_at,
        published_at=version.published_at,
    )


def model_to_version(model: WorkflowVersionModel) -> WorkflowVersion:
    return WorkflowVersion(
        id=WorkflowVersionId(model.id),
        workflow_id=WorkflowId(model.workflow_id),
        tenant_id=TenantId(model.tenant_id),
        version=model.version,
        status=VersionStatus(model.status),
        definition=WorkflowDefinition.from_dict(model.definition),
        created_at=model.created_at,
        published_at=model.published_at,
    )
