from __future__ import annotations

import uuid

import pytest

from app.domain.run.entities import Run
from app.domain.run.errors import InvalidStateTransition
from app.domain.run.events import RunCancelled, RunCreated
from app.domain.run.value_objects import Goal, Priority, RunStatus, TenantId


def _new_run() -> Run:
    return Run.create(tenant_id=TenantId(uuid.uuid4()), goal=Goal("Summarize inbox"))


def test_create_starts_queued_and_records_event() -> None:
    run = _new_run()
    assert run.status is RunStatus.QUEUED
    events = run.pull_events()
    assert len(events) == 1
    assert isinstance(events[0], RunCreated)
    assert run.pull_events() == []


def test_valid_lifecycle_transitions() -> None:
    run = _new_run()
    run.pull_events()
    run.start_planning()
    run.start_running()
    run.complete()
    assert run.status is RunStatus.COMPLETED
    assert {e.name for e in run.pull_events()} == {
        "RunPlanningStarted",
        "RunRunningStarted",
        "RunCompleted",
    }


def test_invalid_transition_raises() -> None:
    run = _new_run()
    with pytest.raises(InvalidStateTransition):
        run.complete()


def test_cancel_from_queued() -> None:
    run = _new_run()
    run.pull_events()
    run.cancel()
    assert run.status is RunStatus.CANCELLED
    assert isinstance(run.pull_events()[0], RunCancelled)


def test_fail_records_reason() -> None:
    run = _new_run()
    run.start_planning()
    run.fail("provider timeout")
    assert run.status is RunStatus.FAILED
    assert run.error == "provider timeout"


def test_empty_goal_rejected() -> None:
    with pytest.raises(ValueError):
        Goal("   ")


def test_priority_values() -> None:
    run = Run.create(
        tenant_id=TenantId(uuid.uuid4()), goal=Goal("x"), priority=Priority.HIGH
    )
    assert run.priority is Priority.HIGH
