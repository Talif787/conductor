"""Repository port for the Governance context."""

from __future__ import annotations

import abc

from app.domain.governance.entities import ApprovalRequest
from app.domain.governance.value_objects import ApprovalStatus
from app.domain.run.value_objects import RunId
from app.domain.shared.identifiers import ApprovalId, TenantId


class ApprovalRepository(abc.ABC):
    @abc.abstractmethod
    async def add(self, approval: ApprovalRequest) -> None: ...

    @abc.abstractmethod
    async def save(self, approval: ApprovalRequest) -> None: ...

    @abc.abstractmethod
    async def get(self, tenant_id: TenantId, approval_id: ApprovalId) -> ApprovalRequest | None: ...

    @abc.abstractmethod
    async def get_for_run(self, tenant_id: TenantId, run_id: RunId) -> ApprovalRequest | None: ...

    @abc.abstractmethod
    async def list(
        self, tenant_id: TenantId, status: ApprovalStatus | None = None
    ) -> list[ApprovalRequest]: ...
