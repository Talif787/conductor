from __future__ import annotations

from app.domain.identity.roles import Role


def test_register_list_get_update_tool(client, auth_headers) -> None:
    created = client.post(
        "/api/v1/tools",
        json={"name": "fetch", "kind": "http", "input_schema": {"type": "object"}},
        headers=auth_headers,
    )
    assert created.status_code == 201
    tool_id = created.json()["id"]

    listed = client.get("/api/v1/tools", headers=auth_headers)
    assert listed.status_code == 200
    assert any(item["id"] == tool_id for item in listed.json())

    fetched = client.get(f"/api/v1/tools/{tool_id}", headers=auth_headers)
    assert fetched.status_code == 200

    updated = client.patch(
        f"/api/v1/tools/{tool_id}",
        json={"description": "documented"},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "documented"


def test_duplicate_tool_name_conflicts(client, auth_headers) -> None:
    body = {"name": "fetch", "kind": "http"}
    assert client.post("/api/v1/tools", json=body, headers=auth_headers).status_code == 201
    conflict = client.post("/api/v1/tools", json=body, headers=auth_headers)
    assert conflict.status_code == 409
    assert conflict.headers["content-type"].startswith("application/problem+json")


def test_register_requires_write_permission(client, make_auth_headers) -> None:
    viewer = make_auth_headers({Role.VIEWER})
    resp = client.post("/api/v1/tools", json={"name": "x", "kind": "http"}, headers=viewer)
    assert resp.status_code == 403


def test_tools_require_authentication(client) -> None:
    assert client.get("/api/v1/tools").status_code == 401
