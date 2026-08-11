from __future__ import annotations

from datetime import UTC, datetime

from app.application.execution.temporal_dtos import RunWorkflowResult, StepOutcome
from app.application.execution.temporal_mapping import to_run_execution, to_workflow_input
from app.domain.execution.value_objects import ExecutionStatus
from app.domain.run.entities import Run
from app.domain.run.value_objects import Goal
from app.domain.shared.identifiers import TenantId
from app.domain.workflows.value_objects import Step, WorkflowDefinition


def _run() -> Run:
    return Run.create(
        tenant_id=TenantId.new(),
        goal=Goal("get weather"),
        parameters={"city": "boston"},
        workflow_id="wf-1",
        workflow_version="1",
    )


def test_to_workflow_input_maps_run_and_steps() -> None:
    run = _run()
    definition = WorkflowDefinition(
        steps=(
            Step(step_id="fetch", name="fetch", tool_id="t1"),
            Step(step_id="label", name="label", tool_id="t2", depends_on=("fetch",)),
        )
    )
    request = to_workflow_input(run, definition)
    assert request.tenant_id == str(run.tenant_id)
    assert request.run_id == str(run.id)
    assert request.parameters == {"city": "boston"}
    assert [(s.step_id, s.tool_id, s.depends_on) for s in request.steps] == [
        ("fetch", "t1", []),
        ("label", "t2", ["fetch"]),
    ]


def test_to_run_execution_maps_status_output_times_and_ids() -> None:
    run = _run()
    started_at = datetime.now(UTC)
    result = RunWorkflowResult(
        status="succeeded",
        error=None,
        steps=[
            StepOutcome(
                step_id="fetch",
                tool_id="t1",
                position=0,
                status="succeeded",
                output={"text": "boston"},
                started_at="2026-08-11T00:00:00+00:00",
                finished_at="2026-08-11T00:00:01+00:00",
            ),
            StepOutcome(
                step_id="label",
                tool_id="t2",
                position=1,
                status="skipped",
                error="skipped after an upstream failure",
            ),
        ],
    )
    execution = to_run_execution(run, started_at, result)
    assert execution.status is ExecutionStatus.SUCCEEDED
    assert execution.run_id is run.id
    assert execution.tenant_id is run.tenant_id
    fetch = execution.steps[0]
    assert fetch.status is ExecutionStatus.SUCCEEDED
    assert fetch.output == {"text": "boston"}
    assert fetch.started_at is not None and fetch.finished_at is not None
    label = execution.steps[1]
    assert label.status is ExecutionStatus.SKIPPED
    assert label.started_at is None
