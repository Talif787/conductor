"""Command handlers for the Governance context.

SubmitRunHandler is the governed entry point for execution: it evaluates policy,
then either delegates to the execution handler (allow), parks the run behind an
approval request (require_approval), or denies it (deny). Approve and reject
handlers decide a pending request; approving drives the parked run to execution.
"""

from __future__ import annotations

from collections.abc import Callable

import structlog

from app.application.execution.command_handlers import ExecuteRunHandler
from app.application.execution.commands import ExecuteRun
from app.application.governance.commands import ApproveRequest, RejectRequest, SubmitRun
from app.application.governance.dtos import ApprovalDTO, SubmitRunResultDTO
from app.application.governance.mappers import build_policy_query, to_approval_dto
from app.application.governance.policy import PolicyDecisionPoint
from app.application.ports import EventPublisher, UnitOfWork
from app.domain.execution.errors import RunNotExecutableError
from app.domain.governance.entities import ApprovalRequest as ApprovalRequestEntity
from app.domain.governance.errors import (
    ApprovalNotFoundError,
    InvalidApprovalStateError,
    RunDeniedError,
)
from app.domain.governance.value_objects import PolicyEffect
from app.domain.run.entities import Run
from app.domain.run.errors import RunNotFoundError
from app.domain.run.value_objects import RunId, RunStatus
from app.domain.shared.identifiers import ApprovalId, TenantId, ToolId, UserId, WorkflowId
from app.domain.tools.entities import Tool

logger = structlog.get_logger(__name__)

UnitOfWorkFactory = Callable[[], UnitOfWork]


async def _referenced_tools(uow: UnitOfWork, tenant_id: TenantId, run: Run) -> list[Tool]:
    if run.workflow_id is None:
        return []
    version = await uow.workflow_versions.get(
        tenant_id, WorkflowId.parse(run.workflow_id), int(run.workflow_version or 0)
    )
    if version is None:
        return []
    ordered: list[str] = []
    for step in version.definition.steps:
        if step.tool_id not in ordered:
            ordered.append(step.tool_id)
    tools: list[Tool] = []
    for raw in ordered:
        try:
            tool = await uow.tools.get(tenant_id, ToolId.parse(raw))
        except ValueError:
            tool = None
        if tool is not None:
            tools.append(tool)
    return tools


class SubmitRunHandler:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        policy: PolicyDecisionPoint,
        executor: ExecuteRunHandler,
        publisher: EventPublisher,
    ) -> None:
        self._uow_factory = uow_factory
        self._policy = policy
        self._executor = executor
        self._publisher = publisher

    async def handle(self, command: SubmitRun) -> SubmitRunResultDTO:
        tenant_id = TenantId.parse(command.tenant_id)
        run_id = RunId.parse(command.run_id)

        async with self._uow_factory() as uow:
            run = await uow.runs.get(tenant_id, run_id)
            if run is None:
                raise RunNotFoundError(command.run_id)
            if run.status is not RunStatus.QUEUED:
                raise RunNotExecutableError(
                    f"run is '{run.status.value}'; only queued runs can be submitted"
                )
            if run.workflow_id is None:
                raise RunNotExecutableError("run has no workflow to execute")
            tools = await _referenced_tools(uow, tenant_id, run)

        query = build_policy_query(
            run=run, tools=tools, principal_id=command.principal_id, roles=command.roles
        )
        decision = await self._policy.evaluate(query)
        logger.info(
            "policy.evaluated",
            run_id=command.run_id,
            effect=decision.effect.value,
            reason=decision.reason,
        )

        if decision.effect is PolicyEffect.DENY:
            await self._fail_run(tenant_id, run_id, f"denied by policy: {decision.reason}")
            raise RunDeniedError(decision.reason)

        if decision.effect is PolicyEffect.REQUIRE_APPROVAL:
            approval = await self._park_for_approval(tenant_id, run_id, decision.reason)
            return SubmitRunResultDTO(
                outcome="pending_approval", approval=to_approval_dto(approval)
            )

        execution = await self._executor.handle(
            ExecuteRun(tenant_id=command.tenant_id, run_id=command.run_id)
        )
        return SubmitRunResultDTO(outcome="executed", execution=execution)

    async def _park_for_approval(
        self, tenant_id: TenantId, run_id: RunId, reason: str
    ) -> ApprovalRequestEntity:
        async with self._uow_factory() as uow:
            run = await uow.runs.get(tenant_id, run_id)
            if run is None:
                raise RunNotFoundError(str(run_id))
            approval = ApprovalRequestEntity.open(tenant_id=tenant_id, run_id=run_id, reason=reason)
            run.await_approval(reason)
            events = run.pull_events()
            await uow.approvals.add(approval)
            await uow.runs.save(run, events)
            await uow.commit()
        await self._publisher.publish(events)
        return approval

    async def _fail_run(self, tenant_id: TenantId, run_id: RunId, reason: str) -> None:
        events: list = []
        async with self._uow_factory() as uow:
            run = await uow.runs.get(tenant_id, run_id)
            if run is not None and run.status is RunStatus.QUEUED:
                run.fail(reason)
                events = run.pull_events()
                await uow.runs.save(run, events)
                await uow.commit()
        await self._publisher.publish(events)


class ApproveRequestHandler:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        executor: ExecuteRunHandler,
    ) -> None:
        self._uow_factory = uow_factory
        self._executor = executor

    async def handle(self, command: ApproveRequest) -> SubmitRunResultDTO:
        tenant_id = TenantId.parse(command.tenant_id)
        approval_id = ApprovalId.parse(command.approval_id)
        async with self._uow_factory() as uow:
            approval = await uow.approvals.get(tenant_id, approval_id)
            if approval is None:
                raise ApprovalNotFoundError(command.approval_id)
            if not approval.is_pending:
                raise InvalidApprovalStateError(
                    f"approval request is already '{approval.status.value}'"
                )
            approval.approve(decided_by=UserId.parse(command.decided_by), note=command.note)
            await uow.approvals.save(approval)
            await uow.commit()
            run_id = approval.run_id

        execution = await self._executor.handle(
            ExecuteRun(tenant_id=command.tenant_id, run_id=str(run_id))
        )
        return SubmitRunResultDTO(
            outcome="executed", execution=execution, approval=to_approval_dto(approval)
        )


class RejectRequestHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory, publisher: EventPublisher) -> None:
        self._uow_factory = uow_factory
        self._publisher = publisher

    async def handle(self, command: RejectRequest) -> ApprovalDTO:
        tenant_id = TenantId.parse(command.tenant_id)
        approval_id = ApprovalId.parse(command.approval_id)
        events: list = []
        async with self._uow_factory() as uow:
            approval = await uow.approvals.get(tenant_id, approval_id)
            if approval is None:
                raise ApprovalNotFoundError(command.approval_id)
            if not approval.is_pending:
                raise InvalidApprovalStateError(
                    f"approval request is already '{approval.status.value}'"
                )
            approval.reject(decided_by=UserId.parse(command.decided_by), note=command.note)
            await uow.approvals.save(approval)
            run = await uow.runs.get(tenant_id, approval.run_id)
            if run is not None and run.status is RunStatus.AWAITING_APPROVAL:
                run.fail(f"approval rejected: {command.note or 'no reason given'}")
                events = run.pull_events()
                await uow.runs.save(run, events)
            await uow.commit()
        await self._publisher.publish(events)
        return to_approval_dto(approval)
