"""Deterministic DAG planning helpers.

Pure and framework free so the same ordering logic is unit testable and safe to
call inside a Temporal workflow, where set iteration order is not permitted. All
ordered outputs derive from the step definition order, so results are
reproducible across workflow replays.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.application.execution.temporal_dtos import WorkflowStepSpec

_SUCCEEDED = "succeeded"
_FAILED_OR_SKIPPED = ("failed", "skipped")


def dependency_map(steps: Sequence[WorkflowStepSpec]) -> dict[str, list[str]]:
    return {step.step_id: list(step.depends_on) for step in steps}


def positions(steps: Sequence[WorkflowStepSpec]) -> dict[str, int]:
    return {step.step_id: index for index, step in enumerate(steps)}


def ready_steps(
    remaining: Sequence[str], deps: dict[str, list[str]], statuses: dict[str, str]
) -> list[str]:
    """Steps whose every dependency has succeeded, in the given order."""
    return [sid for sid in remaining if all(statuses.get(dep) == _SUCCEEDED for dep in deps[sid])]


def steps_to_skip(
    remaining: Sequence[str], deps: dict[str, list[str]], statuses: dict[str, str]
) -> list[str]:
    """Steps with at least one failed or skipped dependency, in the given order."""
    return [
        sid
        for sid in remaining
        if any(statuses.get(dep) in _FAILED_OR_SKIPPED for dep in deps[sid])
    ]


def compute_waves(steps: Sequence[WorkflowStepSpec]) -> list[list[str]]:
    """Topological waves assuming every step succeeds.

    Each wave is a list of step ids that can run concurrently. Raises ValueError
    on an unknown dependency or a cycle. Ordering follows the step definition
    order so the result is deterministic.
    """
    deps = dependency_map(steps)
    known = set(deps)
    for sid, dependencies in deps.items():
        for dep in dependencies:
            if dep not in known:
                raise ValueError(f"step '{sid}' depends on unknown step '{dep}'")

    remaining = [step.step_id for step in steps]
    done: set[str] = set()
    waves: list[list[str]] = []
    while remaining:
        wave = [sid for sid in remaining if all(dep in done for dep in deps[sid])]
        if not wave:
            raise ValueError("workflow steps contain a cycle")
        waves.append(wave)
        done.update(wave)
        remaining = [sid for sid in remaining if sid not in wave]
    return waves


def summarize_outcomes(
    outcomes: Sequence[tuple[str, str, str | None]],
) -> tuple[str, str | None]:
    """Reduce ordered (step_id, status, error) tuples to an overall status.

    A single failed step fails the run; steps skipped after an upstream failure
    also fail the run. Mirrors the local engine's summary.
    """
    failed = [(sid, err) for sid, status, err in outcomes if status == "failed"]
    if failed:
        sid, err = failed[0]
        return "failed", f"step '{sid}' failed: {err}"
    if any(status == "skipped" for _, status, _ in outcomes):
        return "failed", "one or more steps were skipped after an upstream failure"
    return "succeeded", None
