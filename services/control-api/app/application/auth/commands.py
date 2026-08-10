"""Auth commands."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RegisterTenant:
    tenant_name: str
    email: str
    password: str


@dataclass(frozen=True, slots=True)
class Login:
    email: str
    password: str


@dataclass(frozen=True, slots=True)
class RefreshTokens:
    refresh_token: str


@dataclass(frozen=True, slots=True)
class Logout:
    refresh_token: str
