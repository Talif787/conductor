from __future__ import annotations

import pytest

from app.application.execution.command_handlers import ExecuteRunHandler
from app.application.execution.commands import ExecuteRun
from app.application.execution.queries import GetRunExecution
from app.application.execution.query_handlers import GetRunExecutionHandler
from app.application.run.command_handlers import CreateRunHandler
from app.application.run.commands import CreateRun
from app.application.tools.command_handlers import RegisterToolHandler
from app.application.tools.commands import RegisterTool
from app.application.workflows.command_handlers import (
    CreateWorkflowHandler,
    PublishVersionHandler,
    UpdateDraftHandler,
)
from app.application.workflows.commands import CreateWorkflow, PublishVersion, UpdateDraft
from app.domain.execution.errors import RunExecutionNotFoundError, RunNotExecutableError
from app.domain.run.value_objects import RunId, TenantId
from app.infrastructure.execution.local_engine import LocalExecutionEngine
from app.infrastructure.execution.tool_invoker import BuiltinToolInvoker, CompositeToolInvoker
from app.infrastructure.llm.gateway import FakeLLMGateway
from app.infrastructure.persistence.in_memory import InMemoryDatabase, InMemoryUnitOfWork


class _Pub:
    async def publish(self, events) -> None:  # noqa: ANN001
        return None


def _factory():
    db = InMemoryDatabase()
    return db, (lambda: InMemoryUnitOfWork(db))


def _engine() -> LocalExecutionEngine:
    return LocalExecutionEngine(CompositeToolInvoker(BuiltinToolInvoker(FakeLLMGateway())))


async def _author(factory, tenant_id: str, sum_tool: str) -> str:
    reg = RegisterToolHandler(factory)
    echo = await reg.handle(RegisterTool(tenant_id, "echo", "builtin", {}, {}))
    summ = await reg.handle(RegisterTool(tenant_id, sum_tool, "builtin", {}, {}))
    workflow = await CreateWorkflowHandler(factory).handle(CreateWorkflow(tenant_id, "Pipeline"))
    definition = {
        "steps": [
            {"step_id": "fetch", "tool_id": echo.id},
            {"step_id": "sum", "tool_id": summ.id, "depends_on": ["fetch"]},
        ]
    }
    await UpdateDraftHandler(factory).handle(UpdateDraft(tenant_id, workflow.id, 1, definition))
    await PublishVersionHandler(factory).handle(PublishVersion(tenant_id, workflow.id, 1))
    return workflow.id


async def test_execute_success_completes_run() -> None:
    _, factory = _factory()
    tenant_id = str(TenantId.new())
    workflow_id = await _author(factory, tenant_id, "llm")
    run = await CreateRunHandler(factory, _Pub()).handle(
        CreateRun(
            tenant_id=tenant_id,
            goal="summarize",
            parameters={"prompt": "hello"},
            workflow_id=workflow_id,
            workflow_version="1",
        )
    )
    execution = await ExecuteRunHandler(factory, _engine(), _Pub()).handle(
        ExecuteRun(tenant_id, run.id)
    )
    assert execution.status == "succeeded"
    assert [s.status for s in execution.steps] == ["succeeded", "succeeded"]
    async with factory() as uow:
        stored = await uow.runs.get(TenantId.parse(tenant_id), RunId.parse(run.id))
        assert stored.status.value == "completed"


async def test_execute_is_rejected_when_not_queued() -> None:
    _, factory = _factory()
    tenant_id = str(TenantId.new())
    workflow_id = await _author(factory, tenant_id, "llm")
    run = await CreateRunHandler(factory, _Pub()).handle(
        CreateRun(tenant_id=tenant_id, goal="go", workflow_id=workflow_id, workflow_version="1")
    )
    await ExecuteRunHandler(factory, _engine(), _Pub()).handle(ExecuteRun(tenant_id, run.id))
    with pytest.raises(RunNotExecutableError):
        await ExecuteRunHandler(factory, _engine(), _Pub()).handle(ExecuteRun(tenant_id, run.id))


async def test_failing_step_fails_run() -> None:
    _, factory = _factory()
    tenant_id = str(TenantId.new())
    workflow_id = await _author(factory, tenant_id, "no-such-builtin")
    run = await CreateRunHandler(factory, _Pub()).handle(
        CreateRun(tenant_id=tenant_id, goal="go", workflow_id=workflow_id, workflow_version="1")
    )
    execution = await ExecuteRunHandler(factory, _engine(), _Pub()).handle(
        ExecuteRun(tenant_id, run.id)
    )
    status = {s.step_id: s.status for s in execution.steps}
    assert status == {"fetch": "succeeded", "sum": "failed"}
    assert execution.status == "failed"
    async with factory() as uow:
        stored = await uow.runs.get(TenantId.parse(tenant_id), RunId.parse(run.id))
        assert stored.status.value == "failed"


async def test_run_without_workflow_cannot_execute() -> None:
    _, factory = _factory()
    tenant_id = str(TenantId.new())
    run = await CreateRunHandler(factory, _Pub()).handle(
        CreateRun(tenant_id=tenant_id, goal="no workflow")
    )
    with pytest.raises(RunNotExecutableError):
        await ExecuteRunHandler(factory, _engine(), _Pub()).handle(ExecuteRun(tenant_id, run.id))


async def test_get_execution_missing_raises() -> None:
    _, factory = _factory()
    tenant_id = str(TenantId.new())
    run = await CreateRunHandler(factory, _Pub()).handle(CreateRun(tenant_id=tenant_id, goal="x"))
    with pytest.raises(RunExecutionNotFoundError):
        await GetRunExecutionHandler(factory).handle(GetRunExecution(tenant_id, run.id))
