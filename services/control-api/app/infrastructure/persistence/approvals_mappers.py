from __future__ import annotations

from app.domain.governance.entities import ApprovalRequest
from app.domain.governance.value_objects import ApprovalStatus
from app.domain.run.value_objects import RunId
from app.domain.shared.identifiers import ApprovalId, TenantId, UserId
from app.infrastructure.persistence.models import ApprovalRequestModel


def approval_to_model(approval: ApprovalRequest) -> ApprovalRequestModel:
    return ApprovalRequestModel(
        id=approval.id.value,
        tenant_id=approval.tenant_id.value,
        run_id=approval.run_id.value,
        reason=approval.reason,
        status=approval.status.value,
        requested_at=approval.requested_at,
        decided_at=approval.decided_at,
        decided_by=approval.decided_by.value if approval.decided_by else None,
        decision_note=approval.decision_note,
    )


def apply_to_model(approval: ApprovalRequest, model: ApprovalRequestModel) -> None:
    model.status = approval.status.value
    model.decided_at = approval.decided_at
    model.decided_by = approval.decided_by.value if approval.decided_by else None
    model.decision_note = approval.decision_note


def model_to_approval(model: ApprovalRequestModel) -> ApprovalRequest:
    return ApprovalRequest(
        id=ApprovalId(model.id),
        tenant_id=TenantId(model.tenant_id),
        run_id=RunId(model.run_id),
        reason=model.reason,
        status=ApprovalStatus(model.status),
        requested_at=model.requested_at,
        decided_at=model.decided_at,
        decided_by=UserId(model.decided_by) if model.decided_by else None,
        decision_note=model.decision_note,
    )
