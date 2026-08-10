"""Auth command handlers: register, login, refresh (with rotation), logout."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

import structlog

from app.application.auth.commands import Login, Logout, RefreshTokens, RegisterTenant
from app.application.auth.dtos import AuthTokensDTO
from app.application.auth.ports import AccessTokenService, PasswordHasher
from app.application.auth.principal import Principal
from app.application.ports import UnitOfWork
from app.domain.identity.entities import Membership, RefreshToken, Tenant, User
from app.domain.identity.errors import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    RefreshTokenInvalidError,
    TokenReuseError,
)
from app.domain.identity.roles import Role
from app.domain.identity.value_objects import Email
from app.domain.shared.identifiers import TenantId, UserId

logger = structlog.get_logger(__name__)

UnitOfWorkFactory = Callable[[], UnitOfWork]
_REFRESH_TOKEN_BYTES = 48


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(UTC)


class _TokenMinter:
    def __init__(self, tokens: AccessTokenService, refresh_ttl_seconds: int) -> None:
        self._tokens = tokens
        self._refresh_ttl = refresh_ttl_seconds

    async def mint(
        self,
        uow: UnitOfWork,
        *,
        user_id: UserId,
        tenant_id: TenantId,
        roles: frozenset[Role],
        family_id: uuid.UUID | None = None,
    ) -> AuthTokensDTO:
        principal = Principal(user_id=user_id, tenant_id=tenant_id, roles=roles)
        access = self._tokens.issue(principal)
        raw_refresh = secrets.token_urlsafe(_REFRESH_TOKEN_BYTES)
        record = RefreshToken.issue(
            user_id=user_id,
            tenant_id=tenant_id,
            token_hash=_hash_token(raw_refresh),
            ttl_seconds=self._refresh_ttl,
            family_id=family_id,
        )
        await uow.refresh_tokens.add(record)
        return AuthTokensDTO(
            access_token=access.token,
            refresh_token=raw_refresh,
            token_type="Bearer",  # noqa: S106
            expires_in=access.expires_in_seconds,
        )


class RegisterTenantHandler:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        hasher: PasswordHasher,
        tokens: AccessTokenService,
        refresh_ttl_seconds: int,
    ) -> None:
        self._uow_factory = uow_factory
        self._hasher = hasher
        self._minter = _TokenMinter(tokens, refresh_ttl_seconds)

    async def handle(self, command: RegisterTenant) -> AuthTokensDTO:
        email = Email(command.email)
        async with self._uow_factory() as uow:
            if await uow.users.find_by_email(email) is not None:
                raise EmailAlreadyExistsError(email.value)
            tenant = Tenant.create(command.tenant_name)
            user = User.create(email, self._hasher.hash(command.password))
            membership = Membership.create(user.id, tenant.id, Role.OWNER)
            await uow.tenants.add(tenant)
            await uow.users.add(user)
            # Flush parents so memberships and refresh tokens satisfy their foreign keys.
            await uow.flush()
            await uow.memberships.add(membership)
            tokens = await self._minter.mint(
                uow, user_id=user.id, tenant_id=tenant.id, roles=frozenset({membership.role})
            )
            await uow.commit()
        logger.info("auth.registered", tenant_id=str(tenant.id), user_id=str(user.id))
        return tokens


class LoginHandler:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        hasher: PasswordHasher,
        tokens: AccessTokenService,
        refresh_ttl_seconds: int,
    ) -> None:
        self._uow_factory = uow_factory
        self._hasher = hasher
        self._minter = _TokenMinter(tokens, refresh_ttl_seconds)

    async def handle(self, command: Login) -> AuthTokensDTO:
        email = Email(command.email)
        async with self._uow_factory() as uow:
            user = await uow.users.find_by_email(email)
            if user is None or not self._hasher.verify(user.password_hash, command.password):
                raise InvalidCredentialsError()
            memberships = await uow.memberships.find_by_user(user.id)
            if not memberships:
                raise InvalidCredentialsError("no tenant membership")
            membership = memberships[0]
            tokens = await self._minter.mint(
                uow,
                user_id=user.id,
                tenant_id=membership.tenant_id,
                roles=frozenset({membership.role}),
            )
            await uow.commit()
        logger.info("auth.login", user_id=str(user.id))
        return tokens


class RefreshTokensHandler:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        tokens: AccessTokenService,
        refresh_ttl_seconds: int,
    ) -> None:
        self._uow_factory = uow_factory
        self._minter = _TokenMinter(tokens, refresh_ttl_seconds)

    async def handle(self, command: RefreshTokens) -> AuthTokensDTO:
        token_hash = _hash_token(command.refresh_token)
        async with self._uow_factory() as uow:
            record = await uow.refresh_tokens.find_by_hash(token_hash)
            if record is None:
                raise RefreshTokenInvalidError("unknown refresh token")
            if not record.is_active:
                await uow.refresh_tokens.revoke_family(record.family_id)
                await uow.commit()
                logger.warning("auth.refresh.reuse_detected", family_id=str(record.family_id))
                raise TokenReuseError("refresh token reuse detected")
            if record.is_expired(_utcnow()):
                raise RefreshTokenInvalidError("refresh token expired")
            memberships = await uow.memberships.find_by_user(record.user_id)
            roles = frozenset(m.role for m in memberships if m.tenant_id == record.tenant_id)
            if not roles:
                raise RefreshTokenInvalidError("membership no longer exists")
            await uow.refresh_tokens.mark_used(record.id.value)
            tokens = await self._minter.mint(
                uow,
                user_id=record.user_id,
                tenant_id=record.tenant_id,
                roles=roles,
                family_id=record.family_id,
            )
            await uow.commit()
        return tokens


class LogoutHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, command: Logout) -> None:
        token_hash = _hash_token(command.refresh_token)
        async with self._uow_factory() as uow:
            record = await uow.refresh_tokens.find_by_hash(token_hash)
            if record is not None:
                await uow.refresh_tokens.revoke_family(record.family_id)
                await uow.commit()
