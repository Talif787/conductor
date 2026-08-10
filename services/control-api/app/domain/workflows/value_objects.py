"""Value objects for the Workflow Authoring context."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class WorkflowStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class VersionStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class Step:
    step_id: str
    name: str
    tool_id: str
    depends_on: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "tool_id": self.tool_id,
            "depends_on": list(self.depends_on),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Step:
        try:
            return Step(
                step_id=str(data["step_id"]),
                name=str(data.get("name", data["step_id"])),
                tool_id=str(data["tool_id"]),
                depends_on=tuple(str(dep) for dep in data.get("depends_on", [])),
            )
        except (KeyError, TypeError) as exc:
            raise ValueError(f"invalid step definition: {exc}") from exc


@dataclass(frozen=True, slots=True)
class WorkflowDefinition:
    steps: tuple[Step, ...]

    @staticmethod
    def empty() -> WorkflowDefinition:
        return WorkflowDefinition(steps=())

    def to_dict(self) -> dict[str, Any]:
        return {"steps": [step.to_dict() for step in self.steps]}

    @staticmethod
    def from_dict(data: dict[str, Any]) -> WorkflowDefinition:
        raw_steps = data.get("steps", [])
        if not isinstance(raw_steps, list):
            raise ValueError("workflow definition 'steps' must be a list")
        return WorkflowDefinition(steps=tuple(Step.from_dict(item) for item in raw_steps))
