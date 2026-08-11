from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SubmitRun:
    tenant_id: str
    run_id: str
    principal_id: str
    roles: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ApproveRequest:
    tenant_id: str
    approval_id: str
    decided_by: str
    note: str | None = None


@dataclass(frozen=True, slots=True)
class RejectRequest:
    tenant_id: str
    approval_id: str
    decided_by: str
    note: str | None = None
