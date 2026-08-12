from __future__ import annotations

from app.domain.execution.entities import RunExecution, StepExecution
from app.domain.execution.value_objects import ExecutionStatus
from app.domain.run.value_objects import RunId
from app.domain.shared.identifiers import RunExecutionId, StepExecutionId, TenantId
from app.infrastructure.persistence.models import RunExecutionModel, StepExecutionModel


def execution_to_models(
    execution: RunExecution,
) -> tuple[RunExecutionModel, list[StepExecutionModel]]:
    parent = RunExecutionModel(
        id=execution.id.value,
        run_id=execution.run_id.value,
        tenant_id=execution.tenant_id.value,
        status=execution.status.value,
        error=execution.error,
        started_at=execution.started_at,
        finished_at=execution.finished_at,
        total_cost_usd=execution.total_cost_usd,
    )
    children = [
        StepExecutionModel(
            id=step.id.value,
            run_execution_id=execution.id.value,
            step_id=step.step_id,
            tool_id=step.tool_id,
            position=step.position,
            status=step.status.value,
            output=step.output,
            error=step.error,
            started_at=step.started_at,
            finished_at=step.finished_at,
            cost_usd=step.cost_usd,
        )
        for step in execution.steps
    ]
    return parent, children


def models_to_execution(parent: RunExecutionModel, steps: list[StepExecutionModel]) -> RunExecution:
    return RunExecution(
        id=RunExecutionId(parent.id),
        run_id=RunId(parent.run_id),
        tenant_id=TenantId(parent.tenant_id),
        status=ExecutionStatus(parent.status),
        started_at=parent.started_at,
        finished_at=parent.finished_at,
        error=parent.error,
        total_cost_usd=parent.total_cost_usd,
        steps=[
            StepExecution(
                id=StepExecutionId(row.id),
                step_id=row.step_id,
                tool_id=row.tool_id,
                position=row.position,
                status=ExecutionStatus(row.status),
                output=row.output,
                error=row.error,
                started_at=row.started_at,
                finished_at=row.finished_at,
                cost_usd=row.cost_usd,
            )
            for row in sorted(steps, key=lambda r: r.position)
        ],
    )
