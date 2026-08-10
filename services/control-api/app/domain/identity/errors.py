"""Errors for the Identity bounded context."""

from __future__ import annotations


class IdentityError(Exception):
    """Base class for identity and authentication failures."""


class EmailAlreadyExistsError(IdentityError):
    def __init__(self, email: str) -> None:
        super().__init__(f"an account already exists for '{email}'")
        self.email = email


class InvalidCredentialsError(IdentityError):
    def __init__(self, detail: str = "invalid email or password") -> None:
        super().__init__(detail)


class AuthenticationError(IdentityError):
    """The access token is missing, malformed, or invalid."""


class RefreshTokenInvalidError(IdentityError):
    """The refresh token is unknown or expired."""


class TokenReuseError(IdentityError):
    """A refresh token that was already rotated or revoked was presented."""


class PermissionDeniedError(IdentityError):
    def __init__(self, permission: str) -> None:
        super().__init__(f"missing required permission '{permission}'")
        self.permission = permission
