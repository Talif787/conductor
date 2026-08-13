"""Query handlers for the members read surface."""

from __future__ import annotations

from collections.abc import Callable

from app.application.members.dtos import MemberDTO
from app.application.members.queries import ListMembers
from app.application.ports import UnitOfWork
from app.domain.shared.identifiers import TenantId

UnitOfWorkFactory = Callable[[], UnitOfWork]


class ListMembersHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def handle(self, query: ListMembers) -> list[MemberDTO]:
        tenant_id = TenantId.parse(query.tenant_id)
        async with self._uow_factory() as uow:
            memberships = await uow.memberships.find_by_tenant(tenant_id)

            # A user could hold more than one membership in a tenant; collect
            # their roles, then emit one member per user.
            roles_by_user: dict[str, list[str]] = {}
            for m in memberships:
                roles_by_user.setdefault(str(m.user_id), []).append(m.role.value)

            members: list[MemberDTO] = []
            for m in memberships:
                key = str(m.user_id)
                if key not in roles_by_user:
                    continue  # already emitted for this user
                roles = roles_by_user.pop(key)
                user = await uow.users.get(m.user_id)
                if user is None:
                    continue
                members.append(MemberDTO(user_id=key, email=user.email.value, roles=sorted(roles)))

            members.sort(key=lambda x: x.email)
            return members
