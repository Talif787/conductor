from __future__ import annotations

from app.domain.identity.roles import Permission, Role, permissions_for


def test_viewer_can_read_every_catalog_but_not_write() -> None:
    perms = permissions_for({Role.VIEWER})
    assert perms == frozenset(
        {Permission.RUNS_READ, Permission.TOOLS_READ, Permission.WORKFLOWS_READ}
    )
    assert Permission.TOOLS_WRITE not in perms
    assert Permission.WORKFLOWS_WRITE not in perms


def test_operator_can_run_but_not_publish() -> None:
    perms = permissions_for({Role.OPERATOR})
    assert Permission.RUNS_CREATE in perms
    assert Permission.RUNS_CANCEL in perms
    assert Permission.WORKFLOWS_PUBLISH not in perms
    assert Permission.MEMBERS_WRITE not in perms


def test_author_can_author_and_publish() -> None:
    perms = permissions_for({Role.AUTHOR})
    assert {
        Permission.TOOLS_WRITE,
        Permission.WORKFLOWS_WRITE,
        Permission.WORKFLOWS_PUBLISH,
    } <= perms
    assert Permission.MEMBERS_WRITE not in perms


def test_owner_and_admin_have_all_permissions() -> None:
    assert permissions_for({Role.OWNER}) == frozenset(Permission)
    assert permissions_for({Role.ADMIN}) == frozenset(Permission)


def test_permissions_are_the_union_of_roles() -> None:
    perms = permissions_for({Role.VIEWER, Role.OPERATOR})
    assert Permission.RUNS_CANCEL in perms
