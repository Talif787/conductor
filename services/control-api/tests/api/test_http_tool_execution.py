from __future__ import annotations

from fastapi.testclient import TestClient

from app.application.execution.tool_clients import (
    HttpToolClient,
    HttpToolRequest,
    HttpToolResponse,
)
from app.presentation.api.dependencies import provide_http_tool_client

_V1 = "/api/v1"


class _EchoHttpClient(HttpToolClient):
    """Returns the request body back as JSON, so the test can assert threading."""

    def __init__(self) -> None:
        self.seen: HttpToolRequest | None = None

    async def send(self, request: HttpToolRequest) -> HttpToolResponse:
        self.seen = request
        return HttpToolResponse(200, {"echoed": request.body, "text": "ok"}, "")


def _register_http_tool(client: TestClient, headers: dict) -> dict:
    resp = client.post(
        f"{_V1}/tools",
        headers=headers,
        json={
            "name": "remote_fetch",
            "kind": "http",
            "config": {
                "url": "https://api.example.com/echo",
                "method": "POST",
                "headers": {"X-Api": "secret"},
            },
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _publish_single_step_workflow(client: TestClient, headers: dict, tool_id: str) -> str:
    created = client.post(f"{_V1}/workflows", headers=headers, json={"name": "Remote"})
    assert created.status_code == 201, created.text
    workflow_id = created.json()["id"]
    definition = {"definition": {"steps": [{"step_id": "call", "tool_id": tool_id}]}}
    updated = client.put(
        f"{_V1}/workflows/{workflow_id}/versions/1", headers=headers, json=definition
    )
    assert updated.status_code == 200, updated.text
    published = client.post(f"{_V1}/workflows/{workflow_id}/versions/1/publish", headers=headers)
    assert published.status_code == 200, published.text
    return workflow_id


def test_tool_config_round_trips(client: TestClient, auth_headers: dict) -> None:
    created = _register_http_tool(client, auth_headers)
    assert created["config"]["url"] == "https://api.example.com/echo"
    fetched = client.get(f"{_V1}/tools/{created['id']}", headers=auth_headers)
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["config"]["headers"] == {"X-Api": "secret"}


def test_http_tool_executes_in_workflow(client: TestClient, auth_headers: dict) -> None:
    fake = _EchoHttpClient()
    client.app.dependency_overrides[provide_http_tool_client] = lambda: fake
    try:
        tool = _register_http_tool(client, auth_headers)
        workflow_id = _publish_single_step_workflow(client, auth_headers, tool["id"])
        created = client.post(
            f"{_V1}/runs",
            headers=auth_headers,
            json={
                "goal": "call the remote api",
                "parameters": {"city": "boston"},
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
        call_step = next(s for s in body["steps"] if s["step_id"] == "call")
        assert call_step["status"] == "succeeded"
        assert call_step["output"]["text"] == "ok"
        assert call_step["output"]["echoed"] == {
            "parameters": {"city": "boston"},
            "inputs": {},
        }
        assert fake.seen is not None
        assert fake.seen.headers == {"X-Api": "secret"}
    finally:
        client.app.dependency_overrides.pop(provide_http_tool_client, None)
