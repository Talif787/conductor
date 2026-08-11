"""Immutable value objects for the Run bounded context."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum

from app.domain.shared.identifiers import TenantId as TenantId  # re-exported shared identifier

MAX_GOAL_LENGTH = 8000


class RunStatus(StrEnum):
    QUEUED = "queued"
    PLANNING = "planning"
    RUNNING = "running"
    PAUSED = "paused"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}


class Priority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class RunId:
    value: uuid.UUID

    @staticmethod
    def new() -> RunId:
        return RunId(uuid.uuid4())

    @staticmethod
    def parse(raw: str) -> RunId:
        return RunId(uuid.UUID(raw))

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class Goal:
    text: str

    def __post_init__(self) -> None:
        cleaned = self.text.strip()
        if not cleaned:
            raise ValueError("goal must not be empty")
        if len(cleaned) > MAX_GOAL_LENGTH:
            raise ValueError(f"goal exceeds maximum length of {MAX_GOAL_LENGTH} characters")
        object.__setattr__(self, "text", cleaned)
