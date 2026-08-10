"""Structural validation of a workflow definition."""

from __future__ import annotations

from collections.abc import Set

from app.domain.workflows.errors import WorkflowValidationError
from app.domain.workflows.value_objects import Step, WorkflowDefinition

_WHITE, _GRAY, _BLACK = 0, 1, 2


def validate_definition(definition: WorkflowDefinition, available_tool_ids: Set[str]) -> None:
    """Raise WorkflowValidationError if the definition is not a valid DAG.

    Checks: non-empty, unique step ids, dependencies resolve, tool references
    resolve to registered tools, and the dependency graph is acyclic.
    """
    steps = definition.steps
    if not steps:
        raise WorkflowValidationError("a workflow must have at least one step")

    ids = [step.step_id for step in steps]
    seen: set[str] = set()
    duplicates: set[str] = set()
    for step_id in ids:
        if step_id in seen:
            duplicates.add(step_id)
        seen.add(step_id)
    if duplicates:
        raise WorkflowValidationError(f"duplicate step ids: {sorted(duplicates)}")

    for step in steps:
        if step.tool_id not in available_tool_ids:
            raise WorkflowValidationError(
                f"step '{step.step_id}' references unregistered tool '{step.tool_id}'"
            )
        for dependency in step.depends_on:
            if dependency == step.step_id:
                raise WorkflowValidationError(f"step '{step.step_id}' depends on itself")
            if dependency not in seen:
                raise WorkflowValidationError(
                    f"step '{step.step_id}' depends on unknown step '{dependency}'"
                )

    _ensure_acyclic(steps)


def _ensure_acyclic(steps: tuple[Step, ...]) -> None:
    graph: dict[str, list[str]] = {step.step_id: list(step.depends_on) for step in steps}
    color: dict[str, int] = dict.fromkeys(graph, _WHITE)
    stack: list[tuple[str, int]] = []

    for root in graph:
        if color[root] != _WHITE:
            continue
        stack.append((root, 0))
        while stack:
            node, index = stack.pop()
            if index == 0:
                color[node] = _GRAY
            if index < len(graph[node]):
                stack.append((node, index + 1))
                neighbor = graph[node][index]
                if color[neighbor] == _GRAY:
                    raise WorkflowValidationError("workflow definition contains a cycle")
                if color[neighbor] == _WHITE:
                    stack.append((neighbor, 0))
            else:
                color[node] = _BLACK
