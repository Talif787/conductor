from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.shared.identifiers import TenantId, WorkflowId
from app.domain.workflows.entities import Workflow, WorkflowVersion
from app.domain.workflows.repository import (
    WorkflowRepository,
    WorkflowVersionRepository,
)
from app.infrastructure.persistence.models import WorkflowModel, WorkflowVersionModel
from app.infrastructure.persistence.workflow_mappers import (
    model_to_version,
    model_to_workflow,
    version_to_model,
    workflow_to_model,
)


class SqlAlchemyWorkflowRepository(WorkflowRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, workflow: Workflow) -> None:
        self._session.add(workflow_to_model(workflow))

    async def save(self, workflow: Workflow) -> None:
        await self._session.merge(workflow_to_model(workflow))

    async def get(self, tenant_id: TenantId, workflow_id: WorkflowId) -> Workflow | None:
        model = await self._session.get(WorkflowModel, workflow_id.value)
        if model is None or model.tenant_id != tenant_id.value:
            return None
        return model_to_workflow(model)

    async def find_by_name(self, tenant_id: TenantId, name: str) -> Workflow | None:
        stmt = select(WorkflowModel).where(
            WorkflowModel.tenant_id == tenant_id.value, WorkflowModel.name == name
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return model_to_workflow(model) if model is not None else None

    async def list(self, tenant_id: TenantId) -> list[Workflow]:
        stmt = (
            select(WorkflowModel)
            .where(WorkflowModel.tenant_id == tenant_id.value)
            .order_by(WorkflowModel.created_at)
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [model_to_workflow(m) for m in models]


class SqlAlchemyWorkflowVersionRepository(WorkflowVersionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, version: WorkflowVersion) -> None:
        self._session.add(version_to_model(version))

    async def save(self, version: WorkflowVersion) -> None:
        await self._session.merge(version_to_model(version))

    async def get(
        self, tenant_id: TenantId, workflow_id: WorkflowId, version: int
    ) -> WorkflowVersion | None:
        stmt = select(WorkflowVersionModel).where(
            WorkflowVersionModel.tenant_id == tenant_id.value,
            WorkflowVersionModel.workflow_id == workflow_id.value,
            WorkflowVersionModel.version == version,
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return model_to_version(model) if model is not None else None

    async def list_for_workflow(
        self, tenant_id: TenantId, workflow_id: WorkflowId
    ) -> list[WorkflowVersion]:
        stmt = (
            select(WorkflowVersionModel)
            .where(
                WorkflowVersionModel.tenant_id == tenant_id.value,
                WorkflowVersionModel.workflow_id == workflow_id.value,
            )
            .order_by(WorkflowVersionModel.version)
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [model_to_version(m) for m in models]

    async def latest(self, tenant_id: TenantId, workflow_id: WorkflowId) -> WorkflowVersion | None:
        stmt = (
            select(WorkflowVersionModel)
            .where(
                WorkflowVersionModel.tenant_id == tenant_id.value,
                WorkflowVersionModel.workflow_id == workflow_id.value,
            )
            .order_by(WorkflowVersionModel.version.desc())
            .limit(1)
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return model_to_version(model) if model is not None else None
