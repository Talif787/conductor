"""Entities for the Execution context."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.domain.execution.value_objects import ExecutionStatus
from app.domain.run.value_objects import RunId
from app.domain.shared.identifiers import RunExecutionId, StepExecutionId, TenantId


@dataclass
class StepExecution:
    id: StepExecutionId
    step_id: str
    tool_id: str
    position: int
    status: ExecutionStatus
    output: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


@dataclass
class RunExecution:
    id: RunExecutionId
    run_id: RunId
    tenant_id: TenantId
    status: ExecutionStatus
    started_at: datetime
    finished_at: datetime | None = None
    error: str | None = None
    steps: list[StepExecution] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return self.status is ExecutionStatus.SUCCEEDED
