from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RunViewDTO:
    run_id: str
    tenant_id: str
    status: str
    goal: str
    priority: str
    created_at: str
    updated_at: str
    event_count: int


@dataclass(frozen=True, slots=True)
class RunStatsDTO:
    total: int
    active: int
    by_status: dict[str, int]
