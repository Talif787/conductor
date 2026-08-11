from __future__ import annotations

from collections.abc import Callable

from app.application.governance.dtos import ApprovalDTO
from app.application.governance.mappers import to_approval_dto
from app.application.governance.queries import GetApproval, ListApprovals
from app.application.ports import UnitOfWork
from app.domain.governance.errors import ApprovalNotFoundError
from app.domain.governance.value_objects import ApprovalStatus
from app.domain.shared.identifiers import ApprovalId, TenantId

UnitOfWorkFactory = Callable[[], UnitOfWork]


class GetApprovalHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, query: GetApproval) -> ApprovalDTO:
        tenant_id = TenantId.parse(query.tenant_id)
        approval_id = ApprovalId.parse(query.approval_id)
        async with self._uow_factory() as uow:
            approval = await uow.approvals.get(tenant_id, approval_id)
            if approval is None:
                raise ApprovalNotFoundError(query.approval_id)
            return to_approval_dto(approval)


class ListApprovalsHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, query: ListApprovals) -> list[ApprovalDTO]:
        tenant_id = TenantId.parse(query.tenant_id)
        status = ApprovalStatus(query.status) if query.status else None
        async with self._uow_factory() as uow:
            approvals = await uow.approvals.list(tenant_id, status)
            return [to_approval_dto(a) for a in approvals]
