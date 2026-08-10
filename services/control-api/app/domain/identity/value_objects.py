"""Value objects for the Identity bounded context."""

from __future__ import annotations

from dataclasses import dataclass

_MAX_EMAIL_LENGTH = 320


@dataclass(frozen=True, slots=True)
class Email:
    value: str

    def __post_init__(self) -> None:
        cleaned = self.value.strip().lower()
        if "@" not in cleaned or len(cleaned) < 3 or len(cleaned) > _MAX_EMAIL_LENGTH:
            raise ValueError("invalid email address")
        local, _, domain = cleaned.partition("@")
        if not local or "." not in domain:
            raise ValueError("invalid email address")
        object.__setattr__(self, "value", cleaned)

    def __str__(self) -> str:
        return self.value
