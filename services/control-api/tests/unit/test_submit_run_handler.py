from __future__ import annotations

import pytest

from app.application.execution.command_handlers import ExecuteRunHandler
from app.application.governance.command_handlers import (
    ApproveRequestHandler,
    RejectRequestHandler,
    SubmitRunHandler,
)
from app.application.governance.commands import ApproveRequest, RejectRequest, SubmitRun
from app.application.governance.queries import ListApprovals
from app.application.governance.query_handlers import ListApprovalsHandler
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
from app.domain.governance.errors import RunDeniedError
from app.domain.run.value_objects import RunId, RunStatus, TenantId
from app.domain.shared.identifiers import UserId
from app.infrastructure.execution.local_engine import LocalExecutionEngine
from app.infrastructure.execution.tool_invoker import BuiltinToolInvoker, CompositeToolInvoker
from app.infrastructure.governance.local_policy import LocalPolicyEvaluator
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


async def _author(factory, tenant_id: str) -> str:
    reg = RegisterToolHandler(factory)
    echo = await reg.handle(RegisterTool(tenant_id, "echo", "builtin", {}, {}))
    summ = await reg.handle(RegisterTool(tenant_id, "llm", "builtin", {}, {}))
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


async def _make_run(factory, tenant_id: str, workflow_id: str, priority: str = "normal") -> str:
    run = await CreateRunHandler(factory, _Pub()).handle(
        CreateRun(
            tenant_id=tenant_id,
            goal="go",
            priority=priority,
            parameters={"prompt": "hi"},
            workflow_id=workflow_id,
            workflow_version="1",
        )
    )
    return run.id


async def _status(factory, tenant_id: str, run_id: str) -> RunStatus:
    async with factory() as uow:
        run = await uow.runs.get(TenantId.parse(tenant_id), RunId.parse(run_id))
        return run.status


async def test_allow_executes_immediately() -> None:
    _, factory = _factory()
    tenant = str(TenantId.new())
    workflow = await _author(factory, tenant)
    run_id = await _make_run(factory, tenant, workflow)
    handler = SubmitRunHandler(
        factory, LocalPolicyEvaluator(), ExecuteRunHandler(factory, _engine(), _Pub()), _Pub()
    )
    result = await handler.handle(SubmitRun(tenant, run_id, principal_id="u", roles=("operator",)))
    assert result.outcome == "executed"
    assert result.execution.status == "succeeded"
    assert (await _status(factory, tenant, run_id)) is RunStatus.COMPLETED


async def test_require_approval_parks_run() -> None:
    _, factory = _factory()
    tenant = str(TenantId.new())
    workflow = await _author(factory, tenant)
    run_id = await _make_run(factory, tenant, workflow, priority="high")
    handler = SubmitRunHandler(
        factory,
        LocalPolicyEvaluator(require_approval_for_high_priority=True),
        ExecuteRunHandler(factory, _engine(), _Pub()),
        _Pub(),
    )
    result = await handler.handle(SubmitRun(tenant, run_id, principal_id="u", roles=("author",)))
    assert result.outcome == "pending_approval"
    assert result.execution is None
    assert result.approval.status == "pending"
    assert (await _status(factory, tenant, run_id)) is RunStatus.AWAITING_APPROVAL
    async with factory() as uow:
        assert await uow.run_executions.get(TenantId.parse(tenant), RunId.parse(run_id)) is None
    pending = await ListApprovalsHandler(factory).handle(ListApprovals(tenant, status="pending"))
    assert [a.id for a in pending] == [result.approval.id]


async def test_approve_executes_parked_run() -> None:
    _, factory = _factory()
    tenant = str(TenantId.new())
    workflow = await _author(factory, tenant)
    run_id = await _make_run(factory, tenant, workflow, priority="high")
    executor = ExecuteRunHandler(factory, _engine(), _Pub())
    submit = SubmitRunHandler(
        factory, LocalPolicyEvaluator(require_approval_for_high_priority=True), executor, _Pub()
    )
    result = await submit.handle(SubmitRun(tenant, run_id, principal_id="u", roles=("author",)))
    approved = await ApproveRequestHandler(factory, executor).handle(
        ApproveRequest(tenant, result.approval.id, decided_by=str(UserId.new()))
    )
    assert approved.outcome == "executed"
    assert approved.execution.status == "succeeded"
    assert approved.approval.status == "approved"
    assert (await _status(factory, tenant, run_id)) is RunStatus.COMPLETED


async def test_reject_fails_parked_run() -> None:
    _, factory = _factory()
    tenant = str(TenantId.new())
    workflow = await _author(factory, tenant)
    run_id = await _make_run(factory, tenant, workflow, priority="high")
    executor = ExecuteRunHandler(factory, _engine(), _Pub())
    submit = SubmitRunHandler(
        factory, LocalPolicyEvaluator(require_approval_for_high_priority=True), executor, _Pub()
    )
    result = await submit.handle(SubmitRun(tenant, run_id, principal_id="u", roles=("author",)))
    rejected = await RejectRequestHandler(factory, _Pub()).handle(
        RejectRequest(tenant, result.approval.id, decided_by=str(UserId.new()), note="not now")
    )
    assert rejected.status == "rejected"
    assert (await _status(factory, tenant, run_id)) is RunStatus.FAILED


async def test_deny_fails_run_and_raises() -> None:
    _, factory = _factory()
    tenant = str(TenantId.new())
    workflow = await _author(factory, tenant)
    run_id = await _make_run(factory, tenant, workflow)
    handler = SubmitRunHandler(
        factory,
        LocalPolicyEvaluator(denied_tool_kinds=("builtin",)),
        ExecuteRunHandler(factory, _engine(), _Pub()),
        _Pub(),
    )
    with pytest.raises(RunDeniedError):
        await handler.handle(SubmitRun(tenant, run_id, principal_id="u", roles=("operator",)))
    assert (await _status(factory, tenant, run_id)) is RunStatus.FAILED
