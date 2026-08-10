"""LLM gateway adapters: a deterministic fake and a real HTTP client."""

from __future__ import annotations

from app.application.execution.ports import LLMGateway, LLMRequest, LLMResponse
from app.domain.execution.errors import LLMError


class FakeLLMGateway(LLMGateway):
    """Deterministic gateway for local development and tests."""

    async def complete(self, request: LLMRequest) -> LLMResponse:
        preview = request.prompt.strip().replace("\n", " ")[:120]
        return LLMResponse(
            text=f"[fake:{request.model}] {preview}",
            model=request.model,
            usage={"prompt_tokens": len(request.prompt.split())},
        )


class HttpLLMGateway(LLMGateway):
    """Calls an OpenAI-compatible chat-completions endpoint.

    Exercised only with real credentials; the local default is FakeLLMGateway.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int = 30,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds

    async def complete(self, request: LLMRequest) -> LLMResponse:
        import httpx  # lazy import so the module loads without httpx present

        payload = {
            "model": self._model or request.model,
            "messages": [{"role": "user", "content": request.prompt}],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions", json=payload, headers=headers
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise LLMError(f"llm request failed: {exc}") from exc

        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"unexpected llm response shape: {exc}") from exc
        return LLMResponse(
            text=text, model=data.get("model", self._model), usage=data.get("usage", {})
        )
