"""Token pricing and cost estimation for LLM usage.

Gateways report token counts (as providers do); turning tokens into dollars is
a platform concern, so pricing lives here and is applied by the execution
engine. Rates are per 1000 tokens and configurable via CostSettings.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TokenPricing:
    prompt_usd_per_1k: float = 0.00015
    completion_usd_per_1k: float = 0.0006


def estimate_cost_usd(usage: Mapping[str, int], pricing: TokenPricing) -> float:
    prompt = int(usage.get("prompt_tokens", 0) or 0)
    completion = int(usage.get("completion_tokens", 0) or 0)
    cost = (
        prompt / 1000 * pricing.prompt_usd_per_1k
        + completion / 1000 * pricing.completion_usd_per_1k
    )
    return round(cost, 6)
