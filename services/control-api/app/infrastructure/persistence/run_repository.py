"""PostgreSQL-backed implementation of the RunRepository port."""
from __future__ import annotations

import base64
import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Select, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.run.entities import Run
from app.domain.run.events import DomainEvent
from app.domain.run.repository import Page, PagedRuns, RunFilter, RunRepository
from app.domain.run.value_objects import RunId, TenantId
from app.infrastructure.persistence.mappers import event_to_model, model_to_run, run_to_model
from app.infrastructure.persistence.models import RunModel

_CURSOR_SEPARATOR = "|"


def _encode_cursor(created_at: datetime, run_id: str) -> str:
    raw = f"{created_at.isoformat()}{_CURSOR_SEPARATOR}{run_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    created_at_str, run_id = raw.split(_CURSOR_SEPARATOR, 1)
    return datetime.fromisoformat(created_at_str), uuid.UUID(run_id)


class SqlAlchemyRunRepository(RunRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, run: Run, events: Sequence[DomainEvent]) -> None:
        self._session.add(run_to_model(run))
        # Flush so the parent runs row is inserted before its run_events children.
        # These models share a table-level foreign key but no ORM relationship, so the
        # unit of work will not order the two inserts on its own. This stays inside the
        # transaction: the commit still happens later in the unit of work.
        await self._session.flush()
        for event in events:
            self._session.add(event_to_model(event))

    async def save(self, run: Run, events: Sequence[DomainEvent]) -> None:
        await self._session.execute(
            update(RunModel)
            .where(RunModel.id == run.id.value, RunModel.tenant_id == run.tenant_id.value)
            .values(status=run.status.value, error=run.error, updated_at=run.updated_at)
        )
        for event in events:
            self._session.add(event_to_model(event))

    async def get(self, tenant_id: TenantId, run_id: RunId) -> Run | None:
        stmt = select(RunModel).where(
            RunModel.id == run_id.value, RunModel.tenant_id == tenant_id.value
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return model_to_run(model) if model is not None else None

    async def find_by_idempotency_key(
        self, tenant_id: TenantId, idempotency_key: str
    ) -> Run | None:
        stmt = select(RunModel).where(
            RunModel.tenant_id == tenant_id.value,
            RunModel.idempotency_key == idempotency_key,
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return model_to_run(model) if model is not None else None

    async def list(self, tenant_id: TenantId, run_filter: RunFilter, page: Page) -> PagedRuns:
        stmt: Select[tuple[RunModel]] = select(RunModel).where(
            RunModel.tenant_id == tenant_id.value
        )
        if run_filter.status is not None:
            stmt = stmt.where(RunModel.status == run_filter.status.value)
        if page.cursor is not None:
            cursor_created_at, cursor_run_id = _decode_cursor(page.cursor)
            stmt = stmt.where(
                tuple_(RunModel.created_at, RunModel.id)
                < (cursor_created_at, cursor_run_id)
            )
        stmt = stmt.order_by(RunModel.created_at.desc(), RunModel.id.desc()).limit(page.limit + 1)

        models = list((await self._session.execute(stmt)).scalars().all())
        next_cursor: str | None = None
        if len(models) > page.limit:
            last = models[page.limit - 1]
            next_cursor = _encode_cursor(last.created_at, str(last.id))
            models = models[: page.limit]
        return PagedRuns(runs=[model_to_run(m) for m in models], next_cursor=next_cursor)
