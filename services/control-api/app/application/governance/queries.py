from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GetApproval:
    tenant_id: str
    approval_id: str


@dataclass(frozen=True, slots=True)
class ListApprovals:
    tenant_id: str
    status: str | None = None
