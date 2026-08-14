"""Read surface for workspace members."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.application.auth.principal import Principal
from app.application.members.command_handlers import (
    AddMemberHandler,
    ChangeMemberRoleHandler,
)
from app.application.members.commands import AddMember, ChangeMemberRole
from app.application.members.queries import ListMembers
from app.application.members.query_handlers import ListMembersHandler
from app.domain.identity.roles import Permission
from app.presentation.api.dependencies import (
    provide_add_member_handler,
    provide_change_member_role_handler,
    provide_list_members_handler,
    require_permission,
)
from app.presentation.api.v1.schemas import (
    AddMemberRequest,
    ChangeMemberRoleRequest,
    MemberResponse,
)

router = APIRouter(prefix="/members", tags=["members"])


@router.get("", response_model=list[MemberResponse])
async def list_members(
    principal: Annotated[Principal, Depends(require_permission(Permission.MEMBERS_READ))],
    handler: Annotated[ListMembersHandler, Depends(provide_list_members_handler)],
) -> list[MemberResponse]:
    members = await handler.handle(ListMembers(tenant_id=str(principal.tenant_id)))
    return [MemberResponse.from_dto(m) for m in members]


@router.post("", response_model=MemberResponse, status_code=201)
async def add_member(
    body: AddMemberRequest,
    principal: Annotated[Principal, Depends(require_permission(Permission.MEMBERS_WRITE))],
    handler: Annotated[AddMemberHandler, Depends(provide_add_member_handler)],
) -> MemberResponse:
    member = await handler.handle(
        AddMember(
            tenant_id=str(principal.tenant_id),
            email=body.email,
            password=body.password,
            role=body.role,
        )
    )
    return MemberResponse.from_dto(member)


@router.put("/{user_id}", response_model=MemberResponse)
async def change_member_role(
    user_id: str,
    body: ChangeMemberRoleRequest,
    principal: Annotated[Principal, Depends(require_permission(Permission.MEMBERS_WRITE))],
    handler: Annotated[ChangeMemberRoleHandler, Depends(provide_change_member_role_handler)],
) -> MemberResponse:
    member = await handler.handle(
        ChangeMemberRole(
            tenant_id=str(principal.tenant_id),
            user_id=user_id,
            role=body.role,
        )
    )
    return MemberResponse.from_dto(member)
