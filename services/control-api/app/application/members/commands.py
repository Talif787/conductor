"""Commands for the members write surface."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AddMember:
    tenant_id: str
    email: str
    password: str
    role: str
