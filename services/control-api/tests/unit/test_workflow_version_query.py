"""Unit tests for reading a workflow version's definition."""

from __future__ import annotations

import pytest

from app.application.tools.command_handlers import RegisterToolHandler
from app.application.tools.commands import RegisterTool
from app.application.workflows.command_handlers import (
    CreateWorkflowHandler,
    UpdateDraftHandler,
)
from app.application.workflows.commands import CreateWorkflow, UpdateDraft
from app.application.workflows.queries import GetWorkflowVersion
from app.application.workflows.query_handlers import GetWorkflowVersionHandler
from app.domain.shared.identifiers import TenantId
from app.domain.workflows.errors import WorkflowVersionNotFoundError
from app.infrastructure.persistence.in_memory import InMemoryDatabase, InMemoryUnitOfWork


@pytest.fixture
def uow_factory():
    db = InMemoryDatabase()
    return lambda: InMemoryUnitOfWork(db)


async def _seed(uow_factory, tenant: str) -> str:
    tool = await RegisterToolHandler(uow_factory).handle(
        RegisterTool(tenant, "summarize", "builtin", {}, {})
    )
    workflow = await CreateWorkflowHandler(uow_factory).handle(CreateWorkflow(tenant, "Pipeline"))
    definition = {"steps": [{"step_id": "sum", "name": "Summarize", "tool_id": tool.id}]}
    await UpdateDraftHandler(uow_factory).handle(UpdateDraft(tenant, workflow.id, 1, definition))
    return workflow.id


async def test_get_version_returns_definition(uow_factory) -> None:
    tenant = str(TenantId.new())
    workflow_id = await _seed(uow_factory, tenant)

    dto = await GetWorkflowVersionHandler(uow_factory).handle(
        GetWorkflowVersion(tenant_id=tenant, workflow_id=workflow_id, version=1)
    )

    assert dto.version == 1
    assert dto.status == "draft"
    steps = dto.definition["steps"]
    assert len(steps) == 1 and steps[0]["step_id"] == "sum"


async def test_get_missing_version_raises(uow_factory) -> None:
    tenant = str(TenantId.new())
    workflow_id = await _seed(uow_factory, tenant)
    with pytest.raises(WorkflowVersionNotFoundError):
        await GetWorkflowVersionHandler(uow_factory).handle(
            GetWorkflowVersion(tenant_id=tenant, workflow_id=workflow_id, version=99)
        )


async def test_get_version_is_tenant_scoped(uow_factory) -> None:
    tenant = str(TenantId.new())
    workflow_id = await _seed(uow_factory, tenant)
    other_tenant = str(TenantId.new())
    with pytest.raises(WorkflowVersionNotFoundError):
        await GetWorkflowVersionHandler(uow_factory).handle(
            GetWorkflowVersion(tenant_id=other_tenant, workflow_id=workflow_id, version=1)
        )
