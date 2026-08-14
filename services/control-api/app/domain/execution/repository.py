"""Repository port for run executions."""

from __future__ import annotations

import abc

from app.domain.execution.entities import RunExecution
from app.domain.run.value_objects import RunId
from app.domain.shared.identifiers import TenantId


class RunExecutionRepository(abc.ABC):
    @abc.abstractmethod
    async def add(self, execution: RunExecution) -> None: ...

    @abc.abstractmethod
    async def get(self, tenant_id: TenantId, run_id: RunId) -> RunExecution | None: ...

    @abc.abstractmethod
    async def total_cost(self, tenant_id: TenantId) -> float: ...
