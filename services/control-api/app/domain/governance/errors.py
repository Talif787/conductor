"""Domain rule violations for the Governance context."""

from __future__ import annotations


class GovernanceError(Exception):
    """Base class for governance rule violations."""


class ApprovalNotFoundError(GovernanceError):
    def __init__(self, approval_id: str) -> None:
        super().__init__(f"approval request '{approval_id}' was not found")
        self.approval_id = approval_id


class InvalidApprovalStateError(GovernanceError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class RunDeniedError(GovernanceError):
    """Raised when policy denies a run outright."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"run denied by policy: {reason}")
        self.reason = reason
