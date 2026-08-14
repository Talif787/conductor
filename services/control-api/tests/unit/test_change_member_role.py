"""Unit tests for changing a member's role."""

from __future__ import annotations

import pytest

from app.application.members.command_handlers import AddMemberHandler, ChangeMemberRoleHandler
from app.application.members.commands import AddMember, ChangeMemberRole
from app.application.members.queries import ListMembers
from app.application.members.query_handlers import ListMembersHandler
from app.domain.identity.entities import Membership, Tenant, User
from app.domain.identity.errors import CannotChangeOwnerRoleError, MemberNotFoundError
from app.domain.identity.roles import Role
from app.domain.identity.value_objects import Email
from app.domain.shared.identifiers import UserId
from app.infrastructure.persistence.in_memory import InMemoryDatabase, InMemoryUnitOfWork


class _FakeHasher:
    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, hashed: str, password: str) -> bool:
        return hashed == f"hashed:{password}"


@pytest.fixture
def uow_factory():
    db = InMemoryDatabase()
    return lambda: InMemoryUnitOfWork(db)


async def _seed_owner(uow_factory) -> tuple[str, str]:
    """Create a tenant + owner; return (tenant_id, owner_user_id)."""
    async with uow_factory() as uow:
        tenant = Tenant.create("Acme")
        owner = User.create(Email("owner@acme.test"), "h")
        await uow.tenants.add(tenant)
        await uow.users.add(owner)
        await uow.flush()
        await uow.memberships.add(Membership.create(owner.id, tenant.id, Role.OWNER))
        await uow.commit()
        return str(tenant.id), str(owner.id)


async def _add_viewer(uow_factory, tenant_id: str) -> str:
    member = await AddMemberHandler(uow_factory, _FakeHasher()).handle(
        AddMember(
            tenant_id=tenant_id,
            email="viewer@acme.test",
            password="temp-pass-123",
            role="viewer",
        )
    )
    return member.user_id


async def test_changes_role(uow_factory) -> None:
    tenant_id, _ = await _seed_owner(uow_factory)
    viewer_id = await _add_viewer(uow_factory, tenant_id)

    result = await ChangeMemberRoleHandler(uow_factory).handle(
        ChangeMemberRole(tenant_id=tenant_id, user_id=viewer_id, role="author")
    )
    assert result.roles == ["author"]

    listed = await ListMembersHandler(uow_factory).handle(ListMembers(tenant_id=tenant_id))
    changed = next(m for m in listed if m.user_id == viewer_id)
    assert changed.roles == ["author"]


async def test_unknown_member_raises(uow_factory) -> None:
    tenant_id, _ = await _seed_owner(uow_factory)
    with pytest.raises(MemberNotFoundError):
        await ChangeMemberRoleHandler(uow_factory).handle(
            ChangeMemberRole(tenant_id=tenant_id, user_id=str(UserId.new()), role="viewer")
        )


async def test_owner_role_is_immutable(uow_factory) -> None:
    tenant_id, owner_id = await _seed_owner(uow_factory)
    with pytest.raises(CannotChangeOwnerRoleError):
        await ChangeMemberRoleHandler(uow_factory).handle(
            ChangeMemberRole(tenant_id=tenant_id, user_id=owner_id, role="viewer")
        )
