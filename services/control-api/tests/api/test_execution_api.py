from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.domain.identity.roles import Role

_V1 = "/api/v1"


def _make_tool(client: TestClient, headers: dict, name: str) -> str:
    resp = client.post(
        f"{_V1}/tools",
        headers=headers,
        json={"name": name, "kind": "builtin", "input_schema": {}, "output_schema": {}},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _publish_two_step_workflow(client: TestClient, headers: dict) -> str:
    echo = _make_tool(client, headers, "echo")
    summ = _make_tool(client, headers, "llm")
    created = client.post(f"{_V1}/workflows", headers=headers, json={"name": "Pipeline"})
    assert created.status_code == 201, created.text
    workflow_id = created.json()["id"]
    definition = {
        "definition": {
            "steps": [
                {"step_id": "fetch", "tool_id": echo},
                {"step_id": "sum", "tool_id": summ, "depends_on": ["fetch"]},
            ]
        }
    }
    updated = client.put(
        f"{_V1}/workflows/{workflow_id}/versions/1", headers=headers, json=definition
    )
    assert updated.status_code == 200, updated.text
    published = client.post(f"{_V1}/workflows/{workflow_id}/versions/1/publish", headers=headers)
    assert published.status_code == 200, published.text
    return workflow_id


def test_execute_run_end_to_end(client: TestClient, auth_headers: dict) -> None:
    workflow_id = _publish_two_step_workflow(client, auth_headers)
    created = client.post(
        f"{_V1}/runs",
        headers=auth_headers,
        json={
            "goal": "summarize the report",
            "parameters": {"prompt": "quarterly numbers"},
            "workflow_id": workflow_id,
            "workflow_version": "1",
        },
    )
    assert created.status_code == 201, created.text
    run_id = created.json()["id"]

    executed = client.post(f"{_V1}/runs/{run_id}/execute", headers=auth_headers)
    assert executed.status_code == 200, executed.text
    body = executed.json()
    assert body["status"] == "succeeded"
    assert [s["status"] for s in body["steps"]] == ["succeeded", "succeeded"]
    sum_step = next(s for s in body["steps"] if s["step_id"] == "sum")
    assert sum_step["output"]["completion"].startswith("[fake:")

    fetched = client.get(f"{_V1}/runs/{run_id}/execution", headers=auth_headers)
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["status"] == "succeeded"


def test_execute_requires_permission(
    client: TestClient, auth_headers: dict, make_auth_headers
) -> None:
    workflow_id = _publish_two_step_workflow(client, auth_headers)
    created = client.post(
        f"{_V1}/runs",
        headers=auth_headers,
        json={"goal": "go", "workflow_id": workflow_id, "workflow_version": "1"},
    )
    run_id = created.json()["id"]
    viewer = make_auth_headers({Role.VIEWER})
    resp = client.post(f"{_V1}/runs/{run_id}/execute", headers=viewer)
    assert resp.status_code == 403, resp.text


def test_execute_run_without_workflow_conflicts(client: TestClient, auth_headers: dict) -> None:
    created = client.post(f"{_V1}/runs", headers=auth_headers, json={"goal": "no workflow"})
    run_id = created.json()["id"]
    resp = client.post(f"{_V1}/runs/{run_id}/execute", headers=auth_headers)
    assert resp.status_code == 409, resp.text


def test_execute_unknown_run_not_found(client: TestClient, auth_headers: dict) -> None:
    resp = client.post(f"{_V1}/runs/{uuid.uuid4()}/execute", headers=auth_headers)
    assert resp.status_code == 404, resp.text
