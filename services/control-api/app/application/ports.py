"""Application-level ports: unit of work and event publishing."""

from __future__ import annotations

import abc
from collections.abc import Sequence
from types import TracebackType

from app.domain.execution.repository import RunExecutionRepository
from app.domain.identity.repository import (
    MembershipRepository,
    RefreshTokenRepository,
    TenantRepository,
    UserRepository,
)
from app.domain.run.events import DomainEvent
from app.domain.run.repository import RunRepository
from app.domain.tools.repository import ToolRepository
from app.domain.workflows.repository import (
    WorkflowRepository,
    WorkflowVersionRepository,
)


class UnitOfWork(abc.ABC):
    """Transactional boundary exposing the aggregate repositories."""

    runs: RunRepository
    tenants: TenantRepository
    users: UserRepository
    memberships: MembershipRepository
    refresh_tokens: RefreshTokenRepository
    tools: ToolRepository
    workflows: WorkflowRepository
    workflow_versions: WorkflowVersionRepository
    run_executions: RunExecutionRepository

    async def __aenter__(self) -> UnitOfWork:
        return self

    @abc.abstractmethod
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    @abc.abstractmethod
    async def flush(self) -> None: ...

    @abc.abstractmethod
    async def commit(self) -> None: ...

    @abc.abstractmethod
    async def rollback(self) -> None: ...


class EventPublisher(abc.ABC):
    @abc.abstractmethod
    async def publish(self, events: Sequence[DomainEvent]) -> None: ...
