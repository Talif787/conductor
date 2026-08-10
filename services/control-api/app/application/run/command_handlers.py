"""Command handlers implementing the write side of the Run context."""

from __future__ import annotations

from collections.abc import Callable

import structlog

from app.application.ports import EventPublisher, UnitOfWork
from app.application.run.commands import CancelRun, CreateRun
from app.application.run.dtos import RunDTO
from app.application.run.mappers import to_run_dto
from app.domain.run.entities import Run
from app.domain.run.errors import RunNotFoundError
from app.domain.run.value_objects import Goal, Priority, RunId, TenantId
from app.domain.shared.identifiers import WorkflowId
from app.domain.workflows.errors import (
    WorkflowNotPublishedError,
    WorkflowVersionNotFoundError,
)

logger = structlog.get_logger(__name__)

UnitOfWorkFactory = Callable[[], UnitOfWork]


class CreateRunHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory, publisher: EventPublisher) -> None:
        self._uow_factory = uow_factory
        self._publisher = publisher

    async def handle(self, command: CreateRun) -> RunDTO:
        tenant_id = TenantId.parse(command.tenant_id)
        goal = Goal(command.goal)
        priority = Priority(command.priority)

        async with self._uow_factory() as uow:
            if command.idempotency_key is not None:
                existing = await uow.runs.find_by_idempotency_key(
                    tenant_id, command.idempotency_key
                )
                if existing is not None:
                    logger.info(
                        "run.create.idempotent_hit",
                        run_id=str(existing.id),
                        idempotency_key=command.idempotency_key,
                    )
                    return to_run_dto(existing)

            if command.workflow_id is not None:
                await self._assert_published_workflow(
                    uow, tenant_id, command.workflow_id, command.workflow_version
                )

            run = Run.create(
                tenant_id=tenant_id,
                goal=goal,
                priority=priority,
                parameters=command.parameters,
                workflow_id=command.workflow_id,
                workflow_version=command.workflow_version,
                idempotency_key=command.idempotency_key,
            )
            events = run.pull_events()
            await uow.runs.add(run, events)
            await uow.commit()

        await self._publisher.publish(events)
        logger.info("run.created", run_id=str(run.id), tenant_id=str(tenant_id))
        return to_run_dto(run)

    @staticmethod
    async def _assert_published_workflow(
        uow: UnitOfWork,
        tenant_id: TenantId,
        workflow_id_raw: str,
        version_raw: str | None,
    ) -> None:
        workflow_id = WorkflowId.parse(workflow_id_raw)
        if version_raw is None:
            raise WorkflowVersionNotFoundError(workflow_id_raw, "unspecified")
        try:
            version_num = int(version_raw)
        except (TypeError, ValueError):
            raise WorkflowVersionNotFoundError(workflow_id_raw, version_raw) from None
        version = await uow.workflow_versions.get(tenant_id, workflow_id, version_num)
        if version is None:
            raise WorkflowVersionNotFoundError(workflow_id_raw, version_raw)
        if not version.is_published:
            raise WorkflowNotPublishedError(workflow_id_raw, version_raw)


class CancelRunHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory, publisher: EventPublisher) -> None:
        self._uow_factory = uow_factory
        self._publisher = publisher

    async def handle(self, command: CancelRun) -> RunDTO:
        tenant_id = TenantId.parse(command.tenant_id)
        run_id = RunId.parse(command.run_id)

        async with self._uow_factory() as uow:
            run = await uow.runs.get(tenant_id, run_id)
            if run is None:
                raise RunNotFoundError(str(run_id))
            run.cancel()
            events = run.pull_events()
            await uow.runs.save(run, events)
            await uow.commit()

        await self._publisher.publish(events)
        logger.info("run.cancelled", run_id=str(run.id), tenant_id=str(tenant_id))
        return to_run_dto(run)
