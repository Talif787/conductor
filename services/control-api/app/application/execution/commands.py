from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExecuteRun:
    tenant_id: str
    run_id: str
