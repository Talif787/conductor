"""Query handlers implementing the read side of the Run context."""

from __future__ import annotations

from collections.abc import Callable

from app.application.ports import UnitOfWork
from app.application.run.dtos import PagedRunsDTO, RunDTO
from app.application.run.mappers import to_run_dto, to_run_summary_dto
from app.application.run.queries import GetRun, ListRuns
from app.domain.run.errors import RunNotFoundError
from app.domain.run.repository import Page, RunFilter
from app.domain.run.value_objects import RunId, RunStatus, TenantId

UnitOfWorkFactory = Callable[[], UnitOfWork]


class GetRunHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, query: GetRun) -> RunDTO:
        tenant_id = TenantId.parse(query.tenant_id)
        run_id = RunId.parse(query.run_id)
        async with self._uow_factory() as uow:
            run = await uow.runs.get(tenant_id, run_id)
        if run is None:
            raise RunNotFoundError(str(run_id))
        return to_run_dto(run)


class ListRunsHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, query: ListRuns) -> PagedRunsDTO:
        tenant_id = TenantId.parse(query.tenant_id)
        status = RunStatus(query.status) if query.status is not None else None
        page = Page(limit=query.limit, cursor=query.cursor)
        async with self._uow_factory() as uow:
            result = await uow.runs.list(tenant_id, RunFilter(status=status), page)
        return PagedRunsDTO(
            items=[to_run_summary_dto(run) for run in result.runs],
            next_cursor=result.next_cursor,
        )
