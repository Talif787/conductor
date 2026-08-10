"""Domain rule violations for the Run bounded context."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for violations of domain invariants."""


class InvalidStateTransitionError(DomainError):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(f"cannot transition run from '{current}' to '{target}'")
        self.current = current
        self.target = target


class RunNotFoundError(DomainError):
    def __init__(self, run_id: str) -> None:
        super().__init__(f"run '{run_id}' was not found")
        self.run_id = run_id
