# Phase 5: External Tool Invocation

Phase 4 shipped the agent runtime with a `ToolInvoker` port and a builtin
invoker (echo, uppercase, llm). Tools of kind `http` and `mcp` were accepted by
the registry but raised `ToolKindNotSupportedError` at execution time. Phase 5
closes that gap: HTTP tools call real endpoints and MCP tools call real MCP
servers, both as ordinary steps inside a workflow. The execution engine is
unchanged. These invokers are additional dispatch targets behind the same
`ToolInvoker` port, so they work with the existing `LocalExecutionEngine`.

## Tool configuration

Tools gained an additive `config` field (JSONB, defaults to `{}`), threaded
through the domain entity, application commands and DTOs, persistence, and the
API schemas. Migration `0005_tool_config` adds the column with a server default
of `{}`, so existing rows are backfilled and nothing breaks.

An HTTP tool carries its endpoint in `config`:

```json
{
  "name": "remote_fetch",
  "kind": "http",
  "config": {
    "url": "https://api.example.com/echo",
    "method": "POST",
    "headers": { "X-Api": "secret" },
    "timeout_seconds": 30
  }
}
```

`url` is required. `method` defaults to `POST`, `headers` to `{}`, and
`timeout_seconds` to 30. A missing `url` fails the step with
`ToolExecutionError`.

An MCP tool points at a server and (optionally) names the remote tool:

```json
{
  "name": "search",
  "kind": "mcp",
  "config": {
    "server_url": "https://mcp.example.com/",
    "tool": "web_search",
    "headers": {},
    "timeout_seconds": 30
  }
}
```

`server_url` is required. `tool` defaults to the registered tool name, so a tool
named `web_search` needs no explicit `tool` entry. A missing `server_url` fails
the step.

## Invocation contract

Every step receives the same context the builtin invoker sees: the run
`parameters` (the input context supplied when the run was created) and `inputs`
(the outputs of upstream steps this step depends on).

For HTTP, the invoker sends a JSON body of that context on methods that carry a
body (`POST`, `PUT`, `PATCH`):

```json
{ "parameters": { "city": "boston" }, "inputs": { "fetch": { "text": "boston" } } }
```

`GET` and other methods send no body. A response with status 400 or above fails
the step. A JSON object response becomes the step output as is; a non-object
JSON value is wrapped as `{ "result": <value> }`; a non-JSON response becomes
`{ "raw": "<text>" }`.

For MCP, the same context is sent as the `arguments` of a `tools/call`. The
`result` object returned by the server becomes the step output. If the server
marks the result as an error (`isError`), the step fails.

Because the output of each step flows into the `inputs` of its dependents, an
HTTP tool that returns `{ "text": "boston" }` can feed a downstream `uppercase`
builtin that produces `{ "text": "BOSTON" }`. External and builtin tools compose
in a single DAG.

## Dispatch

`CompositeToolInvoker` now routes by tool kind: `builtin` to the builtin
invoker, `http` to `HttpToolInvoker`, and `mcp` to `McpToolInvoker`. The HTTP
and MCP invokers are optional constructor arguments. When absent (some unit
tests wire builtin only), those kinds still raise `ToolKindNotSupportedError`,
which keeps the earlier deferral behavior valid. The composition root wires all
three.

Transport lives behind two ports, `HttpToolClient` and `McpToolClient`, so the
invoker logic (config to request, response to output, error handling) is tested
with fakes and never touches the network in tests. Real adapters:

- `HttpxToolClient` issues the request with httpx and maps the response.
- `JsonRpcMcpToolClient` speaks JSON-RPC over the MCP streamable HTTP transport:
  it performs the `initialize` handshake, captures the session id, sends the
  `notifications/initialized` notification, then issues `tools/call`. It decodes
  both `application/json` and `text/event-stream` responses. It targets MCP
  servers reachable over HTTP; the stdio transport is future work. This adapter
  is validated against a live MCP server rather than in the unit suite.

## Verifying locally

```bash
cd services/control-api
make test lint typecheck
```

Apply the migration and confirm the head, then prove the rollback:

```bash
docker compose up -d --wait postgres
alembic upgrade head && alembic current          # expect 0005 (head)
alembic downgrade 0004 && alembic current        # expect 0004
alembic upgrade head && alembic current          # expect 0005 (head)
make test-integration
```

### HTTP smoke test against a public echo endpoint

`httpbin.org/post` echoes the JSON body it receives, which makes it a convenient
real endpoint for an end to end check. With the API running (`make run`, port
8000):

```bash
BASE=http://localhost:8000/api/v1

# 1. Register and log in, capture the access token.
TOKEN=$(curl -s -X POST "$BASE/auth/register" \
  -H 'Content-Type: application/json' \
  -d '{"tenant_name":"Acme","email":"owner@acme.test","password":"password123"}' \
  | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
AUTH="Authorization: Bearer $TOKEN"

# 2. Register an HTTP tool pointing at httpbin.
TOOL=$(curl -s -X POST "$BASE/tools" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"name":"echo_remote","kind":"http","config":{"url":"https://httpbin.org/post","method":"POST"}}' \
  | python -c 'import sys,json;print(json.load(sys.stdin)["id"])')

# 3. Author and publish a one step workflow that uses it.
WF=$(curl -s -X POST "$BASE/workflows" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"name":"Echo"}' | python -c 'import sys,json;print(json.load(sys.stdin)["id"])')
curl -s -X PUT "$BASE/workflows/$WF/versions/1" -H "$AUTH" -H 'Content-Type: application/json' \
  -d "{\"definition\":{\"steps\":[{\"step_id\":\"call\",\"tool_id\":\"$TOOL\"}]}}" > /dev/null
curl -s -X POST "$BASE/workflows/$WF/versions/1/publish" -H "$AUTH" > /dev/null

# 4. Create and execute a run.
RUN=$(curl -s -X POST "$BASE/runs" -H "$AUTH" -H 'Content-Type: application/json' \
  -d "{\"goal\":\"echo\",\"parameters\":{\"city\":\"boston\"},\"workflow_id\":\"$WF\",\"workflow_version\":\"1\"}" \
  | python -c 'import sys,json;print(json.load(sys.stdin)["id"])')
curl -s -X POST "$BASE/runs/$RUN/execute" -H "$AUTH" | python -m json.tool
```

The run reports `succeeded`, and the `call` step output contains httpbin's echo
of the `{ "parameters": ..., "inputs": ... }` body under its `json` field.
