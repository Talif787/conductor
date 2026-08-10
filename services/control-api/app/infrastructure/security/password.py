"""Argon2id password hasher."""

from __future__ import annotations

from argon2 import PasswordHasher as _Argon2PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.application.auth.ports import PasswordHasher


class Argon2PasswordHasher(PasswordHasher):
    def __init__(self) -> None:
        self._ph = _Argon2PasswordHasher()

    def hash(self, plaintext: str) -> str:
        return self._ph.hash(plaintext)

    def verify(self, hashed: str, plaintext: str) -> bool:
        try:
            return self._ph.verify(hashed, plaintext)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False
