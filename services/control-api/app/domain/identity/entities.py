"""Entities for the Identity bounded context."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.domain.identity.roles import Role
from app.domain.identity.value_objects import Email
from app.domain.shared.identifiers import (
    MembershipId,
    RefreshTokenId,
    TenantId,
    UserId,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class Tenant:
    id: TenantId
    name: str
    created_at: datetime

    @classmethod
    def create(cls, name: str) -> Tenant:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("tenant name must not be empty")
        return cls(id=TenantId.new(), name=cleaned, created_at=_utcnow())


@dataclass
class User:
    id: UserId
    email: Email
    password_hash: str
    created_at: datetime

    @classmethod
    def create(cls, email: Email, password_hash: str) -> User:
        return cls(id=UserId.new(), email=email, password_hash=password_hash, created_at=_utcnow())


@dataclass
class Membership:
    id: MembershipId
    user_id: UserId
    tenant_id: TenantId
    role: Role
    created_at: datetime

    @classmethod
    def create(cls, user_id: UserId, tenant_id: TenantId, role: Role) -> Membership:
        return cls(
            id=MembershipId.new(),
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            created_at=_utcnow(),
        )


@dataclass
class RefreshToken:
    id: RefreshTokenId
    family_id: uuid.UUID
    user_id: UserId
    tenant_id: TenantId
    token_hash: str
    issued_at: datetime
    expires_at: datetime
    used: bool = False
    revoked: bool = False

    @classmethod
    def issue(
        cls,
        *,
        user_id: UserId,
        tenant_id: TenantId,
        token_hash: str,
        ttl_seconds: int,
        family_id: uuid.UUID | None = None,
    ) -> RefreshToken:
        now = _utcnow()
        return cls(
            id=RefreshTokenId.new(),
            family_id=family_id or uuid.uuid4(),
            user_id=user_id,
            tenant_id=tenant_id,
            token_hash=token_hash,
            issued_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )

    @property
    def is_active(self) -> bool:
        return not self.used and not self.revoked

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at
