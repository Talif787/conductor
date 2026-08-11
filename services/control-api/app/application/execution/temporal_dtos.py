"""Serializable data transfer objects for the Temporal boundary.

Plain dataclasses only: Temporal's default data converter handles dataclasses,
dicts, lists, and primitives over JSON. Nothing here imports temporalio, so the
types can be unit tested without a cluster and passed through the workflow
sandbox cheaply.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkflowStepSpec:
    step_id: str
    tool_id: str
    depends_on: list[str] = field(default_factory=list)


@dataclass
class RunWorkflowInput:
    tenant_id: str
    run_id: str
    parameters: dict[str, Any] = field(default_factory=dict)
    steps: list[WorkflowStepSpec] = field(default_factory=list)
    activity_timeout_seconds: int = 60
    activity_max_attempts: int = 1


@dataclass
class StepActivityInput:
    tenant_id: str
    tool_id: str
    step_id: str
    parameters: dict[str, Any] = field(default_factory=dict)
    inputs: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class StepActivityResult:
    output: dict[str, Any] = field(default_factory=dict)
    started_at: str = ""
    finished_at: str = ""


@dataclass
class StepOutcome:
    step_id: str
    tool_id: str
    position: int
    status: str
    output: dict[str, Any] | None = None
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


@dataclass
class RunWorkflowResult:
    status: str
    error: str | None = None
    steps: list[StepOutcome] = field(default_factory=list)
