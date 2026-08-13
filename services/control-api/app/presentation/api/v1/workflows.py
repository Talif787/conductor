"""HTTP endpoints for Workflow Authoring."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.application.auth.principal import Principal
from app.application.workflows.command_handlers import (
    ArchiveWorkflowHandler,
    CreateDraftHandler,
    CreateWorkflowHandler,
    PublishVersionHandler,
    UpdateDraftHandler,
)
from app.application.workflows.commands import (
    ArchiveWorkflow,
    CreateDraft,
    CreateWorkflow,
    PublishVersion,
    UpdateDraft,
)
from app.application.workflows.queries import (
    GetWorkflow,
    GetWorkflowVersion,
    ListWorkflows,
)
from app.application.workflows.query_handlers import (
    GetWorkflowHandler,
    GetWorkflowVersionHandler,
    ListWorkflowsHandler,
)
from app.domain.identity.roles import Permission
from app.presentation.api.dependencies import (
    provide_archive_workflow_handler,
    provide_create_draft_handler,
    provide_create_workflow_handler,
    provide_get_workflow_handler,
    provide_get_workflow_version_handler,
    provide_list_workflows_handler,
    provide_publish_version_handler,
    provide_update_draft_handler,
    require_permission,
)
from app.presentation.api.v1.schemas import (
    CreateWorkflowRequest,
    UpdateDraftRequest,
    WorkflowResponse,
    WorkflowVersionResponse,
)

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    body: CreateWorkflowRequest,
    principal: Annotated[Principal, Depends(require_permission(Permission.WORKFLOWS_WRITE))],
    handler: Annotated[CreateWorkflowHandler, Depends(provide_create_workflow_handler)],
) -> WorkflowResponse:
    dto = await handler.handle(
        CreateWorkflow(
            tenant_id=str(principal.tenant_id), name=body.name, description=body.description
        )
    )
    return WorkflowResponse.from_dto(dto)


@router.get("", response_model=list[WorkflowResponse])
async def list_workflows(
    principal: Annotated[Principal, Depends(require_permission(Permission.WORKFLOWS_READ))],
    handler: Annotated[ListWorkflowsHandler, Depends(provide_list_workflows_handler)],
) -> list[WorkflowResponse]:
    dtos = await handler.handle(ListWorkflows(tenant_id=str(principal.tenant_id)))
    return [WorkflowResponse.from_dto(dto) for dto in dtos]


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str,
    principal: Annotated[Principal, Depends(require_permission(Permission.WORKFLOWS_READ))],
    handler: Annotated[GetWorkflowHandler, Depends(provide_get_workflow_handler)],
) -> WorkflowResponse:
    dto = await handler.handle(
        GetWorkflow(tenant_id=str(principal.tenant_id), workflow_id=workflow_id)
    )
    return WorkflowResponse.from_dto(dto)


@router.get("/{workflow_id}/versions/{version}", response_model=WorkflowVersionResponse)
async def get_workflow_version(
    workflow_id: str,
    version: int,
    principal: Annotated[Principal, Depends(require_permission(Permission.WORKFLOWS_READ))],
    handler: Annotated[GetWorkflowVersionHandler, Depends(provide_get_workflow_version_handler)],
) -> WorkflowVersionResponse:
    dto = await handler.handle(
        GetWorkflowVersion(
            tenant_id=str(principal.tenant_id),
            workflow_id=workflow_id,
            version=version,
        )
    )
    return WorkflowVersionResponse.from_dto(dto)


@router.put("/{workflow_id}/versions/{version}", response_model=WorkflowVersionResponse)
async def update_draft(
    workflow_id: str,
    version: int,
    body: UpdateDraftRequest,
    principal: Annotated[Principal, Depends(require_permission(Permission.WORKFLOWS_WRITE))],
    handler: Annotated[UpdateDraftHandler, Depends(provide_update_draft_handler)],
) -> WorkflowVersionResponse:
    dto = await handler.handle(
        UpdateDraft(
            tenant_id=str(principal.tenant_id),
            workflow_id=workflow_id,
            version=version,
            definition=body.definition.model_dump(),
        )
    )
    return WorkflowVersionResponse.from_dto(dto)


@router.post("/{workflow_id}/versions/{version}/publish", response_model=WorkflowVersionResponse)
async def publish_version(
    workflow_id: str,
    version: int,
    principal: Annotated[Principal, Depends(require_permission(Permission.WORKFLOWS_PUBLISH))],
    handler: Annotated[PublishVersionHandler, Depends(provide_publish_version_handler)],
) -> WorkflowVersionResponse:
    dto = await handler.handle(
        PublishVersion(tenant_id=str(principal.tenant_id), workflow_id=workflow_id, version=version)
    )
    return WorkflowVersionResponse.from_dto(dto)


@router.post(
    "/{workflow_id}/versions",
    response_model=WorkflowVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_draft(
    workflow_id: str,
    principal: Annotated[Principal, Depends(require_permission(Permission.WORKFLOWS_WRITE))],
    handler: Annotated[CreateDraftHandler, Depends(provide_create_draft_handler)],
) -> WorkflowVersionResponse:
    dto = await handler.handle(
        CreateDraft(tenant_id=str(principal.tenant_id), workflow_id=workflow_id)
    )
    return WorkflowVersionResponse.from_dto(dto)


@router.post("/{workflow_id}/archive", response_model=WorkflowResponse)
async def archive_workflow(
    workflow_id: str,
    principal: Annotated[Principal, Depends(require_permission(Permission.WORKFLOWS_WRITE))],
    handler: Annotated[ArchiveWorkflowHandler, Depends(provide_archive_workflow_handler)],
) -> WorkflowResponse:
    dto = await handler.handle(
        ArchiveWorkflow(tenant_id=str(principal.tenant_id), workflow_id=workflow_id)
    )
    return WorkflowResponse.from_dto(dto)
