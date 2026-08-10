# Contributing to Conductor

This guide describes how to work in this repository: where to run commands,
how to branch and commit, and the quality gate every change must pass.

## Where to run commands

Run every `make`, `docker compose`, and `alembic` command from the service
directory, because that is where the `Makefile`, `docker-compose.yml`, and
`alembic.ini` live:

```
cd ~/conductor/services/control-api
```

Git commands are the exception: run those from anywhere inside `~/conductor`.

## Local quality gate

Before pushing, run the same gate CI runs. Tests use in-memory adapters, so no
database is required:

```
make test        # pytest
make lint        # ruff
make typecheck   # mypy
make fmt         # ruff auto-fix and format (run before committing)
```

All three must be green. If `make lint` reports something after `make fmt`, run
`make fmt` once more, since one fix can expose another (for example, an import
that becomes unused).

Some bugs only appear against a real database or the real logger, since the
default test suite substitutes in-memory adapters. When you touch persistence,
messaging, or anything at the infrastructure edge, also run the service against
Postgres and exercise the affected path by hand (see
`services/control-api/docs/PHASE1_RUNBOOK.md`). A Postgres-backed integration
test suite is planned to close this gap.

## Branch strategy

Trunk-based development with short-lived feature branches and pull requests into
`main`. Keep `main` always green.

```
git switch main && git pull
git switch -c feat/short-description
# work, commit
git push -u origin feat/short-description
gh pr create --fill --base main
# after CI is green:
gh pr merge --squash --delete-branch
git switch main && git pull
```

Branch name prefixes: `feat/`, `fix/`, `chore/`, `docs/`, `ci/`, `refactor/`,
`test/`.

## Commit messages

Use Conventional Commits. The format is `type(scope): summary`, where type is
one of `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `ci`, or `perf`.

Examples:

```
feat(runs): add cancel endpoint
fix(persistence): flush parent run before inserting run_events
docs(runbook): document the three run modes
```

Keep the summary in the imperative mood and under about 72 characters. Use the
body to explain why, not just what.

## Formatting rules

Do not use em dashes in code, comments, docstrings, or documentation. Use
commas, colons, parentheses, or separate sentences instead.

Line length is 100 characters (enforced by ruff). Prefer self-documenting code
over comments; add a comment only when it explains a non-obvious decision.

## Architecture boundaries

The code follows hexagonal architecture with dependencies pointing inward:
`presentation` depends on `application`, which depends on `domain`.
`infrastructure` implements the ports declared by the inner layers and is wired
at the composition root. Do not import `infrastructure` or `presentation` from
`domain` or `application`. Each bounded context owns its data and is accessed by
others through APIs or events, never by reaching across tables.

## Pull requests

Keep pull requests focused on a single change. A PR should pass the full quality
gate locally before you open it, include tests for new behavior, and update the
relevant documentation when behavior or setup changes.
