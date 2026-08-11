from __future__ import annotations

from dataclasses import dataclass

from app.application.execution.dtos import RunExecutionDTO


@dataclass(frozen=True, slots=True)
class ApprovalDTO:
    id: str
    run_id: str
    reason: str
    status: str
    requested_at: str
    decided_at: str | None
    decided_by: str | None
    decision_note: str | None


@dataclass(frozen=True, slots=True)
class SubmitRunResultDTO:
    outcome: str  # "executed" or "pending_approval"
    execution: RunExecutionDTO | None = None
    approval: ApprovalDTO | None = None
