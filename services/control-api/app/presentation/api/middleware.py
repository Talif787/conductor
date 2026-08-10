"""Correlation-id and request-logging/metrics middleware."""
from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.infrastructure.observability.logging import bind_correlation_id, clear_request_context
from app.infrastructure.observability.metrics import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
)

_CORRELATION_HEADER = "X-Request-Id"
logger = structlog.get_logger("http")


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        correlation_id = request.headers.get(_CORRELATION_HEADER) or str(uuid.uuid4())
        bind_correlation_id(correlation_id)
        route = request.scope.get("route")
        path_label = getattr(route, "path", request.url.path)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            duration = time.perf_counter() - start
            HTTP_REQUEST_DURATION_SECONDS.labels(request.method, path_label).observe(duration)
        response.headers[_CORRELATION_HEADER] = correlation_id
        HTTP_REQUESTS_TOTAL.labels(request.method, path_label, str(response.status_code)).inc()
        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(duration * 1000, 2),
        )
        clear_request_context()
        return response
