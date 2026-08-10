# Phase 3: Workflow Authoring and Tool Registry

This phase gives the `workflow_id` and `workflow_version` fields on a run real
meaning. You register tools, author a workflow as a versioned draft, validate
and publish it, and only then can a run reference that published version.

## Two new bounded contexts

**Tool Registry** (`app/domain/tools`, `app/application/tools`). A tool is a
tenant-scoped, named capability with an input and output JSON schema and a kind
(`builtin`, `http`, or `mcp`). Tool names are unique per tenant. Tools are the
building blocks a workflow step points at.

**Workflow Authoring** (`app/domain/workflows`, `app/application/workflows`). A
workflow is a tenant-scoped container with one or more versions. A version holds
a definition (a DAG of steps) and moves through a small lifecycle:

```
draft  --publish-->  published        (immutable from here)
  ^                       |
  |                       v
  +----- new draft -------+   (open a new version, edit, publish again)
```

A version is immutable once published. To change a published workflow you open a
new draft version, which starts as a copy of the latest version's definition.

## The definition and its validation

A definition is a set of steps. Each step has a `step_id` (unique within the
workflow), a `tool_id` pointing at a registered tool, and a `depends_on` list of
upstream step ids. Validation runs at publish time and enforces:

1. the definition has at least one step,
2. step ids are unique,
3. every dependency resolves to a real step and no step depends on itself,
4. every `tool_id` resolves to a tool registered in the same tenant,
5. the dependency graph is acyclic.

Validation lives in `app/domain/workflows/validation.py` as a pure function, so
the entire rule set is unit-tested without a database or the web layer.

## Run linkage

When a run is created with a `workflow_id` and `workflow_version`, the run
create handler verifies the referenced version exists, belongs to the caller's
tenant, and is published. A draft or unknown version is refused (409 or 404), so
a run can never point at an unpublished or foreign workflow.

## RBAC

New permissions: `tools:read`, `tools:write`, `workflows:read`,
`workflows:write`, `workflows:publish`. Role grants:

- **viewer**: read runs, tools, and workflows.
- **operator**: viewer plus create and cancel runs.
- **author**: operator plus write tools, write workflows, and publish.
- **admin` / `owner**: all permissions.

## Endpoints

Tools:

- `POST   /api/v1/tools`               register a tool           (`tools:write`)
- `GET    /api/v1/tools`               list tools                (`tools:read`)
- `GET    /api/v1/tools/{id}`          get one tool              (`tools:read`)
- `PATCH  /api/v1/tools/{id}`          update a tool             (`tools:write`)

Workflows:

- `POST   /api/v1/workflows`                              create (draft v1)  (`workflows:write`)
- `GET    /api/v1/workflows`                              list               (`workflows:read`)
- `GET    /api/v1/workflows/{id}`                         get with versions  (`workflows:read`)
- `PUT    /api/v1/workflows/{id}/versions/{v}`            edit a draft       (`workflows:write`)
- `POST   /api/v1/workflows/{id}/versions/{v}/publish`    publish a draft    (`workflows:publish`)
- `POST   /api/v1/workflows/{id}/versions`               open a new draft   (`workflows:write`)
- `POST   /api/v1/workflows/{id}/archive`                archive            (`workflows:write`)

## End-to-end example

Register the tools your steps will use:

```bash
BASE=http://localhost:8000/api/v1
AUTH="Authorization: Bearer $TOKEN"

FETCH=$(curl -s -X POST "$BASE/tools" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"name":"fetch","kind":"http","input_schema":{"type":"object"}}' | jq -r .id)

SUMMARIZE=$(curl -s -X POST "$BASE/tools" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"name":"summarize","kind":"builtin"}' | jq -r .id)
```

Create a workflow (it starts with an empty draft, version 1):

```bash
WF=$(curl -s -X POST "$BASE/workflows" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"name":"Research Pipeline"}' | jq -r .id)
```

Fill in the draft definition, then publish it:

```bash
curl -s -X PUT "$BASE/workflows/$WF/versions/1" -H "$AUTH" -H 'Content-Type: application/json' \
  -d "{\"definition\":{\"steps\":[
        {\"step_id\":\"fetch\",\"name\":\"Fetch\",\"tool_id\":\"$FETCH\"},
        {\"step_id\":\"sum\",\"name\":\"Summarize\",\"tool_id\":\"$SUMMARIZE\",\"depends_on\":[\"fetch\"]}
      ]}}"

curl -s -X POST "$BASE/workflows/$WF/versions/1/publish" -H "$AUTH"
```

Create a run against the published version:

```bash
curl -s -X POST "$BASE/runs" -H "$AUTH" -H 'Content-Type: application/json' \
  -d "{\"goal\":\"Summarize this week's papers\",\"workflow_id\":\"$WF\",\"workflow_version\":\"1\"}"
```

Referencing the draft before it was published, or a version that does not exist,
is refused.

## Deferred (later phases)

Actually executing a workflow is Phase 4 (Agent Runtime). Deep JSON-schema
validation of how a step's inputs map from upstream outputs, version diffing,
and tool deprecation are intentionally out of scope here and noted for later.

## Migration

`0003_tools_and_workflows` creates `tools`, `workflows`, and `workflow_versions`
(the last with a `CASCADE` foreign key to `workflows` and a unique constraint on
`(workflow_id, version)`). Definitions are stored as JSONB.
