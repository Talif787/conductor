from __future__ import annotations

from app.application.governance.policy import PolicyQuery, PolicyToolRef
from app.domain.governance.value_objects import PolicyEffect
from app.infrastructure.governance.local_policy import LocalPolicyEvaluator

_BUILTIN = PolicyToolRef(id="1", name="echo", kind="builtin")
_HTTP = PolicyToolRef(id="2", name="fetch", kind="http")
_MCP = PolicyToolRef(id="3", name="search", kind="mcp")


def _query(priority: str = "normal", tools=()) -> PolicyQuery:
    return PolicyQuery(
        tenant_id="t",
        principal_id="u",
        roles=["operator"],
        run_id="r",
        goal="g",
        priority=priority,
        parameters={},
        workflow_id="w",
        workflow_version="1",
        tools=list(tools),
    )


async def test_default_evaluator_allows_everything() -> None:
    decision = await LocalPolicyEvaluator().evaluate(_query(priority="high", tools=(_HTTP, _MCP)))
    assert decision.effect is PolicyEffect.ALLOW


async def test_high_priority_requires_approval() -> None:
    ev = LocalPolicyEvaluator(require_approval_for_high_priority=True)
    assert (await ev.evaluate(_query("high", (_BUILTIN,)))).effect is (
        PolicyEffect.REQUIRE_APPROVAL
    )
    assert (await ev.evaluate(_query("normal", (_BUILTIN,)))).effect is PolicyEffect.ALLOW


async def test_external_tools_require_approval() -> None:
    ev = LocalPolicyEvaluator(require_approval_for_external_tools=True)
    decision = await ev.evaluate(_query(tools=(_BUILTIN, _HTTP)))
    assert decision.effect is PolicyEffect.REQUIRE_APPROVAL
    assert "http" in decision.reason
    assert (await ev.evaluate(_query(tools=(_BUILTIN,)))).effect is PolicyEffect.ALLOW


async def test_denied_kind_takes_precedence() -> None:
    ev = LocalPolicyEvaluator(require_approval_for_high_priority=True, denied_tool_kinds=("mcp",))
    decision = await ev.evaluate(_query("high", (_BUILTIN, _MCP)))
    assert decision.effect is PolicyEffect.DENY
    assert "mcp" in decision.reason


async def test_query_serializes_for_opa() -> None:
    doc = _query(tools=(_HTTP,)).to_input()
    assert doc["priority"] == "normal"
    assert doc["tools"][0]["kind"] == "http"
    assert isinstance(doc["roles"], list)
