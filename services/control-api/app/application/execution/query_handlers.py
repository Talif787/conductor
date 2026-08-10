from __future__ import annotations

from collections.abc import Callable

from app.application.execution.dtos import RunExecutionDTO
from app.application.execution.mappers import to_execution_dto
from app.application.execution.queries import GetRunExecution
from app.application.ports import UnitOfWork
from app.domain.execution.errors import RunExecutionNotFoundError
from app.domain.run.value_objects import RunId, TenantId

UnitOfWorkFactory = Callable[[], UnitOfWork]


class GetRunExecutionHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, query: GetRunExecution) -> RunExecutionDTO:
        tenant_id = TenantId.parse(query.tenant_id)
        run_id = RunId.parse(query.run_id)
        async with self._uow_factory() as uow:
            execution = await uow.run_executions.get(tenant_id, run_id)
            if execution is None:
                raise RunExecutionNotFoundError(query.run_id)
            return to_execution_dto(execution)
