"""Open Policy Agent decision point (opt-in).

Posts the policy query as an OPA input document and maps the returned decision
document to a PolicyDecision. This is the only governance adapter that reaches an
external service, so it is selected explicitly via configuration and httpx is
imported lazily. The Rego policy is expected to return a document shaped like
{"result": {"effect": "allow|deny|require_approval", "reason": "..."}}.
"""

from __future__ import annotations

from typing import Any

from app.application.governance.policy import (
    PolicyDecision,
    PolicyDecisionPoint,
    PolicyQuery,
)
from app.domain.governance.value_objects import PolicyEffect

_EFFECTS = {e.value: e for e in PolicyEffect}


class OpaPolicyDecisionPoint(PolicyDecisionPoint):
    def __init__(
        self,
        *,
        base_url: str,
        decision_path: str,
        timeout_seconds: float = 5.0,
        fail_closed: bool = True,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/{decision_path.lstrip('/')}"
        self._timeout = timeout_seconds
        self._fail_closed = fail_closed

    async def evaluate(self, query: PolicyQuery) -> PolicyDecision:
        import httpx

        payload = {"input": query.to_input()}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(self._url, json=payload)
                response.raise_for_status()
                body = response.json()
        except Exception as exc:  # noqa: BLE001
            if self._fail_closed:
                return PolicyDecision(PolicyEffect.DENY, f"policy engine unavailable: {exc}")
            return PolicyDecision(PolicyEffect.ALLOW, "policy engine unavailable (fail open)")
        return self._parse(body.get("result"))

    @staticmethod
    def _parse(result: Any) -> PolicyDecision:
        if result is None:
            return PolicyDecision(PolicyEffect.DENY, "policy returned no decision")
        if isinstance(result, bool):
            return PolicyDecision(
                PolicyEffect.ALLOW if result else PolicyEffect.DENY,
                "" if result else "denied by policy",
            )
        if isinstance(result, dict):
            raw = str(result.get("effect", "")).lower()
            effect = _EFFECTS.get(raw, PolicyEffect.DENY)
            reason = str(result.get("reason", "")) or (
                "" if effect is PolicyEffect.ALLOW else "denied by policy"
            )
            return PolicyDecision(effect, reason)
        return PolicyDecision(PolicyEffect.DENY, "unrecognized policy decision")
