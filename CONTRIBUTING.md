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

Always activate the virtual environment first in a new shell, or commands fall
back to the system Python and fail with missing modules:

```
source ~/conductor/.venv/bin/activate
```

## Local quality gate

Before pushing, run the same gate CI runs. The default test suite uses in-memory
adapters, so no database is required:

```
make fmt        # ruff auto-fix and format (run before committing)
make lint       # ruff
make typecheck  # mypy
make test       # pytest (unit; in-memory adapters)
```

All must be green. If `make lint` reports something after `make fmt`, run
`make fmt` once more, since one fix can expose another (for example, an import
that becomes unused).

### Integration tests (Postgres-backed)

A Postgres-backed integration suite now exists and runs in CI. Some bugs only
appear against a real database (for example, a missing table or a driver-level
connection issue), which the in-memory suite cannot catch. When you touch
persistence, messaging, migrations, or anything at the infrastructure edge, run
it locally against Postgres:

```
docker compose up -d --wait postgres
alembic upgrade head
make test-integration
```

If auth or data endpoints return a 500 with `relation "..." does not exist`, the
database is empty or unmigrated; run `alembic upgrade head` and confirm the app
and alembic point at the same database (a stray `CONDUCTOR_DB_URL` in the shell
can split them).

### Security scanning

CI runs Trivy (dependencies, IaC, secrets), gitleaks (secret scan), and Bandit
(Python SAST) on every pull request, and Dependabot proposes weekly updates. A
failing security job is a real finding: fix the vulnerability or secret, or add a
justified entry to `.trivyignore` with a comment explaining the risk acceptance.
Do not merge past a security failure without addressing it.

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

### Branch protection

`main` is protected: the `quality` and `integration` CI checks must pass, and one
approving review is required. On a solo repository you cannot approve your own
pull request, so merge with admin bypass:

```
gh pr merge <n> --squash --delete-branch --admin
```

If `gh` reports "Resource not accessible by personal access token," a Terraform
`GITHUB_TOKEN` is shadowing your login; run `unset GITHUB_TOKEN` and retry.

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
relevant documentation when behavior or setup changes. Changes that affect
deployment, environment variables, or operations should also update the relevant
file under docs/deployment/ (DEPLOYMENT, RUNBOOK, ENVIRONMENT_VARIABLES, and so
on).
