"""Read-side queries for the Run bounded context."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GetRun:
    tenant_id: str
    run_id: str


@dataclass(frozen=True, slots=True)
class ListRuns:
    tenant_id: str
    status: str | None = None
    limit: int = 20
    cursor: str | None = None
