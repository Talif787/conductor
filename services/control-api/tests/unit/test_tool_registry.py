from __future__ import annotations

import uuid

import pytest

from app.application.tools.command_handlers import RegisterToolHandler, UpdateToolHandler
from app.application.tools.commands import RegisterTool, UpdateTool
from app.application.tools.queries import GetTool, ListTools
from app.application.tools.query_handlers import GetToolHandler, ListToolsHandler
from app.domain.shared.identifiers import TenantId
from app.domain.tools.errors import ToolNameConflictError, ToolNotFoundError
from app.infrastructure.persistence.in_memory import InMemoryDatabase, InMemoryUnitOfWork


@pytest.fixture
def uow_factory():
    db = InMemoryDatabase()
    return lambda: InMemoryUnitOfWork(db)


async def test_register_and_get(uow_factory) -> None:
    tenant = str(TenantId.new())
    registered = await RegisterToolHandler(uow_factory).handle(
        RegisterTool(tenant, "fetch", "http", {"type": "object"}, {})
    )
    fetched = await GetToolHandler(uow_factory).handle(GetTool(tenant, registered.id))
    assert fetched.name == "fetch"
    assert fetched.kind == "http"


async def test_duplicate_name_rejected(uow_factory) -> None:
    tenant = str(TenantId.new())
    await RegisterToolHandler(uow_factory).handle(RegisterTool(tenant, "fetch", "http", {}, {}))
    with pytest.raises(ToolNameConflictError):
        await RegisterToolHandler(uow_factory).handle(
            RegisterTool(tenant, "fetch", "builtin", {}, {})
        )


async def test_update_then_list(uow_factory) -> None:
    tenant = str(TenantId.new())
    registered = await RegisterToolHandler(uow_factory).handle(
        RegisterTool(tenant, "fetch", "http", {}, {})
    )
    updated = await UpdateToolHandler(uow_factory).handle(
        UpdateTool(tenant, registered.id, description="now documented")
    )
    assert updated.description == "now documented"
    listed = await ListToolsHandler(uow_factory).handle(ListTools(tenant))
    assert len(listed) == 1


async def test_missing_tool_raises(uow_factory) -> None:
    tenant = str(TenantId.new())
    with pytest.raises(ToolNotFoundError):
        await GetToolHandler(uow_factory).handle(GetTool(tenant, str(uuid.uuid4())))


async def test_tools_are_tenant_scoped(uow_factory) -> None:
    tenant_a = str(TenantId.new())
    tenant_b = str(TenantId.new())
    await RegisterToolHandler(uow_factory).handle(RegisterTool(tenant_a, "fetch", "http", {}, {}))
    assert await ListToolsHandler(uow_factory).handle(ListTools(tenant_b)) == []
