"""Pure mapping between domain objects and the Temporal boundary DTOs.

No temporalio import here, so both directions are unit testable without a
cluster. The engine adapter is a thin shell around these functions.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.application.execution.temporal_dtos import (
    RunWorkflowInput,
    RunWorkflowResult,
    WorkflowStepSpec,
)
from app.domain.execution.entities import RunExecution, StepExecution
from app.domain.execution.value_objects import ExecutionStatus
from app.domain.run.entities import Run
from app.domain.shared.identifiers import RunExecutionId, StepExecutionId
from app.domain.workflows.value_objects import WorkflowDefinition


def to_workflow_input(run: Run, definition: WorkflowDefinition) -> RunWorkflowInput:
    return RunWorkflowInput(
        tenant_id=str(run.tenant_id),
        run_id=str(run.id),
        parameters=dict(run.parameters or {}),
        steps=[
            WorkflowStepSpec(
                step_id=step.step_id,
                tool_id=step.tool_id,
                depends_on=list(step.depends_on),
            )
            for step in definition.steps
        ],
    )


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def to_run_execution(run: Run, started_at: datetime, result: RunWorkflowResult) -> RunExecution:
    steps = [
        StepExecution(
            id=StepExecutionId.new(),
            step_id=outcome.step_id,
            tool_id=outcome.tool_id,
            position=outcome.position,
            status=ExecutionStatus(outcome.status),
            output=outcome.output,
            error=outcome.error,
            started_at=_parse_dt(outcome.started_at),
            finished_at=_parse_dt(outcome.finished_at),
        )
        for outcome in result.steps
    ]
    return RunExecution(
        id=RunExecutionId.new(),
        run_id=run.id,
        tenant_id=run.tenant_id,
        status=ExecutionStatus(result.status),
        started_at=started_at,
        finished_at=datetime.now(UTC),
        error=result.error,
        steps=steps,
    )
