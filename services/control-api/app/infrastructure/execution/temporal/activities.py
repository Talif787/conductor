"""Temporal activity that executes a single tool step.

The activity is the durable, side-effecting unit. It loads the tool from the
repository, builds a ToolInvocation, and delegates to the same CompositeToolInvoker
used by the local engine, so the actual tool-execution logic is already tested.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from temporalio import activity
from temporalio.exceptions import ApplicationError

from app.application.execution.ports import ToolInvocation, ToolInvoker
from app.application.execution.temporal_dtos import StepActivityInput, StepActivityResult
from app.application.ports import UnitOfWork
from app.domain.shared.identifiers import TenantId, ToolId

UnitOfWorkFactory = Callable[[], UnitOfWork]


class ExecutionActivities:
    """Holds the dependencies a step activity needs (repository + invoker)."""

    def __init__(self, uow_factory: UnitOfWorkFactory, invoker: ToolInvoker) -> None:
        self._uow_factory = uow_factory
        self._invoker = invoker

    @activity.defn
    async def run_tool(self, request: StepActivityInput) -> StepActivityResult:
        started_at = datetime.now(UTC).isoformat()
        tenant_id = TenantId.parse(request.tenant_id)
        tool_id = ToolId.parse(request.tool_id)
        async with self._uow_factory() as uow:
            tool = await uow.tools.get(tenant_id, tool_id)
        if tool is None:
            raise ApplicationError(
                f"tool '{request.tool_id}' is not registered", non_retryable=True
            )
        invocation = ToolInvocation(tool=tool, parameters=request.parameters, inputs=request.inputs)
        try:
            output = await self._invoker.invoke(invocation)
        except Exception as exc:  # noqa: BLE001
            raise ApplicationError(str(exc), non_retryable=True) from exc
        return StepActivityResult(
            output=output,
            started_at=started_at,
            finished_at=datetime.now(UTC).isoformat(),
        )
