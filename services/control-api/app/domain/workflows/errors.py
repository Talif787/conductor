"""Errors for the Workflow Authoring context."""

from __future__ import annotations


class WorkflowError(Exception):
    """Base class for workflow authoring failures."""


class WorkflowNotFoundError(WorkflowError):
    def __init__(self, workflow_id: str) -> None:
        super().__init__(f"workflow '{workflow_id}' was not found")


class WorkflowVersionNotFoundError(WorkflowError):
    def __init__(self, workflow_id: str, version: int | str) -> None:
        super().__init__(f"version '{version}' of workflow '{workflow_id}' was not found")


class InvalidWorkflowStateError(WorkflowError):
    """The requested transition is not allowed from the current state."""


class WorkflowValidationError(WorkflowError):
    """The workflow definition is structurally invalid."""


class WorkflowNameConflictError(WorkflowError):
    def __init__(self, name: str) -> None:
        super().__init__(f"a workflow named '{name}' already exists")
        self.name = name


class WorkflowNotPublishedError(WorkflowError):
    def __init__(self, workflow_id: str, version: int | str) -> None:
        super().__init__(f"version '{version}' of workflow '{workflow_id}' is not published")
