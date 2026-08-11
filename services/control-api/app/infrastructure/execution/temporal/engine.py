"""TemporalExecutionEngine: runs a workflow's DAG as a durable Temporal workflow.

Implements the same ExecutionEngine port as the local engine. The heavy lifting
is delegated: ordering to the workflow, tool execution to the activity, and the
domain mapping to temporal_mapping. This adapter just connects, starts the
workflow, waits for the result, and maps it back to a RunExecution.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.application.execution.ports import ExecutionEngine
from app.application.execution.temporal_mapping import to_run_execution, to_workflow_input
from app.config.settings import TemporalSettings
from app.domain.execution.entities import RunExecution
from app.domain.run.entities import Run
from app.domain.tools.entities import Tool
from app.domain.workflows.value_objects import WorkflowDefinition


class TemporalExecutionEngine(ExecutionEngine):
    def __init__(self, settings: TemporalSettings) -> None:
        self._settings = settings

    async def execute(
        self,
        run: Run,
        definition: WorkflowDefinition,
        tools: dict[str, Tool],
    ) -> RunExecution:
        # tools are loaded from the repository inside the activity, so the map is
        # not needed here; the parameter is kept to satisfy the engine port.
        from temporalio.client import Client

        from app.infrastructure.execution.temporal.workflow import ConductorRunWorkflow

        started_at = datetime.now(UTC)
        request = to_workflow_input(run, definition)
        request.activity_timeout_seconds = self._settings.activity_start_to_close_timeout_seconds
        request.activity_max_attempts = self._settings.activity_max_attempts

        client = await Client.connect(self._settings.host, namespace=self._settings.namespace)
        result = await client.execute_workflow(
            ConductorRunWorkflow.run,
            request,
            id=f"conductor-run-{run.id}",
            task_queue=self._settings.task_queue,
            execution_timeout=timedelta(seconds=self._settings.workflow_execution_timeout_seconds),
        )
        return to_run_execution(run, started_at, result)
