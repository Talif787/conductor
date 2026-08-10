from __future__ import annotations

import pytest

from app.application.auth.command_handlers import (
    LoginHandler,
    LogoutHandler,
    RefreshTokensHandler,
    RegisterTenantHandler,
)
from app.application.auth.commands import Login, Logout, RefreshTokens, RegisterTenant
from app.application.auth.ports import AccessTokenService, IssuedAccessToken, PasswordHasher
from app.domain.identity.errors import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    RefreshTokenInvalidError,
    TokenReuseError,
)
from app.infrastructure.persistence.in_memory import InMemoryDatabase, InMemoryUnitOfWork

_TTL = 3600


class _Hasher(PasswordHasher):
    def hash(self, plaintext: str) -> str:
        return "h$" + plaintext

    def verify(self, hashed: str, plaintext: str) -> bool:
        return hashed == "h$" + plaintext


class _Tokens(AccessTokenService):
    def issue(self, principal) -> IssuedAccessToken:
        return IssuedAccessToken(token="access-" + str(principal.user_id), expires_in_seconds=900)

    def decode(self, token):  # pragma: no cover - unused in these tests
        raise NotImplementedError


@pytest.fixture
def factory():
    db = InMemoryDatabase()
    return lambda: InMemoryUnitOfWork(db)


@pytest.mark.asyncio
async def test_register_creates_owner_and_tokens(factory) -> None:
    handler = RegisterTenantHandler(factory, _Hasher(), _Tokens(), _TTL)
    tokens = await handler.handle(
        RegisterTenant(tenant_name="Acme", email="owner@acme.com", password="password123")
    )
    assert tokens.token_type == "Bearer"
    assert tokens.access_token and tokens.refresh_token


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email(factory) -> None:
    handler = RegisterTenantHandler(factory, _Hasher(), _Tokens(), _TTL)
    await handler.handle(RegisterTenant("Acme", "owner@acme.com", "password123"))
    with pytest.raises(EmailAlreadyExistsError):
        await handler.handle(RegisterTenant("Acme2", "OWNER@acme.com", "password456"))


@pytest.mark.asyncio
async def test_login_rejects_bad_password(factory) -> None:
    reg = RegisterTenantHandler(factory, _Hasher(), _Tokens(), _TTL)
    await reg.handle(RegisterTenant("Acme", "owner@acme.com", "password123"))
    login = LoginHandler(factory, _Hasher(), _Tokens(), _TTL)
    with pytest.raises(InvalidCredentialsError):
        await login.handle(Login(email="owner@acme.com", password="wrong"))


@pytest.mark.asyncio
async def test_refresh_rotation_and_reuse_detection(factory) -> None:
    reg = RegisterTenantHandler(factory, _Hasher(), _Tokens(), _TTL)
    first = await reg.handle(RegisterTenant("Acme", "owner@acme.com", "password123"))
    refresh = RefreshTokensHandler(factory, _Tokens(), _TTL)

    rotated = await refresh.handle(RefreshTokens(refresh_token=first.refresh_token))
    assert rotated.refresh_token != first.refresh_token

    # presenting the already-rotated token is a reuse: family is revoked
    with pytest.raises(TokenReuseError):
        await refresh.handle(RefreshTokens(refresh_token=first.refresh_token))

    # the rotated token is now revoked as part of the family
    with pytest.raises((TokenReuseError, RefreshTokenInvalidError)):
        await refresh.handle(RefreshTokens(refresh_token=rotated.refresh_token))


@pytest.mark.asyncio
async def test_logout_revokes_refresh(factory) -> None:
    reg = RegisterTenantHandler(factory, _Hasher(), _Tokens(), _TTL)
    tokens = await reg.handle(RegisterTenant("Acme", "owner@acme.com", "password123"))
    await LogoutHandler(factory).handle(Logout(refresh_token=tokens.refresh_token))
    with pytest.raises((TokenReuseError, RefreshTokenInvalidError)):
        await RefreshTokensHandler(factory, _Tokens(), _TTL).handle(
            RefreshTokens(refresh_token=tokens.refresh_token)
        )
