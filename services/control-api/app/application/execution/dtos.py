from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class StepExecutionDTO:
    step_id: str
    tool_id: str
    position: int
    status: str
    output: dict[str, Any] | None
    error: str | None
    started_at: str | None
    finished_at: str | None
    cost_usd: float


@dataclass(frozen=True, slots=True)
class RunExecutionDTO:
    run_id: str
    status: str
    error: str | None
    started_at: str
    finished_at: str | None
    total_cost_usd: float
    steps: list[StepExecutionDTO]
