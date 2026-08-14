from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.execution.entities import RunExecution
from app.domain.execution.repository import RunExecutionRepository
from app.domain.run.value_objects import RunId
from app.domain.shared.identifiers import TenantId
from app.infrastructure.persistence.execution_mappers import (
    execution_to_models,
    models_to_execution,
)
from app.infrastructure.persistence.models import RunExecutionModel, StepExecutionModel


class SqlAlchemyRunExecutionRepository(RunExecutionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, execution: RunExecution) -> None:
        parent, children = execution_to_models(execution)
        self._session.add(parent)
        self._session.add_all(children)

    async def get(self, tenant_id: TenantId, run_id: RunId) -> RunExecution | None:
        stmt = (
            select(RunExecutionModel)
            .where(
                RunExecutionModel.run_id == run_id.value,
                RunExecutionModel.tenant_id == tenant_id.value,
            )
            .order_by(RunExecutionModel.started_at.desc())
            .limit(1)
        )
        parent = (await self._session.execute(stmt)).scalar_one_or_none()
        if parent is None:
            return None
        steps_stmt = select(StepExecutionModel).where(
            StepExecutionModel.run_execution_id == parent.id
        )
        steps = list((await self._session.execute(steps_stmt)).scalars().all())
        return models_to_execution(parent, steps)

    async def total_cost(self, tenant_id: TenantId) -> float:
        stmt = select(func.coalesce(func.sum(RunExecutionModel.total_cost_usd), 0.0)).where(
            RunExecutionModel.tenant_id == tenant_id.value
        )
        return float((await self._session.execute(stmt)).scalar_one())
