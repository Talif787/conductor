"""Unit tests for listing workspace members."""

from __future__ import annotations

import pytest

from app.application.members.queries import ListMembers
from app.application.members.query_handlers import ListMembersHandler
from app.domain.identity.entities import Membership, Tenant, User
from app.domain.identity.roles import Role
from app.domain.identity.value_objects import Email
from app.infrastructure.persistence.in_memory import InMemoryDatabase, InMemoryUnitOfWork


@pytest.fixture
def uow_factory():
    db = InMemoryDatabase()
    return lambda: InMemoryUnitOfWork(db)


async def _seed(uow_factory) -> str:
    async with uow_factory() as uow:
        tenant = Tenant.create("Acme")
        owner = User.create(Email("owner@acme.test"), "h")
        viewer = User.create(Email("viewer@acme.test"), "h")
        await uow.tenants.add(tenant)
        await uow.users.add(owner)
        await uow.users.add(viewer)
        await uow.memberships.add(Membership.create(owner.id, tenant.id, Role.OWNER))
        await uow.memberships.add(Membership.create(viewer.id, tenant.id, Role.VIEWER))

        other_tenant = Tenant.create("Other")
        outsider = User.create(Email("outsider@other.test"), "h")
        await uow.tenants.add(other_tenant)
        await uow.users.add(outsider)
        await uow.memberships.add(Membership.create(outsider.id, other_tenant.id, Role.OWNER))

        await uow.commit()
        return str(tenant.id)


async def test_lists_members_sorted_by_email(uow_factory) -> None:
    tenant_id = await _seed(uow_factory)
    members = await ListMembersHandler(uow_factory).handle(ListMembers(tenant_id=tenant_id))
    assert [m.email for m in members] == ["owner@acme.test", "viewer@acme.test"]
    viewer = next(m for m in members if m.email == "viewer@acme.test")
    assert viewer.roles == ["viewer"]


async def test_scoped_to_tenant(uow_factory) -> None:
    tenant_id = await _seed(uow_factory)
    members = await ListMembersHandler(uow_factory).handle(ListMembers(tenant_id=tenant_id))
    assert len(members) == 2
    assert all(m.email != "outsider@other.test" for m in members)
