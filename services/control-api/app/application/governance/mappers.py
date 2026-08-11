from __future__ import annotations

from collections.abc import Sequence

from app.application.governance.dtos import ApprovalDTO
from app.application.governance.policy import PolicyQuery, PolicyToolRef
from app.domain.governance.entities import ApprovalRequest
from app.domain.run.entities import Run
from app.domain.tools.entities import Tool


def to_approval_dto(approval: ApprovalRequest) -> ApprovalDTO:
    return ApprovalDTO(
        id=str(approval.id),
        run_id=str(approval.run_id),
        reason=approval.reason,
        status=approval.status.value,
        requested_at=approval.requested_at.isoformat(),
        decided_at=approval.decided_at.isoformat() if approval.decided_at else None,
        decided_by=str(approval.decided_by) if approval.decided_by else None,
        decision_note=approval.decision_note,
    )


def build_policy_query(
    *, run: Run, tools: Sequence[Tool], principal_id: str, roles: Sequence[str]
) -> PolicyQuery:
    return PolicyQuery(
        tenant_id=str(run.tenant_id),
        principal_id=principal_id,
        roles=list(roles),
        run_id=str(run.id),
        goal=run.goal.text,
        priority=run.priority.value,
        parameters=dict(run.parameters or {}),
        workflow_id=run.workflow_id,
        workflow_version=run.workflow_version,
        tools=[PolicyToolRef(id=str(t.id), name=t.name, kind=t.kind.value) for t in tools],
    )
