"""DTOs for the members read surface."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MemberDTO:
    user_id: str
    email: str
    roles: list[str]
