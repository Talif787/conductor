from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GetRunStats:
    tenant_id: str


@dataclass(frozen=True, slots=True)
class ListRunViews:
    tenant_id: str
    limit: int = 50
