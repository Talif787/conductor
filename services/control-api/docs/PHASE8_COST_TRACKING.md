# Cost Tracking (Phase 8 follow-on)

This slice adds per-step and per-run LLM cost accounting. It was carved out of
Phase 8 because it touches the LLM gateway and the execution path rather than the
event plumbing, and it builds directly on the execution model that Phase 8 sits
beside. Apply it on a branch off main after Phase 8 is merged.

## How cost flows

The LLM gateway already returns token usage. Gateways report tokens, as real
providers do; turning tokens into dollars is a platform concern, so it happens
outside the gateway:

1. `FakeLLMGateway` returns deterministic `prompt_tokens`, `completion_tokens`,
   and `total_tokens`. `HttpLLMGateway` passes through the provider's `usage`.
2. The `llm` builtin includes that `usage` in its step output, alongside the
   unchanged `completion` and `model` fields.
3. The execution engine reads each step's `usage`, applies `TokenPricing` via
   `estimate_cost_usd`, records `cost_usd` on the step, and sums the steps into
   `total_cost_usd` on the run execution.
4. Both values are persisted (migration 0008) and returned by the execution API.

Steps that do not report usage (echo, uppercase, http, mcp) contribute zero, so
cost is opt-in per tool without special-casing.

## Pricing configuration

Rates are per 1000 tokens and configurable with the `CONDUCTOR_COST_` prefix:

| Setting | Env var | Default |
| --- | --- | --- |
| Prompt rate | `CONDUCTOR_COST_PROMPT_USD_PER_1K` | `0.00015` |
| Completion rate | `CONDUCTOR_COST_COMPLETION_USD_PER_1K` | `0.0006` |

The defaults are illustrative (roughly a small hosted model); set them to match
whatever model you point `HttpLLMGateway` at.

## API

The execution response now carries cost. `GET` for a run execution returns
`total_cost_usd` at the top level and `cost_usd` on each step, so a client can
show both the run total and a per-step breakdown.

## Metrics

The engine increments `conductor_llm_cost_usd_total`, labeled by `model`, by the
estimated dollar cost of each step that incurred one. Combined with the Phase 8
`conductor_events_published_total`, this gives a basic cost-and-throughput view.

## Verification boundary

`tests/unit/test_cost_tracking.py` covers the pricing function, the fake
gateway's usage, the builtin output shape, and the engine's per-step and
run-level aggregation, all without a database. The columns and mappers are
exercised by the execution integration tests.

## Not yet covered

The Temporal execution engine builds its run execution through activities and
does not yet aggregate cost, so runs executed on the Temporal path report
`total_cost_usd` of 0. Wiring cost through the Temporal activities is the next
step, and belongs with the Phase 6 execution code rather than here.
