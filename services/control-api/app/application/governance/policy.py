"""Policy decision port and its query and decision value objects.

The port is provider agnostic: a LocalPolicyEvaluator (in process, default) and
an OpaPolicyDecisionPoint (opt-in, HTTP to Open Policy Agent) both implement it.
The query is a plain, serializable structure so it can be sent to OPA as JSON.
"""

from __future__ import annotations

import abc
from dataclasses import asdict, dataclass, field
from typing import Any

from app.domain.governance.value_objects import PolicyEffect


@dataclass(frozen=True, slots=True)
class PolicyToolRef:
    id: str
    name: str
    kind: str


@dataclass(frozen=True, slots=True)
class PolicyQuery:
    tenant_id: str
    principal_id: str
    roles: list[str]
    run_id: str
    goal: str
    priority: str
    parameters: dict[str, Any]
    workflow_id: str | None
    workflow_version: str | None
    tools: list[PolicyToolRef] = field(default_factory=list)

    def to_input(self) -> dict[str, Any]:
        """Serialize to the OPA input document shape."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    effect: PolicyEffect
    reason: str = ""

    @property
    def is_allowed(self) -> bool:
        return self.effect is PolicyEffect.ALLOW


class PolicyDecisionPoint(abc.ABC):
    @abc.abstractmethod
    async def evaluate(self, query: PolicyQuery) -> PolicyDecision: ...
