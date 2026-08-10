"""Mapping between identity ORM rows and domain entities."""

from __future__ import annotations

from app.domain.identity.entities import Membership, RefreshToken, Tenant, User
from app.domain.identity.roles import Role
from app.domain.identity.value_objects import Email
from app.domain.shared.identifiers import (
    MembershipId,
    RefreshTokenId,
    TenantId,
    UserId,
)
from app.infrastructure.persistence.models import (
    MembershipModel,
    RefreshTokenModel,
    TenantModel,
    UserModel,
)


def tenant_to_model(tenant: Tenant) -> TenantModel:
    return TenantModel(id=tenant.id.value, name=tenant.name, created_at=tenant.created_at)


def model_to_tenant(model: TenantModel) -> Tenant:
    return Tenant(id=TenantId(model.id), name=model.name, created_at=model.created_at)


def user_to_model(user: User) -> UserModel:
    return UserModel(
        id=user.id.value,
        email=user.email.value,
        password_hash=user.password_hash,
        created_at=user.created_at,
    )


def model_to_user(model: UserModel) -> User:
    return User(
        id=UserId(model.id),
        email=Email(model.email),
        password_hash=model.password_hash,
        created_at=model.created_at,
    )


def membership_to_model(membership: Membership) -> MembershipModel:
    return MembershipModel(
        id=membership.id.value,
        user_id=membership.user_id.value,
        tenant_id=membership.tenant_id.value,
        role=membership.role.value,
        created_at=membership.created_at,
    )


def model_to_membership(model: MembershipModel) -> Membership:
    return Membership(
        id=MembershipId(model.id),
        user_id=UserId(model.user_id),
        tenant_id=TenantId(model.tenant_id),
        role=Role(model.role),
        created_at=model.created_at,
    )


def refresh_token_to_model(token: RefreshToken) -> RefreshTokenModel:
    return RefreshTokenModel(
        id=token.id.value,
        family_id=token.family_id,
        user_id=token.user_id.value,
        tenant_id=token.tenant_id.value,
        token_hash=token.token_hash,
        issued_at=token.issued_at,
        expires_at=token.expires_at,
        used=token.used,
        revoked=token.revoked,
    )


def model_to_refresh_token(model: RefreshTokenModel) -> RefreshToken:
    return RefreshToken(
        id=RefreshTokenId(model.id),
        family_id=model.family_id,
        user_id=UserId(model.user_id),
        tenant_id=TenantId(model.tenant_id),
        token_hash=model.token_hash,
        issued_at=model.issued_at,
        expires_at=model.expires_at,
        used=model.used,
        revoked=model.revoked,
    )
