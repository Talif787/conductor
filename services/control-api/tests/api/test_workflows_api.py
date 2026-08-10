from __future__ import annotations

from app.domain.identity.roles import Role


def _register_tool(client, headers, name: str) -> str:
    resp = client.post("/api/v1/tools", json={"name": name, "kind": "http"}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def test_author_publish_and_run_linkage(client, auth_headers) -> None:
    tool_a = _register_tool(client, auth_headers, "fetch")
    tool_b = _register_tool(client, auth_headers, "summarize")

    created = client.post("/api/v1/workflows", json={"name": "Pipeline"}, headers=auth_headers)
    assert created.status_code == 201
    workflow_id = created.json()["id"]
    assert created.json()["versions"][0]["version"] == 1

    definition = {
        "definition": {
            "steps": [
                {"step_id": "fetch", "name": "Fetch", "tool_id": tool_a},
                {
                    "step_id": "sum",
                    "name": "Summarize",
                    "tool_id": tool_b,
                    "depends_on": ["fetch"],
                },
            ]
        }
    }
    updated = client.put(
        f"/api/v1/workflows/{workflow_id}/versions/1", json=definition, headers=auth_headers
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "draft"

    # a run against the unpublished version is refused
    early = client.post(
        "/api/v1/runs",
        json={"goal": "go", "workflow_id": workflow_id, "workflow_version": "1"},
        headers=auth_headers,
    )
    assert early.status_code == 409

    published = client.post(
        f"/api/v1/workflows/{workflow_id}/versions/1/publish", headers=auth_headers
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"

    # now the run is accepted
    ok = client.post(
        "/api/v1/runs",
        json={"goal": "go", "workflow_id": workflow_id, "workflow_version": "1"},
        headers=auth_headers,
    )
    assert ok.status_code == 201
    assert ok.json()["status"] == "queued"


def test_publishing_empty_definition_is_422(client, auth_headers) -> None:
    created = client.post("/api/v1/workflows", json={"name": "Empty"}, headers=auth_headers).json()
    resp = client.post(
        f"/api/v1/workflows/{created['id']}/versions/1/publish", headers=auth_headers
    )
    assert resp.status_code == 422


def test_new_draft_after_publish(client, auth_headers) -> None:
    tool = _register_tool(client, auth_headers, "fetch")
    workflow_id = client.post(
        "/api/v1/workflows", json={"name": "Versioned"}, headers=auth_headers
    ).json()["id"]
    definition = {"definition": {"steps": [{"step_id": "a", "tool_id": tool}]}}
    client.put(f"/api/v1/workflows/{workflow_id}/versions/1", json=definition, headers=auth_headers)
    client.post(f"/api/v1/workflows/{workflow_id}/versions/1/publish", headers=auth_headers)

    draft = client.post(f"/api/v1/workflows/{workflow_id}/versions", headers=auth_headers)
    assert draft.status_code == 201
    assert draft.json()["version"] == 2

    # a second open draft is rejected
    again = client.post(f"/api/v1/workflows/{workflow_id}/versions", headers=auth_headers)
    assert again.status_code == 409


def test_create_workflow_requires_write_permission(client, make_auth_headers) -> None:
    viewer = make_auth_headers({Role.VIEWER})
    resp = client.post("/api/v1/workflows", json={"name": "X"}, headers=viewer)
    assert resp.status_code == 403


def test_publish_requires_publish_permission(client, auth_headers, make_auth_headers) -> None:
    # author owns tenant data via auth_headers, but an operator token cannot publish
    workflow_id = client.post(
        "/api/v1/workflows", json={"name": "Guarded"}, headers=auth_headers
    ).json()["id"]
    operator = make_auth_headers({Role.OPERATOR})
    resp = client.post(f"/api/v1/workflows/{workflow_id}/versions/1/publish", headers=operator)
    assert resp.status_code == 403
