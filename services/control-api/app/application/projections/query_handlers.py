from __future__ import annotations

from collections.abc import Callable

from app.application.ports import UnitOfWork
from app.application.projections.dtos import RunStatsDTO, RunViewDTO
from app.application.projections.queries import GetRunStats, ListRunViews
from app.application.projections.run_view import RunView

UnitOfWorkFactory = Callable[[], UnitOfWork]

_TERMINAL = frozenset({"completed", "failed", "cancelled"})


def _to_dto(view: RunView) -> RunViewDTO:
    return RunViewDTO(
        run_id=view.run_id,
        tenant_id=view.tenant_id,
        status=view.status,
        goal=view.goal,
        priority=view.priority,
        created_at=view.created_at.isoformat(),
        updated_at=view.updated_at.isoformat(),
        event_count=view.event_count,
    )


class GetRunStatsHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, query: GetRunStats) -> RunStatsDTO:
        async with self._uow_factory() as uow:
            counts = await uow.run_view.status_counts(query.tenant_id)
        total = sum(counts.values())
        active = sum(n for status, n in counts.items() if status not in _TERMINAL)
        return RunStatsDTO(total=total, active=active, by_status=dict(counts))


class ListRunViewsHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, query: ListRunViews) -> list[RunViewDTO]:
        async with self._uow_factory() as uow:
            views = await uow.run_view.list(query.tenant_id, query.limit)
        return [_to_dto(v) for v in views]
