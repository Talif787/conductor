from __future__ import annotations

from collections.abc import Callable

import structlog

from app.application.ports import UnitOfWork
from app.application.workflows.commands import (
    ArchiveWorkflow,
    CreateDraft,
    CreateWorkflow,
    PublishVersion,
    UpdateDraft,
)
from app.application.workflows.dtos import WorkflowDTO, WorkflowVersionDTO
from app.application.workflows.mappers import to_version_dto, to_workflow_dto
from app.domain.shared.identifiers import TenantId, WorkflowId
from app.domain.workflows.entities import Workflow, WorkflowVersion
from app.domain.workflows.errors import (
    InvalidWorkflowStateError,
    WorkflowNameConflictError,
    WorkflowNotFoundError,
    WorkflowVersionNotFoundError,
)
from app.domain.workflows.validation import validate_definition
from app.domain.workflows.value_objects import VersionStatus, WorkflowDefinition

logger = structlog.get_logger(__name__)

UnitOfWorkFactory = Callable[[], UnitOfWork]


class CreateWorkflowHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, command: CreateWorkflow) -> WorkflowDTO:
        tenant_id = TenantId.parse(command.tenant_id)
        async with self._uow_factory() as uow:
            if await uow.workflows.find_by_name(tenant_id, command.name.strip()) is not None:
                raise WorkflowNameConflictError(command.name.strip())
            workflow = Workflow.create(tenant_id, command.name, command.description)
            first = WorkflowVersion.draft(workflow.id, tenant_id, version=1)
            await uow.workflows.add(workflow)
            await uow.flush()
            await uow.workflow_versions.add(first)
            await uow.commit()
        logger.info("workflow.created", workflow_id=str(workflow.id), tenant_id=str(tenant_id))
        return to_workflow_dto(workflow, [first])


class UpdateDraftHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, command: UpdateDraft) -> WorkflowVersionDTO:
        tenant_id = TenantId.parse(command.tenant_id)
        workflow_id = WorkflowId.parse(command.workflow_id)
        definition = WorkflowDefinition.from_dict(command.definition)
        async with self._uow_factory() as uow:
            version = await uow.workflow_versions.get(tenant_id, workflow_id, command.version)
            if version is None:
                raise WorkflowVersionNotFoundError(command.workflow_id, command.version)
            version.update_definition(definition)
            await uow.workflow_versions.save(version)
            await uow.commit()
        return to_version_dto(version)


class PublishVersionHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, command: PublishVersion) -> WorkflowVersionDTO:
        tenant_id = TenantId.parse(command.tenant_id)
        workflow_id = WorkflowId.parse(command.workflow_id)
        async with self._uow_factory() as uow:
            version = await uow.workflow_versions.get(tenant_id, workflow_id, command.version)
            if version is None:
                raise WorkflowVersionNotFoundError(command.workflow_id, command.version)
            tools = await uow.tools.list(tenant_id)
            available = {str(tool.id) for tool in tools}
            validate_definition(version.definition, available)
            version.publish()
            await uow.workflow_versions.save(version)
            await uow.commit()
        logger.info("workflow.published", workflow_id=str(workflow_id), version=command.version)
        return to_version_dto(version)


class CreateDraftHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, command: CreateDraft) -> WorkflowVersionDTO:
        tenant_id = TenantId.parse(command.tenant_id)
        workflow_id = WorkflowId.parse(command.workflow_id)
        async with self._uow_factory() as uow:
            workflow = await uow.workflows.get(tenant_id, workflow_id)
            if workflow is None:
                raise WorkflowNotFoundError(command.workflow_id)
            versions = await uow.workflow_versions.list_for_workflow(tenant_id, workflow_id)
            if any(v.status is VersionStatus.DRAFT for v in versions):
                raise InvalidWorkflowStateError("an open draft version already exists")
            latest = max(versions, key=lambda v: v.version)
            new_version = WorkflowVersion.draft(
                workflow_id, tenant_id, version=latest.version + 1, definition=latest.definition
            )
            await uow.workflow_versions.add(new_version)
            await uow.commit()
        return to_version_dto(new_version)


class ArchiveWorkflowHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, command: ArchiveWorkflow) -> WorkflowDTO:
        tenant_id = TenantId.parse(command.tenant_id)
        workflow_id = WorkflowId.parse(command.workflow_id)
        async with self._uow_factory() as uow:
            workflow = await uow.workflows.get(tenant_id, workflow_id)
            if workflow is None:
                raise WorkflowNotFoundError(command.workflow_id)
            workflow.archive()
            await uow.workflows.save(workflow)
            versions = await uow.workflow_versions.list_for_workflow(tenant_id, workflow_id)
            await uow.commit()
        return to_workflow_dto(workflow, versions)
