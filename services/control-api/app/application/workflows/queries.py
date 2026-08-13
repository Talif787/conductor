from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GetWorkflow:
    tenant_id: str
    workflow_id: str


@dataclass(frozen=True, slots=True)
class ListWorkflows:
    tenant_id: str


@dataclass(frozen=True, slots=True)
class GetWorkflowVersion:
    tenant_id: str
    workflow_id: str
    version: int
