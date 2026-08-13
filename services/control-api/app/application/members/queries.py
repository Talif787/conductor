"""Queries for listing workspace members."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ListMembers:
    tenant_id: str
