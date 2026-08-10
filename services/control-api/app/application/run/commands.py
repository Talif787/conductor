"""Write-side commands for the Run bounded context."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CreateRun:
    tenant_id: str
    goal: str
    priority: str = "normal"
    parameters: dict[str, Any] | None = None
    workflow_id: str | None = None
    workflow_version: str | None = None
    idempotency_key: str | None = None


@dataclass(frozen=True, slots=True)
class CancelRun:
    tenant_id: str
    run_id: str
