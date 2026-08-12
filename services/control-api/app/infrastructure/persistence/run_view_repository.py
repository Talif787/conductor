from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.projections.run_view import RunView, RunViewRepository
from app.infrastructure.persistence.models import RunViewModel


def _to_view(model: RunViewModel) -> RunView:
    return RunView(
        run_id=model.run_id,
        tenant_id=model.tenant_id,
        status=model.status,
        goal=model.goal,
        priority=model.priority,
        created_at=model.created_at,
        updated_at=model.updated_at,
        event_count=model.event_count,
    )


class SqlAlchemyRunViewRepository(RunViewRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, tenant_id: str, run_id: str) -> RunView | None:
        model = await self._session.get(RunViewModel, run_id)
        if model is None or model.tenant_id != tenant_id:
            return None
        return _to_view(model)

    async def upsert(self, view: RunView) -> None:
        model = await self._session.get(RunViewModel, view.run_id)
        if model is None:
            self._session.add(
                RunViewModel(
                    run_id=view.run_id,
                    tenant_id=view.tenant_id,
                    status=view.status,
                    goal=view.goal,
                    priority=view.priority,
                    created_at=view.created_at,
                    updated_at=view.updated_at,
                    event_count=view.event_count,
                )
            )
            return
        model.status = view.status
        model.goal = view.goal
        model.priority = view.priority
        model.updated_at = view.updated_at
        model.event_count = view.event_count

    async def list(self, tenant_id: str, limit: int) -> list[RunView]:
        stmt = (
            select(RunViewModel)
            .where(RunViewModel.tenant_id == tenant_id)
            .order_by(RunViewModel.updated_at.desc())
            .limit(limit)
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_to_view(m) for m in models]

    async def status_counts(self, tenant_id: str) -> dict[str, int]:
        stmt = (
            select(RunViewModel.status, func.count())
            .where(RunViewModel.tenant_id == tenant_id)
            .group_by(RunViewModel.status)
        )
        rows = (await self._session.execute(stmt)).all()
        return {status: int(count) for status, count in rows}
