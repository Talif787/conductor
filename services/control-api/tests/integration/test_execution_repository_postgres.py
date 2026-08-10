"""Postgres-backed execution persistence tests.

Run with a live database:  make test-integration
These verify that a run execution and its step rows round-trip through the
run_executions and run_step_executions tables, including JSONB step output.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config.settings import get_settings
from app.domain.execution.entities import RunExecution, StepExecution
from app.domain.execution.value_objects import ExecutionStatus
from app.domain.run.entities import Run
from app.domain.run.value_objects import Goal
from app.domain.shared.identifiers import (
    RunExecutionId,
    StepExecutionId,
    TenantId,
)
from app.infrastructure.persistence.execution_repository import (
    SqlAlchemyRunExecutionRepository,
)
from app.infrastructure.persistence.models import RunModel
from app.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.integration


@pytest.fixture
async def session_factory():
    engine = create_async_engine(get_settings().database.url, future=True)
    try:
        async with engine.connect():
            pass
    except Exception:  # noqa: BLE001
        await engine.dispose()
        pytest.skip("PostgreSQL is not available")
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


@pytest.mark.asyncio
async def test_execution_round_trips_through_postgres(session_factory) -> None:
    tenant = TenantId.new()
    run = Run.create(tenant_id=tenant, goal=Goal("integration goal"), parameters={})
    now = datetime.now(UTC)
    execution = RunExecution(
        id=RunExecutionId.new(),
        run_id=run.id,
        tenant_id=tenant,
        status=ExecutionStatus.SUCCEEDED,
        started_at=now,
        finished_at=now,
        steps=[
            StepExecution(
                id=StepExecutionId.new(),
                step_id="only",
                tool_id="t1",
                position=0,
                status=ExecutionStatus.SUCCEEDED,
                output={"text": "OK"},
                started_at=now,
                finished_at=now,
            )
        ],
    )

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        await uow.runs.add(run, [])
        await uow.run_executions.add(execution)
        await uow.commit()

    async with session_factory() as session:
        loaded = await SqlAlchemyRunExecutionRepository(session).get(tenant, run.id)

    assert loaded is not None
    assert loaded.status is ExecutionStatus.SUCCEEDED
    assert len(loaded.steps) == 1
    assert loaded.steps[0].step_id == "only"
    assert loaded.steps[0].output == {"text": "OK"}

    # Deleting the run cascades to run_executions and run_step_executions.
    async with session_factory() as session:
        await session.execute(delete(RunModel).where(RunModel.id == run.id.value))
        await session.commit()
