"""Entities for the Governance context."""

from __future__ import annotations

from datetime import UTC, datetime

from app.domain.governance.errors import InvalidApprovalStateError
from app.domain.governance.value_objects import ApprovalStatus
from app.domain.run.value_objects import RunId
from app.domain.shared.identifiers import ApprovalId, TenantId, UserId


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ApprovalRequest:
    """A human approval gate for a run parked by policy.

    Created PENDING when a policy decision requires approval; an authorized
    approver moves it to APPROVED or REJECTED exactly once.
    """

    def __init__(
        self,
        *,
        id: ApprovalId,
        tenant_id: TenantId,
        run_id: RunId,
        reason: str,
        status: ApprovalStatus,
        requested_at: datetime,
        decided_at: datetime | None = None,
        decided_by: UserId | None = None,
        decision_note: str | None = None,
    ) -> None:
        self.id = id
        self.tenant_id = tenant_id
        self.run_id = run_id
        self.reason = reason
        self.status = status
        self.requested_at = requested_at
        self.decided_at = decided_at
        self.decided_by = decided_by
        self.decision_note = decision_note

    @classmethod
    def open(cls, *, tenant_id: TenantId, run_id: RunId, reason: str) -> ApprovalRequest:
        return cls(
            id=ApprovalId.new(),
            tenant_id=tenant_id,
            run_id=run_id,
            reason=reason,
            status=ApprovalStatus.PENDING,
            requested_at=_utcnow(),
        )

    @property
    def is_pending(self) -> bool:
        return self.status is ApprovalStatus.PENDING

    def approve(self, *, decided_by: UserId, note: str | None = None) -> None:
        self._decide(ApprovalStatus.APPROVED, decided_by, note)

    def reject(self, *, decided_by: UserId, note: str | None = None) -> None:
        self._decide(ApprovalStatus.REJECTED, decided_by, note)

    def _decide(self, target: ApprovalStatus, decided_by: UserId, note: str | None) -> None:
        if not self.is_pending:
            raise InvalidApprovalStateError(f"approval request is already '{self.status.value}'")
        self.status = target
        self.decided_by = decided_by
        self.decision_note = note
        self.decided_at = _utcnow()
