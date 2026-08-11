from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.governance.entities import ApprovalRequest
from app.domain.governance.repository import ApprovalRepository
from app.domain.governance.value_objects import ApprovalStatus
from app.domain.run.value_objects import RunId
from app.domain.shared.identifiers import ApprovalId, TenantId
from app.infrastructure.persistence.approvals_mappers import (
    apply_to_model,
    approval_to_model,
    model_to_approval,
)
from app.infrastructure.persistence.models import ApprovalRequestModel


class SqlAlchemyApprovalRepository(ApprovalRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, approval: ApprovalRequest) -> None:
        self._session.add(approval_to_model(approval))

    async def save(self, approval: ApprovalRequest) -> None:
        model = await self._session.get(ApprovalRequestModel, approval.id.value)
        if model is None:
            self._session.add(approval_to_model(approval))
            return
        apply_to_model(approval, model)

    async def get(self, tenant_id: TenantId, approval_id: ApprovalId) -> ApprovalRequest | None:
        model = await self._session.get(ApprovalRequestModel, approval_id.value)
        if model is None or model.tenant_id != tenant_id.value:
            return None
        return model_to_approval(model)

    async def get_for_run(self, tenant_id: TenantId, run_id: RunId) -> ApprovalRequest | None:
        stmt = (
            select(ApprovalRequestModel)
            .where(
                ApprovalRequestModel.tenant_id == tenant_id.value,
                ApprovalRequestModel.run_id == run_id.value,
            )
            .order_by(ApprovalRequestModel.requested_at.desc())
        )
        models = (await self._session.execute(stmt)).scalars().all()
        pending = [m for m in models if m.status == ApprovalStatus.PENDING.value]
        chosen = pending[0] if pending else (models[0] if models else None)
        return model_to_approval(chosen) if chosen is not None else None

    async def list(
        self, tenant_id: TenantId, status: ApprovalStatus | None = None
    ) -> list[ApprovalRequest]:
        stmt = select(ApprovalRequestModel).where(ApprovalRequestModel.tenant_id == tenant_id.value)
        if status is not None:
            stmt = stmt.where(ApprovalRequestModel.status == status.value)
        stmt = stmt.order_by(ApprovalRequestModel.requested_at.desc())
        models = (await self._session.execute(stmt)).scalars().all()
        return [model_to_approval(m) for m in models]
