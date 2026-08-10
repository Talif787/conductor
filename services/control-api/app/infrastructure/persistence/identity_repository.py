"""PostgreSQL-backed identity repositories."""

from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.identity.entities import Membership, RefreshToken, Tenant, User
from app.domain.identity.repository import (
    MembershipRepository,
    RefreshTokenRepository,
    TenantRepository,
    UserRepository,
)
from app.domain.identity.value_objects import Email
from app.domain.shared.identifiers import TenantId, UserId
from app.infrastructure.persistence.identity_mappers import (
    membership_to_model,
    model_to_membership,
    model_to_refresh_token,
    model_to_tenant,
    model_to_user,
    refresh_token_to_model,
    tenant_to_model,
    user_to_model,
)
from app.infrastructure.persistence.models import (
    MembershipModel,
    RefreshTokenModel,
    TenantModel,
    UserModel,
)


class SqlAlchemyTenantRepository(TenantRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, tenant: Tenant) -> None:
        self._session.add(tenant_to_model(tenant))

    async def get(self, tenant_id: TenantId) -> Tenant | None:
        model = await self._session.get(TenantModel, tenant_id.value)
        return model_to_tenant(model) if model is not None else None


class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: User) -> None:
        self._session.add(user_to_model(user))

    async def get(self, user_id: UserId) -> User | None:
        model = await self._session.get(UserModel, user_id.value)
        return model_to_user(model) if model is not None else None

    async def find_by_email(self, email: Email) -> User | None:
        stmt = select(UserModel).where(UserModel.email == email.value)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return model_to_user(model) if model is not None else None


class SqlAlchemyMembershipRepository(MembershipRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, membership: Membership) -> None:
        self._session.add(membership_to_model(membership))

    async def find_by_user(self, user_id: UserId) -> list[Membership]:
        stmt = select(MembershipModel).where(MembershipModel.user_id == user_id.value)
        models = (await self._session.execute(stmt)).scalars().all()
        return [model_to_membership(m) for m in models]


class SqlAlchemyRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, token: RefreshToken) -> None:
        self._session.add(refresh_token_to_model(token))

    async def find_by_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return model_to_refresh_token(model) if model is not None else None

    async def mark_used(self, token_id: uuid.UUID) -> None:
        await self._session.execute(
            update(RefreshTokenModel).where(RefreshTokenModel.id == token_id).values(used=True)
        )

    async def revoke_family(self, family_id: uuid.UUID) -> None:
        await self._session.execute(
            update(RefreshTokenModel)
            .where(RefreshTokenModel.family_id == family_id)
            .values(revoked=True)
        )
