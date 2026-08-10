from __future__ import annotations

import pytest

from app.application.run.command_handlers import CreateRunHandler
from app.application.run.commands import CreateRun
from app.application.tools.command_handlers import RegisterToolHandler
from app.application.tools.commands import RegisterTool
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
from app.domain.shared.identifiers import TenantId
from app.domain.workflows.errors import (
    InvalidWorkflowStateError,
    WorkflowNameConflictError,
    WorkflowNotFoundError,
    WorkflowNotPublishedError,
    WorkflowValidationError,
    WorkflowVersionNotFoundError,
)
from app.infrastructure.persistence.in_memory import InMemoryDatabase, InMemoryUnitOfWork


class _NullPublisher:
    async def publish(self, events) -> None:  # noqa: ANN001
        return None


@pytest.fixture
def uow_factory():
    db = InMemoryDatabase()
    return lambda: InMemoryUnitOfWork(db)


async def _two_tools(uow_factory, tenant: str) -> tuple[str, str]:
    reg = RegisterToolHandler(uow_factory)
    a = await reg.handle(RegisterTool(tenant, "fetch", "http", {}, {}))
    b = await reg.handle(RegisterTool(tenant, "summarize", "builtin", {}, {}))
    return a.id, b.id


def _definition(tool_a: str, tool_b: str) -> dict:
    return {
        "steps": [
            {"step_id": "fetch", "name": "Fetch", "tool_id": tool_a},
            {"step_id": "sum", "name": "Summarize", "tool_id": tool_b, "depends_on": ["fetch"]},
        ]
    }


async def test_create_yields_draft_v1(uow_factory) -> None:
    tenant = str(TenantId.new())
    workflow = await CreateWorkflowHandler(uow_factory).handle(CreateWorkflow(tenant, "Pipeline"))
    assert workflow.status == "active"
    assert [v.version for v in workflow.versions] == [1]
    assert workflow.versions[0].status == "draft"


async def test_duplicate_workflow_name_rejected(uow_factory) -> None:
    tenant = str(TenantId.new())
    await CreateWorkflowHandler(uow_factory).handle(CreateWorkflow(tenant, "Pipeline"))
    with pytest.raises(WorkflowNameConflictError):
        await CreateWorkflowHandler(uow_factory).handle(CreateWorkflow(tenant, "Pipeline"))


async def test_publishing_empty_draft_fails_validation(uow_factory) -> None:
    tenant = str(TenantId.new())
    workflow = await CreateWorkflowHandler(uow_factory).handle(CreateWorkflow(tenant, "Pipeline"))
    with pytest.raises(WorkflowValidationError):
        await PublishVersionHandler(uow_factory).handle(PublishVersion(tenant, workflow.id, 1))


async def test_full_publish_and_immutability(uow_factory) -> None:
    tenant = str(TenantId.new())
    tool_a, tool_b = await _two_tools(uow_factory, tenant)
    workflow = await CreateWorkflowHandler(uow_factory).handle(CreateWorkflow(tenant, "Pipeline"))
    definition = _definition(tool_a, tool_b)

    await UpdateDraftHandler(uow_factory).handle(UpdateDraft(tenant, workflow.id, 1, definition))
    published = await PublishVersionHandler(uow_factory).handle(
        PublishVersion(tenant, workflow.id, 1)
    )
    assert published.status == "published"
    assert published.published_at is not None

    with pytest.raises(InvalidWorkflowStateError):
        await UpdateDraftHandler(uow_factory).handle(
            UpdateDraft(tenant, workflow.id, 1, definition)
        )


async def test_create_draft_copies_latest_and_blocks_second_draft(uow_factory) -> None:
    tenant = str(TenantId.new())
    tool_a, tool_b = await _two_tools(uow_factory, tenant)
    workflow = await CreateWorkflowHandler(uow_factory).handle(CreateWorkflow(tenant, "Pipeline"))
    await UpdateDraftHandler(uow_factory).handle(
        UpdateDraft(tenant, workflow.id, 1, _definition(tool_a, tool_b))
    )
    await PublishVersionHandler(uow_factory).handle(PublishVersion(tenant, workflow.id, 1))

    draft = await CreateDraftHandler(uow_factory).handle(CreateDraft(tenant, workflow.id))
    assert draft.version == 2
    assert draft.status == "draft"
    assert len(draft.definition["steps"]) == 2

    with pytest.raises(InvalidWorkflowStateError):
        await CreateDraftHandler(uow_factory).handle(CreateDraft(tenant, workflow.id))


async def test_archive_and_tenant_isolation(uow_factory) -> None:
    tenant = str(TenantId.new())
    workflow = await CreateWorkflowHandler(uow_factory).handle(CreateWorkflow(tenant, "Pipeline"))
    archived = await ArchiveWorkflowHandler(uow_factory).handle(
        ArchiveWorkflow(tenant, workflow.id)
    )
    assert archived.status == "archived"

    other = str(TenantId.new())
    with pytest.raises(WorkflowNotFoundError):
        await ArchiveWorkflowHandler(uow_factory).handle(ArchiveWorkflow(other, workflow.id))


async def test_run_requires_published_workflow_version(uow_factory) -> None:
    tenant = str(TenantId.new())
    tool_a, tool_b = await _two_tools(uow_factory, tenant)
    workflow = await CreateWorkflowHandler(uow_factory).handle(CreateWorkflow(tenant, "Pipeline"))
    await UpdateDraftHandler(uow_factory).handle(
        UpdateDraft(tenant, workflow.id, 1, _definition(tool_a, tool_b))
    )
    runs = CreateRunHandler(uow_factory, _NullPublisher())

    with pytest.raises(WorkflowNotPublishedError):
        await runs.handle(
            CreateRun(tenant_id=tenant, goal="go", workflow_id=workflow.id, workflow_version="1")
        )

    await PublishVersionHandler(uow_factory).handle(PublishVersion(tenant, workflow.id, 1))
    created = await runs.handle(
        CreateRun(tenant_id=tenant, goal="go", workflow_id=workflow.id, workflow_version="1")
    )
    assert created.status == "queued"

    with pytest.raises(WorkflowVersionNotFoundError):
        await runs.handle(
            CreateRun(tenant_id=tenant, goal="go", workflow_id=workflow.id, workflow_version="9")
        )
