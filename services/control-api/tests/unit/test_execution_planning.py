from __future__ import annotations

import pytest

from app.application.execution import planning
from app.application.execution.temporal_dtos import WorkflowStepSpec


def _steps(*specs: tuple[str, tuple[str, ...]]) -> list[WorkflowStepSpec]:
    return [
        WorkflowStepSpec(step_id=sid, tool_id=f"tool-{sid}", depends_on=list(deps))
        for sid, deps in specs
    ]


def test_compute_waves_linear_chain() -> None:
    waves = planning.compute_waves(_steps(("a", ()), ("b", ("a",)), ("c", ("b",))))
    assert waves == [["a"], ["b"], ["c"]]


def test_compute_waves_diamond() -> None:
    waves = planning.compute_waves(
        _steps(("a", ()), ("b", ("a",)), ("c", ("a",)), ("d", ("b", "c")))
    )
    assert waves == [["a"], ["b", "c"], ["d"]]


def test_compute_waves_parallel_roots() -> None:
    assert planning.compute_waves(_steps(("x", ()), ("y", ()))) == [["x", "y"]]


def test_compute_waves_preserves_definition_order_within_wave() -> None:
    assert planning.compute_waves(_steps(("c", ()), ("a", ()), ("b", ()))) == [["c", "a", "b"]]


def test_compute_waves_rejects_cycle() -> None:
    with pytest.raises(ValueError, match="cycle"):
        planning.compute_waves(_steps(("a", ("b",)), ("b", ("a",))))


def test_compute_waves_rejects_unknown_dependency() -> None:
    with pytest.raises(ValueError, match="unknown"):
        planning.compute_waves(_steps(("a", ("ghost",))))


def test_ready_and_skip_reflect_dependency_status() -> None:
    deps = planning.dependency_map(
        _steps(("a", ()), ("b", ("a",)), ("c", ("a",)), ("d", ("b", "c")))
    )
    statuses = {"a": "succeeded", "b": "failed"}
    assert planning.ready_steps(["c", "d"], deps, statuses) == ["c"]
    assert planning.steps_to_skip(["d"], deps, statuses) == ["d"]
    assert planning.ready_steps(["d"], deps, {"b": "succeeded", "c": "succeeded"}) == ["d"]


def test_positions_follow_definition_order() -> None:
    assert planning.positions(_steps(("a", ()), ("b", ()), ("c", ()))) == {"a": 0, "b": 1, "c": 2}


def test_summarize_all_succeeded() -> None:
    assert planning.summarize_outcomes([("a", "succeeded", None), ("b", "succeeded", None)]) == (
        "succeeded",
        None,
    )


def test_summarize_failure_wins_and_names_step() -> None:
    status, error = planning.summarize_outcomes(
        [("a", "succeeded", None), ("b", "failed", "boom"), ("c", "skipped", None)]
    )
    assert status == "failed"
    assert error is not None and "b" in error and "boom" in error


def test_summarize_skip_only_fails_run() -> None:
    status, error = planning.summarize_outcomes([("a", "succeeded", None), ("b", "skipped", None)])
    assert status == "failed"
    assert error is not None and "skipped" in error
