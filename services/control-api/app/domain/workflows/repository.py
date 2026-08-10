"""Repository ports for the Workflow Authoring context."""

from __future__ import annotations

import abc

from app.domain.shared.identifiers import TenantId, WorkflowId
from app.domain.workflows.entities import Workflow, WorkflowVersion


class WorkflowRepository(abc.ABC):
    @abc.abstractmethod
    async def add(self, workflow: Workflow) -> None: ...

    @abc.abstractmethod
    async def save(self, workflow: Workflow) -> None: ...

    @abc.abstractmethod
    async def get(self, tenant_id: TenantId, workflow_id: WorkflowId) -> Workflow | None: ...

    @abc.abstractmethod
    async def find_by_name(self, tenant_id: TenantId, name: str) -> Workflow | None: ...

    @abc.abstractmethod
    async def list(self, tenant_id: TenantId) -> list[Workflow]: ...


class WorkflowVersionRepository(abc.ABC):
    @abc.abstractmethod
    async def add(self, version: WorkflowVersion) -> None: ...

    @abc.abstractmethod
    async def save(self, version: WorkflowVersion) -> None: ...

    @abc.abstractmethod
    async def get(
        self, tenant_id: TenantId, workflow_id: WorkflowId, version: int
    ) -> WorkflowVersion | None: ...

    @abc.abstractmethod
    async def list_for_workflow(
        self, tenant_id: TenantId, workflow_id: WorkflowId
    ) -> list[WorkflowVersion]: ...

    @abc.abstractmethod
    async def latest(
        self, tenant_id: TenantId, workflow_id: WorkflowId
    ) -> WorkflowVersion | None: ...
