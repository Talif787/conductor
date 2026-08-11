"""httpx-backed HttpToolClient. Exercised against real endpoints."""

from __future__ import annotations

from app.application.execution.tool_clients import (
    HttpToolClient,
    HttpToolRequest,
    HttpToolResponse,
)
from app.domain.execution.errors import ToolExecutionError


class HttpxToolClient(HttpToolClient):
    async def send(self, request: HttpToolRequest) -> HttpToolResponse:
        import httpx  # lazy import so the module loads without httpx present

        try:
            async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
                response = await client.request(
                    request.method,
                    request.url,
                    headers=request.headers or None,
                    json=request.body,
                )
        except httpx.HTTPError as exc:
            raise ToolExecutionError(f"http request failed: {exc}") from exc

        body: dict | None
        try:
            parsed = response.json()
            body = parsed if isinstance(parsed, dict) else {"result": parsed}
        except ValueError:
            body = None
        return HttpToolResponse(status_code=response.status_code, body=body, text=response.text)
