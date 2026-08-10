"""RFC 7807 problem+json error handling."""

from __future__ import annotations

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.domain.identity.errors import (
    AuthenticationError,
    EmailAlreadyExistsError,
    IdentityError,
    InvalidCredentialsError,
    PermissionDeniedError,
    RefreshTokenInvalidError,
    TokenReuseError,
)
from app.domain.run.errors import DomainError, InvalidStateTransitionError, RunNotFoundError
from app.domain.tools.errors import ToolError, ToolNameConflictError, ToolNotFoundError
from app.domain.workflows.errors import (
    InvalidWorkflowStateError,
    WorkflowError,
    WorkflowNameConflictError,
    WorkflowNotFoundError,
    WorkflowNotPublishedError,
    WorkflowValidationError,
    WorkflowVersionNotFoundError,
)

logger = structlog.get_logger(__name__)

_PROBLEM_BASE = "https://errors.conductor.dev"
_CONTENT_TYPE = "application/problem+json"
_WWW_AUTH = {"WWW-Authenticate": "Bearer"}


def _problem(
    status: int,
    title: str,
    detail: str,
    request: Request,
    kind: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type=_CONTENT_TYPE,
        headers=headers,
        content={
            "type": f"{_PROBLEM_BASE}/{kind}",
            "title": title,
            "status": status,
            "detail": detail,
            "instance": str(request.url.path),
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RunNotFoundError)
    async def _handle_not_found(request: Request, exc: RunNotFoundError) -> JSONResponse:
        return _problem(404, "Run not found", str(exc), request, "run-not-found")

    @app.exception_handler(InvalidStateTransitionError)
    async def _handle_transition(
        request: Request, exc: InvalidStateTransitionError
    ) -> JSONResponse:
        return _problem(409, "Invalid state transition", str(exc), request, "invalid-transition")

    @app.exception_handler(EmailAlreadyExistsError)
    async def _handle_email_exists(request: Request, exc: EmailAlreadyExistsError) -> JSONResponse:
        return _problem(409, "Email already registered", str(exc), request, "email-exists")

    @app.exception_handler(InvalidCredentialsError)
    async def _handle_bad_credentials(
        request: Request, exc: InvalidCredentialsError
    ) -> JSONResponse:
        return _problem(401, "Authentication failed", str(exc), request, "invalid-credentials")

    @app.exception_handler(AuthenticationError)
    async def _handle_auth(request: Request, exc: AuthenticationError) -> JSONResponse:
        return _problem(
            401, "Not authenticated", str(exc), request, "not-authenticated", headers=_WWW_AUTH
        )

    @app.exception_handler(RefreshTokenInvalidError)
    async def _handle_refresh_invalid(
        request: Request, exc: RefreshTokenInvalidError
    ) -> JSONResponse:
        return _problem(401, "Invalid refresh token", str(exc), request, "invalid-refresh-token")

    @app.exception_handler(TokenReuseError)
    async def _handle_token_reuse(request: Request, exc: TokenReuseError) -> JSONResponse:
        return _problem(401, "Refresh token reuse detected", str(exc), request, "token-reuse")

    @app.exception_handler(PermissionDeniedError)
    async def _handle_permission(request: Request, exc: PermissionDeniedError) -> JSONResponse:
        return _problem(403, "Permission denied", str(exc), request, "permission-denied")

    @app.exception_handler(IdentityError)
    async def _handle_identity(request: Request, exc: IdentityError) -> JSONResponse:
        return _problem(400, "Identity error", str(exc), request, "identity-error")

    @app.exception_handler(ToolNotFoundError)
    async def _handle_tool_missing(request: Request, exc: ToolNotFoundError) -> JSONResponse:
        return _problem(404, "Tool not found", str(exc), request, "tool-not-found")

    @app.exception_handler(ToolNameConflictError)
    async def _handle_tool_conflict(request: Request, exc: ToolNameConflictError) -> JSONResponse:
        return _problem(409, "Tool name conflict", str(exc), request, "tool-name-conflict")

    @app.exception_handler(ToolError)
    async def _handle_tool_error(request: Request, exc: ToolError) -> JSONResponse:
        return _problem(400, "Tool error", str(exc), request, "tool-error")

    @app.exception_handler(WorkflowNotFoundError)
    async def _handle_wf_missing(request: Request, exc: WorkflowNotFoundError) -> JSONResponse:
        return _problem(404, "Workflow not found", str(exc), request, "workflow-not-found")

    @app.exception_handler(WorkflowVersionNotFoundError)
    async def _handle_wf_version_missing(
        request: Request, exc: WorkflowVersionNotFoundError
    ) -> JSONResponse:
        return _problem(404, "Workflow version not found", str(exc), request, "version-not-found")

    @app.exception_handler(WorkflowNameConflictError)
    async def _handle_wf_conflict(request: Request, exc: WorkflowNameConflictError) -> JSONResponse:
        return _problem(409, "Workflow name conflict", str(exc), request, "workflow-name-conflict")

    @app.exception_handler(WorkflowNotPublishedError)
    async def _handle_wf_unpublished(
        request: Request, exc: WorkflowNotPublishedError
    ) -> JSONResponse:
        return _problem(409, "Workflow not published", str(exc), request, "workflow-not-published")

    @app.exception_handler(InvalidWorkflowStateError)
    async def _handle_wf_state(request: Request, exc: InvalidWorkflowStateError) -> JSONResponse:
        return _problem(409, "Invalid workflow state", str(exc), request, "invalid-workflow-state")

    @app.exception_handler(WorkflowValidationError)
    async def _handle_wf_validation(request: Request, exc: WorkflowValidationError) -> JSONResponse:
        return _problem(422, "Workflow validation failed", str(exc), request, "workflow-invalid")

    @app.exception_handler(WorkflowError)
    async def _handle_wf_error(request: Request, exc: WorkflowError) -> JSONResponse:
        return _problem(400, "Workflow error", str(exc), request, "workflow-error")

    @app.exception_handler(ValueError)
    async def _handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
        return _problem(400, "Invalid request", str(exc), request, "invalid-value")

    @app.exception_handler(DomainError)
    async def _handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return _problem(400, "Domain rule violation", str(exc), request, "domain-error")

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _problem(
            422, "Request validation failed", str(exc.errors()), request, "validation-error"
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_exception", error=str(exc), path=request.url.path)
        return _problem(
            500, "Internal server error", "An unexpected error occurred.", request, "internal"
        )
