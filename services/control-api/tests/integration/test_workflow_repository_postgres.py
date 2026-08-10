"""Postgres-backed workflow authoring tests.

Run with a live database:  make test-integration
These verify JSONB definition round-tripping and the workflow/version
insert ordering that in-memory tests cannot catch.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.application.tools.command_handlers import RegisterToolHandler
from app.application.tools.commands import RegisterTool
from app.application.workflows.command_handlers import (
    CreateWorkflowHandler,
    PublishVersionHandler,
    UpdateDraftHandler,
)
from app.application.workflows.commands import (
    CreateWorkflow,
    PublishVersion,
    UpdateDraft,
)
from app.config.settings import get_settings
from app.domain.shared.identifiers import TenantId, WorkflowId
from app.infrastructure.persistence.models import (
    ToolModel,
    WorkflowModel,
    WorkflowVersionModel,
)
from app.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.integration


@pytest.fixture
async def session_factory():
    engine = create_async_engine(get_settings().database.url, future=True)
    try:
        async with engine.connect():
            pass
    except Exception:  # noqa: BLE001
        await engine.dispose()
        pytest.skip("PostgreSQL is not available")
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


@pytest.mark.asyncio
async def test_workflow_definition_round_trips_through_postgres(session_factory) -> None:
    def factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    tenant = str(TenantId.new())
    tool = await RegisterToolHandler(factory).handle(
        RegisterTool(tenant, f"fetch-{uuid.uuid4().hex}", "http", {"type": "object"}, {})
    )
    workflow = await CreateWorkflowHandler(factory).handle(
        CreateWorkflow(tenant, f"pipeline-{uuid.uuid4().hex}")
    )
    definition = {"steps": [{"step_id": "a", "name": "A", "tool_id": tool.id}]}
    await UpdateDraftHandler(factory).handle(UpdateDraft(tenant, workflow.id, 1, definition))
    published = await PublishVersionHandler(factory).handle(PublishVersion(tenant, workflow.id, 1))
    assert published.status == "published"

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        stored = await uow.workflow_versions.get(
            TenantId.parse(tenant), WorkflowId.parse(workflow.id), 1
        )
        assert stored is not None
        assert stored.is_published
        assert [s.step_id for s in stored.definition.steps] == ["a"]
        assert stored.definition.steps[0].tool_id == tool.id

    workflow_uuid = uuid.UUID(workflow.id)
    tool_uuid = uuid.UUID(tool.id)
    async with session_factory() as session:
        await session.execute(
            delete(WorkflowVersionModel).where(WorkflowVersionModel.workflow_id == workflow_uuid)
        )
        await session.execute(delete(WorkflowModel).where(WorkflowModel.id == workflow_uuid))
        await session.execute(delete(ToolModel).where(ToolModel.id == tool_uuid))
        await session.commit()
