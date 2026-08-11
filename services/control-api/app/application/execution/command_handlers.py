from __future__ import annotations

from collections.abc import Callable

import structlog

from app.application.execution.commands import ExecuteRun
from app.application.execution.dtos import RunExecutionDTO
from app.application.execution.mappers import to_execution_dto
from app.application.execution.ports import ExecutionEngine
from app.application.ports import EventPublisher, UnitOfWork
from app.domain.execution.errors import RunNotExecutableError
from app.domain.run.errors import RunNotFoundError
from app.domain.run.value_objects import RunId, RunStatus, TenantId
from app.domain.shared.identifiers import WorkflowId
from app.domain.workflows.errors import (
    WorkflowNotPublishedError,
    WorkflowVersionNotFoundError,
)

logger = structlog.get_logger(__name__)

UnitOfWorkFactory = Callable[[], UnitOfWork]


class ExecuteRunHandler:
    """Drive a queued run through the execution engine to a terminal state."""

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        engine: ExecutionEngine,
        publisher: EventPublisher,
    ) -> None:
        self._uow_factory = uow_factory
        self._engine = engine
        self._publisher = publisher

    async def handle(self, command: ExecuteRun) -> RunExecutionDTO:
        tenant_id = TenantId.parse(command.tenant_id)
        run_id = RunId.parse(command.run_id)

        # Phase 1: load, validate, and move the run into RUNNING before any work.
        async with self._uow_factory() as uow:
            run = await uow.runs.get(tenant_id, run_id)
            if run is None:
                raise RunNotFoundError(command.run_id)
            if run.status not in (RunStatus.QUEUED, RunStatus.AWAITING_APPROVAL):
                raise RunNotExecutableError(
                    f"run is '{run.status.value}'; only queued or approved runs can be executed"
                )
            if run.workflow_id is None:
                raise RunNotExecutableError("run has no workflow to execute")

            version = await uow.workflow_versions.get(
                tenant_id, WorkflowId.parse(run.workflow_id), int(run.workflow_version or 0)
            )
            if version is None:
                raise WorkflowVersionNotFoundError(run.workflow_id, run.workflow_version or "?")
            if not version.is_published:
                raise WorkflowNotPublishedError(run.workflow_id, run.workflow_version or "?")

            definition = version.definition
            tools = {str(tool.id): tool for tool in await uow.tools.list(tenant_id)}

            run.start_planning()
            run.start_running()
            events = run.pull_events()
            await uow.runs.save(run, events)
            await uow.commit()
        await self._publisher.publish(events)

        # Phase 2: run the DAG outside any open transaction.
        try:
            execution = await self._engine.execute(run, definition, tools)
        except Exception as exc:  # noqa: BLE001
            logger.exception("run.execution_crashed", run_id=str(run_id))
            async with self._uow_factory() as uow:
                current = await uow.runs.get(tenant_id, run_id)
                if current is not None and current.status is RunStatus.RUNNING:
                    current.fail(f"execution error: {exc}")
                    failure_events = current.pull_events()
                    await uow.runs.save(current, failure_events)
                    await uow.commit()
                    await self._publisher.publish(failure_events)
            raise

        # Phase 3: persist results and finalize the run status.
        async with self._uow_factory() as uow:
            current = await uow.runs.get(tenant_id, run_id)
            await uow.run_executions.add(execution)
            if current is not None:
                if execution.succeeded:
                    current.complete()
                else:
                    current.fail(execution.error or "one or more steps failed")
                events = current.pull_events()
                await uow.runs.save(current, events)
            await uow.commit()
        await self._publisher.publish(events)
        logger.info("run.executed", run_id=str(run_id), status=execution.status.value)
        return to_execution_dto(execution)
