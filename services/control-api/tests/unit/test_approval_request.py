from __future__ import annotations

import pytest

from app.domain.governance.entities import ApprovalRequest
from app.domain.governance.errors import InvalidApprovalStateError
from app.domain.governance.value_objects import ApprovalStatus
from app.domain.run.value_objects import RunId
from app.domain.shared.identifiers import TenantId, UserId


def _open() -> ApprovalRequest:
    return ApprovalRequest.open(
        tenant_id=TenantId.new(), run_id=RunId.new(), reason="high priority"
    )


def test_open_starts_pending() -> None:
    approval = _open()
    assert approval.is_pending
    assert approval.status is ApprovalStatus.PENDING


def test_approve_records_decider() -> None:
    approval = _open()
    user = UserId.new()
    approval.approve(decided_by=user, note="looks good")
    assert approval.status is ApprovalStatus.APPROVED
    assert approval.decided_by is user
    assert approval.decision_note == "looks good"
    assert approval.decided_at is not None


def test_reject_transitions_to_rejected() -> None:
    approval = _open()
    approval.reject(decided_by=UserId.new(), note="not now")
    assert approval.status is ApprovalStatus.REJECTED


def test_cannot_decide_twice() -> None:
    approval = _open()
    approval.approve(decided_by=UserId.new())
    with pytest.raises(InvalidApprovalStateError):
        approval.approve(decided_by=UserId.new())
    with pytest.raises(InvalidApprovalStateError):
        approval.reject(decided_by=UserId.new())
