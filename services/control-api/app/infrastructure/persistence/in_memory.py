"""In-memory adapters used by unit and API tests (no database required)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from types import TracebackType

from app.application.ports import UnitOfWork
from app.domain.execution.entities import RunExecution
from app.domain.execution.repository import RunExecutionRepository
from app.domain.governance.entities import ApprovalRequest
from app.domain.governance.repository import ApprovalRepository
from app.domain.governance.value_objects import ApprovalStatus
from app.domain.identity.entities import Membership, RefreshToken, Tenant, User
from app.domain.identity.repository import (
    MembershipRepository,
    RefreshTokenRepository,
    TenantRepository,
    UserRepository,
)
from app.domain.identity.value_objects import Email
from app.domain.run.entities import Run
from app.domain.run.events import DomainEvent
from app.domain.run.repository import Page, PagedRuns, RunFilter, RunRepository
from app.domain.run.value_objects import RunId
from app.domain.shared.identifiers import (
    ApprovalId,
    TenantId,
    ToolId,
    UserId,
    WorkflowId,
)
from app.domain.tools.entities import Tool
from app.domain.tools.repository import ToolRepository
from app.domain.workflows.entities import Workflow, WorkflowVersion
from app.domain.workflows.repository import (
    WorkflowRepository,
    WorkflowVersionRepository,
)


@dataclass
class InMemoryDatabase:
    runs: dict[uuid.UUID, Run] = field(default_factory=dict)
    tenants: dict[uuid.UUID, Tenant] = field(default_factory=dict)
    users: dict[uuid.UUID, User] = field(default_factory=dict)
    memberships: dict[uuid.UUID, Membership] = field(default_factory=dict)
    refresh_tokens: dict[uuid.UUID, RefreshToken] = field(default_factory=dict)
    tools: dict[uuid.UUID, Tool] = field(default_factory=dict)
    workflows: dict[uuid.UUID, Workflow] = field(default_factory=dict)
    workflow_versions: dict[uuid.UUID, WorkflowVersion] = field(default_factory=dict)
    run_executions: dict[uuid.UUID, RunExecution] = field(default_factory=dict)
    approvals: dict[uuid.UUID, ApprovalRequest] = field(default_factory=dict)


class InMemoryRunRepository(RunRepository):
    def __init__(self, store: dict[uuid.UUID, Run]) -> None:
        self._store = store
        self.published_events: list[DomainEvent] = []

    async def add(self, run: Run, events: Sequence[DomainEvent]) -> None:
        self._store[run.id.value] = run
        self.published_events.extend(events)

    async def save(self, run: Run, events: Sequence[DomainEvent]) -> None:
        self._store[run.id.value] = run
        self.published_events.extend(events)

    async def get(self, tenant_id: TenantId, run_id: RunId) -> Run | None:
        run = self._store.get(run_id.value)
        if run is not None and run.tenant_id == tenant_id:
            return run
        return None

    async def find_by_idempotency_key(
        self, tenant_id: TenantId, idempotency_key: str
    ) -> Run | None:
        for run in self._store.values():
            if run.tenant_id == tenant_id and run.idempotency_key == idempotency_key:
                return run
        return None

    async def list(self, tenant_id: TenantId, run_filter: RunFilter, page: Page) -> PagedRuns:
        runs = [run for run in self._store.values() if run.tenant_id == tenant_id]
        if run_filter.status is not None:
            runs = [run for run in runs if run.status == run_filter.status]
        runs.sort(key=lambda r: (r.created_at, r.id.value), reverse=True)
        return PagedRuns(runs=runs[: page.limit], next_cursor=None)


class InMemoryTenantRepository(TenantRepository):
    def __init__(self, store: dict[uuid.UUID, Tenant]) -> None:
        self._store = store

    async def add(self, tenant: Tenant) -> None:
        self._store[tenant.id.value] = tenant

    async def get(self, tenant_id: TenantId) -> Tenant | None:
        return self._store.get(tenant_id.value)


class InMemoryUserRepository(UserRepository):
    def __init__(self, store: dict[uuid.UUID, User]) -> None:
        self._store = store

    async def add(self, user: User) -> None:
        self._store[user.id.value] = user

    async def get(self, user_id: UserId) -> User | None:
        return self._store.get(user_id.value)

    async def find_by_email(self, email: Email) -> User | None:
        for user in self._store.values():
            if user.email == email:
                return user
        return None


class InMemoryMembershipRepository(MembershipRepository):
    def __init__(self, store: dict[uuid.UUID, Membership]) -> None:
        self._store = store

    async def add(self, membership: Membership) -> None:
        self._store[membership.id.value] = membership

    async def find_by_user(self, user_id: UserId) -> list[Membership]:
        return [m for m in self._store.values() if m.user_id == user_id]


class InMemoryRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self, store: dict[uuid.UUID, RefreshToken]) -> None:
        self._store = store

    async def add(self, token: RefreshToken) -> None:
        self._store[token.id.value] = token

    async def find_by_hash(self, token_hash: str) -> RefreshToken | None:
        for token in self._store.values():
            if token.token_hash == token_hash:
                return token
        return None

    async def mark_used(self, token_id: uuid.UUID) -> None:
        token = self._store.get(token_id)
        if token is not None:
            token.used = True

    async def revoke_family(self, family_id: uuid.UUID) -> None:
        for token in self._store.values():
            if token.family_id == family_id:
                token.revoked = True


class InMemoryUnitOfWork(UnitOfWork):
    def __init__(self, db: InMemoryDatabase) -> None:
        self._db = db
        self.committed = False

    async def __aenter__(self) -> InMemoryUnitOfWork:
        self.runs = InMemoryRunRepository(self._db.runs)
        self.tenants = InMemoryTenantRepository(self._db.tenants)
        self.users = InMemoryUserRepository(self._db.users)
        self.memberships = InMemoryMembershipRepository(self._db.memberships)
        self.refresh_tokens = InMemoryRefreshTokenRepository(self._db.refresh_tokens)
        self.tools = InMemoryToolRepository(self._db.tools)
        self.workflows = InMemoryWorkflowRepository(self._db.workflows)
        self.workflow_versions = InMemoryWorkflowVersionRepository(self._db.workflow_versions)
        self.run_executions = InMemoryRunExecutionRepository(self._db.run_executions)
        self.approvals = InMemoryApprovalRepository(self._db.approvals)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        return None


class InMemoryToolRepository(ToolRepository):
    def __init__(self, store: dict[uuid.UUID, Tool]) -> None:
        self._store = store

    async def add(self, tool: Tool) -> None:
        self._store[tool.id.value] = tool

    async def get(self, tenant_id: TenantId, tool_id: ToolId) -> Tool | None:
        tool = self._store.get(tool_id.value)
        if tool is not None and tool.tenant_id == tenant_id:
            return tool
        return None

    async def find_by_name(self, tenant_id: TenantId, name: str) -> Tool | None:
        for tool in self._store.values():
            if tool.tenant_id == tenant_id and tool.name == name:
                return tool
        return None

    async def list(self, tenant_id: TenantId) -> list[Tool]:
        return [t for t in self._store.values() if t.tenant_id == tenant_id]


class InMemoryWorkflowRepository(WorkflowRepository):
    def __init__(self, store: dict[uuid.UUID, Workflow]) -> None:
        self._store = store

    async def add(self, workflow: Workflow) -> None:
        self._store[workflow.id.value] = workflow

    async def save(self, workflow: Workflow) -> None:
        self._store[workflow.id.value] = workflow

    async def get(self, tenant_id: TenantId, workflow_id: WorkflowId) -> Workflow | None:
        workflow = self._store.get(workflow_id.value)
        if workflow is not None and workflow.tenant_id == tenant_id:
            return workflow
        return None

    async def find_by_name(self, tenant_id: TenantId, name: str) -> Workflow | None:
        for workflow in self._store.values():
            if workflow.tenant_id == tenant_id and workflow.name == name:
                return workflow
        return None

    async def list(self, tenant_id: TenantId) -> list[Workflow]:
        return [w for w in self._store.values() if w.tenant_id == tenant_id]


class InMemoryWorkflowVersionRepository(WorkflowVersionRepository):
    def __init__(self, store: dict[uuid.UUID, WorkflowVersion]) -> None:
        self._store = store

    async def add(self, version: WorkflowVersion) -> None:
        self._store[version.id.value] = version

    async def save(self, version: WorkflowVersion) -> None:
        self._store[version.id.value] = version

    async def get(
        self, tenant_id: TenantId, workflow_id: WorkflowId, version: int
    ) -> WorkflowVersion | None:
        for candidate in self._store.values():
            if (
                candidate.tenant_id == tenant_id
                and candidate.workflow_id == workflow_id
                and candidate.version == version
            ):
                return candidate
        return None

    async def list_for_workflow(
        self, tenant_id: TenantId, workflow_id: WorkflowId
    ) -> list[WorkflowVersion]:
        return [
            v
            for v in self._store.values()
            if v.tenant_id == tenant_id and v.workflow_id == workflow_id
        ]

    async def latest(self, tenant_id: TenantId, workflow_id: WorkflowId) -> WorkflowVersion | None:
        versions = await self.list_for_workflow(tenant_id, workflow_id)
        return max(versions, key=lambda v: v.version) if versions else None


class InMemoryRunExecutionRepository(RunExecutionRepository):
    def __init__(self, store: dict[uuid.UUID, RunExecution]) -> None:
        self._store = store

    async def add(self, execution: RunExecution) -> None:
        self._store[execution.run_id.value] = execution

    async def get(self, tenant_id: TenantId, run_id: RunId) -> RunExecution | None:
        execution = self._store.get(run_id.value)
        if execution is not None and execution.tenant_id == tenant_id:
            return execution
        return None


class InMemoryApprovalRepository(ApprovalRepository):
    def __init__(self, store: dict[uuid.UUID, ApprovalRequest]) -> None:
        self._store = store

    async def add(self, approval: ApprovalRequest) -> None:
        self._store[approval.id.value] = approval

    async def save(self, approval: ApprovalRequest) -> None:
        self._store[approval.id.value] = approval

    async def get(self, tenant_id: TenantId, approval_id: ApprovalId) -> ApprovalRequest | None:
        approval = self._store.get(approval_id.value)
        if approval is not None and approval.tenant_id == tenant_id:
            return approval
        return None

    async def get_for_run(self, tenant_id: TenantId, run_id: RunId) -> ApprovalRequest | None:
        matches = [
            a for a in self._store.values() if a.tenant_id == tenant_id and a.run_id == run_id
        ]
        pending = [a for a in matches if a.is_pending]
        if pending:
            return pending[0]
        return matches[0] if matches else None

    async def list(
        self, tenant_id: TenantId, status: ApprovalStatus | None = None
    ) -> list[ApprovalRequest]:
        items = [a for a in self._store.values() if a.tenant_id == tenant_id]
        if status is not None:
            items = [a for a in items if a.status == status]
        items.sort(key=lambda a: a.requested_at, reverse=True)
        return items
