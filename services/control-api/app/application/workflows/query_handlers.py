from __future__ import annotations

from collections.abc import Callable

from app.application.ports import UnitOfWork
from app.application.workflows.dtos import WorkflowDTO, WorkflowVersionDTO
from app.application.workflows.mappers import to_version_dto, to_workflow_dto
from app.application.workflows.queries import (
    GetWorkflow,
    GetWorkflowVersion,
    ListWorkflows,
)
from app.domain.shared.identifiers import TenantId, WorkflowId
from app.domain.workflows.errors import (
    WorkflowNotFoundError,
    WorkflowVersionNotFoundError,
)

UnitOfWorkFactory = Callable[[], UnitOfWork]


class GetWorkflowHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, query: GetWorkflow) -> WorkflowDTO:
        tenant_id = TenantId.parse(query.tenant_id)
        workflow_id = WorkflowId.parse(query.workflow_id)
        async with self._uow_factory() as uow:
            workflow = await uow.workflows.get(tenant_id, workflow_id)
            if workflow is None:
                raise WorkflowNotFoundError(query.workflow_id)
            versions = await uow.workflow_versions.list_for_workflow(tenant_id, workflow_id)
            return to_workflow_dto(workflow, versions)


class ListWorkflowsHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, query: ListWorkflows) -> list[WorkflowDTO]:
        tenant_id = TenantId.parse(query.tenant_id)
        async with self._uow_factory() as uow:
            workflows = await uow.workflows.list(tenant_id)
            result: list[WorkflowDTO] = []
            for workflow in workflows:
                versions = await uow.workflow_versions.list_for_workflow(tenant_id, workflow.id)
                result.append(to_workflow_dto(workflow, versions))
            return result


class GetWorkflowVersionHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, query: GetWorkflowVersion) -> WorkflowVersionDTO:
        tenant_id = TenantId.parse(query.tenant_id)
        workflow_id = WorkflowId.parse(query.workflow_id)
        async with self._uow_factory() as uow:
            version = await uow.workflow_versions.get(tenant_id, workflow_id, query.version)
            if version is None:
                raise WorkflowVersionNotFoundError(query.workflow_id, query.version)
            return to_version_dto(version)
