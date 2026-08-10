from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GetRunExecution:
    tenant_id: str
    run_id: str
