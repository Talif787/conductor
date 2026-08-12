"""Unit tests for the run_view read-model projector."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.application.eventing.records import EventRecord
from app.application.projections.run_view import RunView, RunViewProjector, RunViewRepository

_BASE = datetime(2026, 8, 11, tzinfo=UTC)


class _FakeViews(RunViewRepository):
    def __init__(self) -> None:
        self.store: dict[str, RunView] = {}

    async def get(self, tenant_id: str, run_id: str) -> RunView | None:
        view = self.store.get(run_id)
        return view if view is not None and view.tenant_id == tenant_id else None

    async def upsert(self, view: RunView) -> None:
        self.store[view.run_id] = view

    async def list(self, tenant_id: str, limit: int) -> list[RunView]:
        return [v for v in self.store.values() if v.tenant_id == tenant_id][:limit]

    async def status_counts(self, tenant_id: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for view in self.store.values():
            if view.tenant_id == tenant_id:
                counts[view.status] = counts.get(view.status, 0) + 1
        return counts


def _record(name: str, run_id: str, offset: int, **payload: object) -> EventRecord:
    return EventRecord(
        event_id=f"{name}:{run_id}",
        event_name=name,
        tenant_id="ten",
        run_id=run_id,
        occurred_at=_BASE + timedelta(seconds=offset),
        payload=dict(payload),
    )


async def test_projects_full_lifecycle() -> None:
    projector = RunViewProjector()
    views = _FakeViews()
    for event in [
        _record("RunCreated", "r1", 0, goal="summarize", priority="high"),
        _record("RunPlanningStarted", "r1", 1),
        _record("RunRunningStarted", "r1", 2),
        _record("RunCompleted", "r1", 3),
    ]:
        await projector.apply(views, event)
    view = await views.get("ten", "r1")
    assert view is not None
    assert view.status == "completed"
    assert view.goal == "summarize"
    assert view.priority == "high"
    assert view.event_count == 4
    assert view.created_at == _BASE
    assert view.updated_at == _BASE + timedelta(seconds=3)


async def test_projects_approval_rejection() -> None:
    projector = RunViewProjector()
    views = _FakeViews()
    for event in [
        _record("RunCreated", "r2", 0, goal="deploy", priority="high"),
        _record("RunAwaitingApproval", "r2", 1, reason="high priority"),
        _record("RunFailed", "r2", 2, reason="approval rejected"),
    ]:
        await projector.apply(views, event)
    view = await views.get("ten", "r2")
    assert view is not None
    assert view.status == "failed"
    assert view.event_count == 3


async def test_status_event_before_create_synthesizes_row() -> None:
    projector = RunViewProjector()
    views = _FakeViews()
    await projector.apply(views, _record("RunRunningStarted", "r3", 0))
    view = await views.get("ten", "r3")
    assert view is not None
    assert view.status == "running"


async def test_unknown_event_is_ignored() -> None:
    projector = RunViewProjector()
    views = _FakeViews()
    await projector.apply(views, _record("SomethingElse", "r4", 0))
    assert await views.get("ten", "r4") is None


async def test_status_counts_across_runs() -> None:
    projector = RunViewProjector()
    views = _FakeViews()
    await projector.apply(views, _record("RunCreated", "a", 0, goal="g", priority="low"))
    await projector.apply(views, _record("RunCompleted", "a", 1))
    await projector.apply(views, _record("RunCreated", "b", 0, goal="g", priority="low"))
    counts = await views.status_counts("ten")
    assert counts == {"completed": 1, "queued": 1}
