"""FastAPI dependency providers (the composition root wiring)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, Query, Request

from app.application.auth.command_handlers import (
    LoginHandler,
    LogoutHandler,
    RefreshTokensHandler,
    RegisterTenantHandler,
)
from app.application.auth.ports import AccessTokenService, PasswordHasher
from app.application.auth.principal import Principal
from app.application.execution.command_handlers import ExecuteRunHandler
from app.application.execution.ports import ExecutionEngine, LLMGateway
from app.application.execution.query_handlers import GetRunExecutionHandler
from app.application.execution.tool_clients import HttpToolClient, McpToolClient
from app.application.governance.command_handlers import (
    ApproveRequestHandler,
    RejectRequestHandler,
    SubmitRunHandler,
)
from app.application.governance.policy import PolicyDecisionPoint
from app.application.governance.query_handlers import (
    GetApprovalHandler,
    ListApprovalsHandler,
)
from app.application.ports import EventPublisher, UnitOfWork
from app.application.run.command_handlers import CancelRunHandler, CreateRunHandler
from app.application.run.query_handlers import GetRunHandler, ListRunsHandler
from app.application.tools.command_handlers import RegisterToolHandler, UpdateToolHandler
from app.application.tools.query_handlers import GetToolHandler, ListToolsHandler
from app.application.workflows.command_handlers import (
    ArchiveWorkflowHandler,
    CreateDraftHandler,
    CreateWorkflowHandler,
    PublishVersionHandler,
    UpdateDraftHandler,
)
from app.application.workflows.query_handlers import (
    GetWorkflowHandler,
    ListWorkflowsHandler,
)
from app.config.settings import AppSettings, get_settings
from app.domain.identity.errors import AuthenticationError, PermissionDeniedError
from app.domain.identity.roles import Permission
from app.infrastructure.execution.http_invoker import HttpToolInvoker
from app.infrastructure.execution.local_engine import LocalExecutionEngine
from app.infrastructure.execution.mcp_invoker import McpToolInvoker
from app.infrastructure.execution.tool_invoker import (
    BuiltinToolInvoker,
    CompositeToolInvoker,
)
from app.infrastructure.governance.local_policy import LocalPolicyEvaluator
from app.infrastructure.http.http_client import HttpxToolClient
from app.infrastructure.llm.gateway import FakeLLMGateway, HttpLLMGateway
from app.infrastructure.mcp.mcp_client import JsonRpcMcpToolClient
from app.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

UnitOfWorkFactory = Callable[[], UnitOfWork]


def provide_settings() -> AppSettings:
    return get_settings()


def provide_uow_factory(request: Request) -> UnitOfWorkFactory:
    session_factory = request.app.state.session_factory

    def factory() -> UnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    return factory


def provide_publisher(request: Request) -> EventPublisher:
    publisher: EventPublisher = request.app.state.publisher
    return publisher


def provide_password_hasher(request: Request) -> PasswordHasher:
    hasher: PasswordHasher = request.app.state.password_hasher
    return hasher


def provide_token_service(request: Request) -> AccessTokenService:
    service: AccessTokenService = request.app.state.token_service
    return service


# --- run handlers ---
def provide_create_run_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
    publisher: Annotated[EventPublisher, Depends(provide_publisher)],
) -> CreateRunHandler:
    return CreateRunHandler(uow_factory, publisher)


def provide_cancel_run_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
    publisher: Annotated[EventPublisher, Depends(provide_publisher)],
) -> CancelRunHandler:
    return CancelRunHandler(uow_factory, publisher)


def provide_get_run_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
) -> GetRunHandler:
    return GetRunHandler(uow_factory)


def provide_list_runs_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
) -> ListRunsHandler:
    return ListRunsHandler(uow_factory)


# --- auth handlers ---
def provide_register_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
    hasher: Annotated[PasswordHasher, Depends(provide_password_hasher)],
    tokens: Annotated[AccessTokenService, Depends(provide_token_service)],
    settings: Annotated[AppSettings, Depends(provide_settings)],
) -> RegisterTenantHandler:
    return RegisterTenantHandler(uow_factory, hasher, tokens, settings.auth.refresh_ttl_seconds)


def provide_login_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
    hasher: Annotated[PasswordHasher, Depends(provide_password_hasher)],
    tokens: Annotated[AccessTokenService, Depends(provide_token_service)],
    settings: Annotated[AppSettings, Depends(provide_settings)],
) -> LoginHandler:
    return LoginHandler(uow_factory, hasher, tokens, settings.auth.refresh_ttl_seconds)


def provide_refresh_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
    tokens: Annotated[AccessTokenService, Depends(provide_token_service)],
    settings: Annotated[AppSettings, Depends(provide_settings)],
) -> RefreshTokensHandler:
    return RefreshTokensHandler(uow_factory, tokens, settings.auth.refresh_ttl_seconds)


def provide_logout_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
) -> LogoutHandler:
    return LogoutHandler(uow_factory)


# --- authentication and authorization ---
def get_current_principal(
    token_service: Annotated[AccessTokenService, Depends(provide_token_service)],
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthenticationError("missing bearer token")
    token = authorization[len("bearer ") :].strip()
    return token_service.decode(token)


CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]


def require_permission(permission: Permission) -> Callable[[Principal], Principal]:
    def dependency(principal: CurrentPrincipal) -> Principal:
        if not principal.has_permission(permission):
            raise PermissionDeniedError(permission.value)
        return principal

    return dependency


def get_page_params(
    settings: Annotated[AppSettings, Depends(provide_settings)],
    limit: Annotated[int | None, Query(ge=1)] = None,
    cursor: Annotated[str | None, Query()] = None,
) -> tuple[int, str | None]:
    effective = limit or settings.default_page_size
    return min(effective, settings.max_page_size), cursor


PageParams = Annotated[tuple[int, str | None], Depends(get_page_params)]


# --- tool handlers ---
def provide_register_tool_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
) -> RegisterToolHandler:
    return RegisterToolHandler(uow_factory)


def provide_update_tool_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
) -> UpdateToolHandler:
    return UpdateToolHandler(uow_factory)


def provide_get_tool_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
) -> GetToolHandler:
    return GetToolHandler(uow_factory)


def provide_list_tools_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
) -> ListToolsHandler:
    return ListToolsHandler(uow_factory)


# --- workflow handlers ---
def provide_create_workflow_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
) -> CreateWorkflowHandler:
    return CreateWorkflowHandler(uow_factory)


def provide_update_draft_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
) -> UpdateDraftHandler:
    return UpdateDraftHandler(uow_factory)


def provide_publish_version_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
) -> PublishVersionHandler:
    return PublishVersionHandler(uow_factory)


def provide_create_draft_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
) -> CreateDraftHandler:
    return CreateDraftHandler(uow_factory)


def provide_archive_workflow_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
) -> ArchiveWorkflowHandler:
    return ArchiveWorkflowHandler(uow_factory)


def provide_get_workflow_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
) -> GetWorkflowHandler:
    return GetWorkflowHandler(uow_factory)


def provide_list_workflows_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
) -> ListWorkflowsHandler:
    return ListWorkflowsHandler(uow_factory)


# --- execution handlers ---
def provide_llm_gateway() -> LLMGateway:
    settings = get_settings().llm
    if settings.provider == "http":
        return HttpLLMGateway(
            base_url=settings.base_url,
            api_key=settings.api_key,
            model=settings.model,
            timeout_seconds=settings.timeout_seconds,
        )
    return FakeLLMGateway()


def provide_http_tool_client() -> HttpToolClient:
    return HttpxToolClient()


def provide_mcp_tool_client() -> McpToolClient:
    return JsonRpcMcpToolClient()


def provide_execution_engine(
    llm: Annotated[LLMGateway, Depends(provide_llm_gateway)],
    http_client: Annotated[HttpToolClient, Depends(provide_http_tool_client)],
    mcp_client: Annotated[McpToolClient, Depends(provide_mcp_tool_client)],
) -> ExecutionEngine:
    settings = get_settings()
    if settings.execution.engine == "temporal":
        # Imported lazily so the default local path never imports temporalio.
        from app.infrastructure.execution.temporal.engine import TemporalExecutionEngine

        return TemporalExecutionEngine(settings.temporal)
    invoker = CompositeToolInvoker(
        builtin=BuiltinToolInvoker(llm),
        http=HttpToolInvoker(http_client),
        mcp=McpToolInvoker(mcp_client),
    )
    return LocalExecutionEngine(invoker, max_concurrency=settings.execution.max_concurrency)


def provide_execute_run_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
    engine: Annotated[ExecutionEngine, Depends(provide_execution_engine)],
    publisher: Annotated[EventPublisher, Depends(provide_publisher)],
) -> ExecuteRunHandler:
    return ExecuteRunHandler(uow_factory, engine, publisher)


def provide_get_run_execution_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
) -> GetRunExecutionHandler:
    return GetRunExecutionHandler(uow_factory)


# --- governance handlers ---
def provide_policy_decision_point() -> PolicyDecisionPoint:
    policy = get_settings().policy
    if policy.engine == "opa":
        # Imported lazily so the default local path never imports httpx for OPA.
        from app.infrastructure.governance.opa_policy import OpaPolicyDecisionPoint

        return OpaPolicyDecisionPoint(
            base_url=policy.opa_url,
            decision_path=policy.opa_decision_path,
            timeout_seconds=policy.opa_timeout_seconds,
            fail_closed=policy.opa_fail_closed,
        )
    return LocalPolicyEvaluator(
        require_approval_for_high_priority=policy.require_approval_for_high_priority,
        require_approval_for_external_tools=policy.require_approval_for_external_tools,
        denied_tool_kinds=policy.denied_tool_kinds,
    )


def provide_submit_run_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
    policy: Annotated[PolicyDecisionPoint, Depends(provide_policy_decision_point)],
    executor: Annotated[ExecuteRunHandler, Depends(provide_execute_run_handler)],
    publisher: Annotated[EventPublisher, Depends(provide_publisher)],
) -> SubmitRunHandler:
    return SubmitRunHandler(uow_factory, policy, executor, publisher)


def provide_approve_request_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
    executor: Annotated[ExecuteRunHandler, Depends(provide_execute_run_handler)],
) -> ApproveRequestHandler:
    return ApproveRequestHandler(uow_factory, executor)


def provide_reject_request_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
    publisher: Annotated[EventPublisher, Depends(provide_publisher)],
) -> RejectRequestHandler:
    return RejectRequestHandler(uow_factory, publisher)


def provide_get_approval_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
) -> GetApprovalHandler:
    return GetApprovalHandler(uow_factory)


def provide_list_approvals_handler(
    uow_factory: Annotated[UnitOfWorkFactory, Depends(provide_uow_factory)],
) -> ListApprovalsHandler:
    return ListApprovalsHandler(uow_factory)
