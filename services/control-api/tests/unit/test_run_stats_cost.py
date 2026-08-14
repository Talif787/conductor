"""Unit tests for the tenant cost rollup in run stats."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.application.projections.queries import GetRunStats
from app.application.projections.query_handlers import GetRunStatsHandler
from app.domain.execution.entities import RunExecution
from app.domain.run.value_objects import RunId
from app.domain.shared.identifiers import RunExecutionId, TenantId
from app.infrastructure.persistence.in_memory import InMemoryDatabase, InMemoryUnitOfWork


@pytest.fixture
def uow_factory():
    db = InMemoryDatabase()
    return lambda: InMemoryUnitOfWork(db)


def _exec(tenant: TenantId, cost: float) -> RunExecution:
    return RunExecution(
        id=RunExecutionId.new(),
        run_id=RunId.new(),
        tenant_id=tenant,
        status="succeeded",
        started_at=datetime.now(UTC),
        total_cost_usd=cost,
    )


async def _seed(uow_factory, tenant: TenantId, other: TenantId) -> None:
    async with uow_factory() as uow:
        await uow.run_executions.add(_exec(tenant, 0.000003))
        await uow.run_executions.add(_exec(tenant, 0.000007))
        await uow.run_executions.add(_exec(other, 0.5))  # different tenant
        await uow.commit()


async def test_total_cost_sums_tenant_executions(uow_factory) -> None:
    tenant, other = TenantId.new(), TenantId.new()
    await _seed(uow_factory, tenant, other)
    stats = await GetRunStatsHandler(uow_factory).handle(GetRunStats(tenant_id=str(tenant)))
    assert stats.total_cost_usd == pytest.approx(0.00001)


async def test_total_cost_is_tenant_scoped(uow_factory) -> None:
    tenant, other = TenantId.new(), TenantId.new()
    await _seed(uow_factory, tenant, other)
    stats = await GetRunStatsHandler(uow_factory).handle(GetRunStats(tenant_id=str(other)))
    assert stats.total_cost_usd == pytest.approx(0.5)


async def test_total_cost_zero_when_no_executions(uow_factory) -> None:
    tenant = TenantId.new()
    stats = await GetRunStatsHandler(uow_factory).handle(GetRunStats(tenant_id=str(tenant)))
    assert stats.total_cost_usd == 0.0
