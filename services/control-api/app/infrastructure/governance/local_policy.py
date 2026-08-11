"""In-process policy evaluator (the default decision point).

Deterministic and dependency free, driven by configuration. With no rules
enabled it allows every run, so governance is opt-in and existing behavior is
unchanged until a rule is configured.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.application.governance.policy import (
    PolicyDecision,
    PolicyDecisionPoint,
    PolicyQuery,
)
from app.domain.governance.value_objects import PolicyEffect

_EXTERNAL_KINDS = ("http", "mcp")


class LocalPolicyEvaluator(PolicyDecisionPoint):
    def __init__(
        self,
        *,
        require_approval_for_high_priority: bool = False,
        require_approval_for_external_tools: bool = False,
        denied_tool_kinds: Iterable[str] = (),
    ) -> None:
        self._high_priority = require_approval_for_high_priority
        self._external_tools = require_approval_for_external_tools
        self._denied_kinds = frozenset(denied_tool_kinds)

    async def evaluate(self, query: PolicyQuery) -> PolicyDecision:
        denied = sorted({t.kind for t in query.tools if t.kind in self._denied_kinds})
        if denied:
            return PolicyDecision(
                PolicyEffect.DENY, f"tool kind(s) not permitted: {', '.join(denied)}"
            )

        reasons: list[str] = []
        if self._high_priority and query.priority == "high":
            reasons.append("high priority runs require approval")
        if self._external_tools:
            external = sorted({t.kind for t in query.tools if t.kind in _EXTERNAL_KINDS})
            if external:
                reasons.append(f"external tools require approval: {', '.join(external)}")
        if reasons:
            return PolicyDecision(PolicyEffect.REQUIRE_APPROVAL, "; ".join(reasons))
        return PolicyDecision(PolicyEffect.ALLOW)
