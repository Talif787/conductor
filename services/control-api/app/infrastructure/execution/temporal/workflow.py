"""The durable run workflow: orchestrates the step DAG deterministically.

All ordering uses the pure planning helpers (list based, no set iteration), and
timestamps come from workflow.now(), so the workflow is replay safe. Side effects
happen only inside the run_tool activity.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.application.execution import planning
    from app.application.execution.temporal_dtos import (
        RunWorkflowInput,
        RunWorkflowResult,
        StepActivityInput,
        StepOutcome,
    )
    from app.infrastructure.execution.temporal.activities import ExecutionActivities

_SUCCEEDED = "succeeded"
_FAILED = "failed"
_SKIPPED = "skipped"


def _failure_message(exc: BaseException) -> str:
    cause = getattr(exc, "cause", None)
    message = getattr(cause, "message", None)
    return message or str(exc)


@workflow.defn
class ConductorRunWorkflow:
    @workflow.run
    async def run(self, request: RunWorkflowInput) -> RunWorkflowResult:
        deps = planning.dependency_map(request.steps)
        position = planning.positions(request.steps)
        tool_of = {step.step_id: step.tool_id for step in request.steps}
        statuses: dict[str, str] = {}
        outputs: dict[str, dict] = {}
        records: dict[str, StepOutcome] = {}
        remaining = [step.step_id for step in request.steps]

        timeout = timedelta(seconds=request.activity_timeout_seconds)
        retry = RetryPolicy(maximum_attempts=max(1, request.activity_max_attempts))

        while remaining:
            for sid in planning.steps_to_skip(remaining, deps, statuses):
                now = workflow.now().isoformat()
                statuses[sid] = _SKIPPED
                records[sid] = StepOutcome(
                    step_id=sid,
                    tool_id=tool_of[sid],
                    position=position[sid],
                    status=_SKIPPED,
                    error="skipped after an upstream failure",
                    started_at=now,
                    finished_at=now,
                )
            remaining = [sid for sid in remaining if sid not in records]
            if not remaining:
                break

            ready = planning.ready_steps(remaining, deps, statuses)
            if not ready:
                break

            results = await asyncio.gather(
                *(
                    workflow.execute_activity_method(
                        ExecutionActivities.run_tool,
                        StepActivityInput(
                            tenant_id=request.tenant_id,
                            tool_id=tool_of[sid],
                            step_id=sid,
                            parameters=request.parameters,
                            inputs={dep: outputs.get(dep, {}) for dep in deps[sid]},
                        ),
                        start_to_close_timeout=timeout,
                        retry_policy=retry,
                    )
                    for sid in ready
                ),
                return_exceptions=True,
            )
            for sid, result in zip(ready, results, strict=True):
                if isinstance(result, BaseException):
                    now = workflow.now().isoformat()
                    statuses[sid] = _FAILED
                    records[sid] = StepOutcome(
                        step_id=sid,
                        tool_id=tool_of[sid],
                        position=position[sid],
                        status=_FAILED,
                        error=_failure_message(result),
                        started_at=now,
                        finished_at=now,
                    )
                else:
                    statuses[sid] = _SUCCEEDED
                    outputs[sid] = result.output
                    records[sid] = StepOutcome(
                        step_id=sid,
                        tool_id=tool_of[sid],
                        position=position[sid],
                        status=_SUCCEEDED,
                        output=result.output,
                        started_at=result.started_at,
                        finished_at=result.finished_at,
                    )
            remaining = [sid for sid in remaining if sid not in records]

        ordered = [records[step.step_id] for step in request.steps if step.step_id in records]
        overall, error = planning.summarize_outcomes(
            [(outcome.step_id, outcome.status, outcome.error) for outcome in ordered]
        )
        return RunWorkflowResult(status=overall, error=error, steps=ordered)
