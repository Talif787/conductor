from __future__ import annotations

import pytest

from app.domain.workflows.errors import WorkflowValidationError
from app.domain.workflows.validation import validate_definition
from app.domain.workflows.value_objects import Step, WorkflowDefinition

TOOLS = {"t1", "t2", "t3"}


def _def(*steps: Step) -> WorkflowDefinition:
    return WorkflowDefinition(steps=tuple(steps))


def test_valid_diamond_passes() -> None:
    validate_definition(
        _def(
            Step("a", "A", "t1"),
            Step("b", "B", "t2", ("a",)),
            Step("c", "C", "t3", ("a",)),
            Step("d", "D", "t1", ("b", "c")),
        ),
        TOOLS,
    )


def test_empty_is_rejected() -> None:
    with pytest.raises(WorkflowValidationError):
        validate_definition(_def(), TOOLS)


def test_duplicate_step_ids_rejected() -> None:
    with pytest.raises(WorkflowValidationError, match="duplicate"):
        validate_definition(_def(Step("a", "A", "t1"), Step("a", "B", "t2")), TOOLS)


def test_unknown_dependency_rejected() -> None:
    with pytest.raises(WorkflowValidationError, match="unknown step"):
        validate_definition(_def(Step("a", "A", "t1", ("ghost",))), TOOLS)


def test_unregistered_tool_rejected() -> None:
    with pytest.raises(WorkflowValidationError, match="unregistered tool"):
        validate_definition(_def(Step("a", "A", "tX")), TOOLS)


def test_self_dependency_rejected() -> None:
    with pytest.raises(WorkflowValidationError, match="itself"):
        validate_definition(_def(Step("a", "A", "t1", ("a",))), TOOLS)


@pytest.mark.parametrize(
    "steps",
    [
        (Step("a", "A", "t1", ("b",)), Step("b", "B", "t2", ("a",))),
        (
            Step("a", "A", "t1", ("c",)),
            Step("b", "B", "t2", ("a",)),
            Step("c", "C", "t3", ("b",)),
        ),
    ],
)
def test_cycles_rejected(steps: tuple[Step, ...]) -> None:
    with pytest.raises(WorkflowValidationError, match="cycle"):
        validate_definition(WorkflowDefinition(steps=steps), TOOLS)


def test_definition_roundtrip() -> None:
    definition = _def(Step("a", "A", "t1"), Step("b", "B", "t2", ("a",)))
    assert WorkflowDefinition.from_dict(definition.to_dict()) == definition
