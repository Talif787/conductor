"""RFC 7807 problem+json error handling."""
from __future__ import annotations

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.domain.run.errors import DomainError, InvalidStateTransition, RunNotFound

logger = structlog.get_logger(__name__)

_PROBLEM_BASE = "https://errors.conductor.dev"
_CONTENT_TYPE = "application/problem+json"


def _problem(status: int, title: str, detail: str, request: Request, kind: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type=_CONTENT_TYPE,
        content={
            "type": f"{_PROBLEM_BASE}/{kind}",
            "title": title,
            "status": status,
            "detail": detail,
            "instance": str(request.url.path),
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RunNotFound)
    async def _handle_not_found(request: Request, exc: RunNotFound) -> JSONResponse:
        return _problem(404, "Run not found", str(exc), request, "run-not-found")

    @app.exception_handler(InvalidStateTransition)
    async def _handle_transition(
        request: Request, exc: InvalidStateTransition
    ) -> JSONResponse:
        return _problem(409, "Invalid state transition", str(exc), request, "invalid-transition")

    @app.exception_handler(ValueError)
    async def _handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
        return _problem(400, "Invalid request", str(exc), request, "invalid-value")

    @app.exception_handler(DomainError)
    async def _handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return _problem(400, "Domain rule violation", str(exc), request, "domain-error")

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _problem(
            422, "Request validation failed", str(exc.errors()), request, "validation-error"
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_exception", error=str(exc), path=request.url.path)
        return _problem(
            500, "Internal server error", "An unexpected error occurred.", request, "internal"
        )
