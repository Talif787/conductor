from __future__ import annotations

from app.domain.identity.roles import Permission, Role, permissions_for


def test_viewer_can_only_read() -> None:
    perms = permissions_for({Role.VIEWER})
    assert perms == frozenset({Permission.RUNS_READ})


def test_operator_can_manage_runs_but_not_members() -> None:
    perms = permissions_for({Role.OPERATOR})
    assert Permission.RUNS_CREATE in perms
    assert Permission.RUNS_CANCEL in perms
    assert Permission.MEMBERS_WRITE not in perms


def test_owner_and_admin_have_all_permissions() -> None:
    assert permissions_for({Role.OWNER}) == frozenset(Permission)
    assert permissions_for({Role.ADMIN}) == frozenset(Permission)


def test_permissions_are_the_union_of_roles() -> None:
    perms = permissions_for({Role.VIEWER, Role.OPERATOR})
    assert Permission.RUNS_CANCEL in perms
