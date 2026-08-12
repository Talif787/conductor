from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.eventing.ports import OutboxRepository
from app.application.eventing.records import EventRecord
from app.infrastructure.persistence.models import RunEventModel


def _to_record(model: RunEventModel) -> EventRecord:
    return EventRecord(
        event_id=str(model.id),
        event_name=model.name,
        tenant_id=str(model.tenant_id),
        run_id=str(model.run_id),
        occurred_at=model.occurred_at,
        payload=dict(model.payload or {}),
    )


class SqlAlchemyOutboxRepository(OutboxRepository):
    """Reads and drains the run_events transactional outbox."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def fetch_unpublished(self, limit: int) -> list[EventRecord]:
        # FOR UPDATE SKIP LOCKED makes the drain safe: a row a relay is
        # processing is locked until that relay commits (marking it published),
        # so a second relay instance skips it rather than double-projecting it.
        stmt = (
            select(RunEventModel)
            .where(RunEventModel.published.is_(False))
            .order_by(RunEventModel.occurred_at, RunEventModel.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_to_record(m) for m in models]

    async def mark_published(self, event_ids: Sequence[str]) -> None:
        if not event_ids:
            return
        ids = [uuid.UUID(event_id) for event_id in event_ids]
        await self._session.execute(
            update(RunEventModel).where(RunEventModel.id.in_(ids)).values(published=True)
        )
