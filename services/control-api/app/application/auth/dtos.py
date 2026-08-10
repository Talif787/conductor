"""DTOs returned by the auth application layer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuthTokensDTO:
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


@dataclass(frozen=True, slots=True)
class PrincipalDTO:
    user_id: str
    tenant_id: str
    roles: list[str]
    permissions: list[str]
