from __future__ import annotations

from app.application.execution.dtos import RunExecutionDTO, StepExecutionDTO
from app.domain.execution.entities import RunExecution, StepExecution


def _step_dto(step: StepExecution) -> StepExecutionDTO:
    return StepExecutionDTO(
        step_id=step.step_id,
        tool_id=step.tool_id,
        position=step.position,
        status=step.status.value,
        output=step.output,
        error=step.error,
        started_at=step.started_at.isoformat() if step.started_at else None,
        finished_at=step.finished_at.isoformat() if step.finished_at else None,
        cost_usd=step.cost_usd,
    )


def to_execution_dto(execution: RunExecution) -> RunExecutionDTO:
    return RunExecutionDTO(
        run_id=str(execution.run_id),
        status=execution.status.value,
        error=execution.error,
        started_at=execution.started_at.isoformat(),
        finished_at=execution.finished_at.isoformat() if execution.finished_at else None,
        total_cost_usd=execution.total_cost_usd,
        steps=[_step_dto(s) for s in sorted(execution.steps, key=lambda s: s.position)],
    )
