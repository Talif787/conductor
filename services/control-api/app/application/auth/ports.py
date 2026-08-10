"""Ports for password hashing and access-token issuing."""

from __future__ import annotations

import abc
from dataclasses import dataclass

from app.application.auth.principal import Principal


@dataclass(frozen=True, slots=True)
class IssuedAccessToken:
    token: str
    expires_in_seconds: int


class PasswordHasher(abc.ABC):
    @abc.abstractmethod
    def hash(self, plaintext: str) -> str: ...

    @abc.abstractmethod
    def verify(self, hashed: str, plaintext: str) -> bool: ...


class AccessTokenService(abc.ABC):
    @abc.abstractmethod
    def issue(self, principal: Principal) -> IssuedAccessToken: ...

    @abc.abstractmethod
    def decode(self, token: str) -> Principal: ...
