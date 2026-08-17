# Deployment 5: CI/CD and security scanning ($0)

This slice adds the automated pipeline: the merge gate, free security and supply-chain scanning, and orchestrated deploy workflows with health verification. It is designed to be genuinely free, and it is explicit about the two features that are not free on private repositories so you can decide whether to make the repos public.

## Files in this slice

Backend repo (`conductor`):
- `.github/workflows/ci.yml` (already present): the merge gate (lint, type check, unit tests, integration tests with a Postgres service, Docker build).
- `.github/workflows/security.yml` (new): Trivy, gitleaks, and Bandit.
- `.github/workflows/production.yml` (new): orchestrated production deploy plus health and smoke verification.
- `.github/workflows/staging.yml` (new): validation, then optional staging deploy.
- `.github/dependabot.yml` (new): weekly dependency and action updates.

Frontend repo (`conductor-web`):
- `.github/dependabot.yml` (new): weekly npm and action updates.

## 1. The honest CI/CD model for this architecture

The classic pipeline diagram assumes GitHub Actions runs the deploy. This deployment uses platform-native Git deploys: Vercel deploys the frontend on push (with per-PR previews), and Render can auto-deploy the backend on push. That changes what CI/CD is for here:

- The **merge gate** (`ci.yml`) is the real protection. Because deploys happen when code reaches `main`, the gate that decides what may reach `main` is what protects production.
- **Security scanning** (`security.yml`, Dependabot) runs on pull requests and on a schedule.
- **Deploy orchestration** (`production.yml`, `staging.yml`) is optional. It exists so that, if you want GitHub Actions to own deploy timing and an approval gate, it can trigger the platform deploy via a deploy hook and then verify health. To use it you turn off Render's auto-deploy; otherwise you would get two deploys per push.

Both models are valid and free. The simplest is platform auto-deploy plus the `ci.yml` gate. The orchestrated model adds a real approval and post-deploy verification at the cost of a little more setup.

## 2. What is free on private repos, and what is not

Two capabilities the deployment brief asks for are not free on private repositories:

- **CodeQL code scanning** requires GitHub Advanced Security on private repos (paid). It is free only on public repos. This slice therefore does not use CodeQL; it uses Trivy, gitleaks, and Bandit, which are free on any repo.
- **Environment protection rules (required reviewers)** are unavailable on free private repos. The `environment: production` in `production.yml` still works, but the manual approval gate only activates on a public repo or a paid plan. On a free private repo, `workflow_dispatch` plus the concurrency lock provide a manual, non-overlapping deploy as the substitute.

A third point: Actions minutes are unlimited on public repos but capped at 2,000/month on free private repos. The workflows here are light (weekly scans, gated deploys), so they fit the private cap, but it is another reason the recommendation below matters.

### Recommendation: make the repositories public

For a portfolio project, making `conductor` and `conductor-web` public is the single change that unlocks the most, at no cost: CodeQL code scanning, environment protection rules with required reviewers, SARIF upload to the Security tab, and unlimited Actions minutes, all become free. It also lets reviewers and recruiters see the code, which is the point of a portfolio. If you make the repos public, you can additionally enable CodeQL (Settings, Code security, set up CodeQL) and add required reviewers to the `production` environment, and the pipeline becomes the full version the brief describes. This slice is written to be fully $0 either way; going public simply adds the features that are otherwise paid.

## 3. Security scanning (`security.yml`)

Three free scanners, each failing the job on findings (rather than uploading SARIF, which needs Advanced Security on private repos):

- **Trivy** (filesystem scan): dependency vulnerabilities, IaC/config misconfigurations, and secrets, failing on High/Critical, ignoring unfixable advisories.
- **gitleaks**: secret scanning across full git history (the binary is downloaded and run directly, which is free for any repo).
- **Bandit**: Python static analysis over the backend `app` package at medium severity and above.

Runs on every pull request, on push to `main`, and weekly. Dependabot complements these with automated dependency-update pull requests (free on all repos, including private).

## 4. Deploy orchestration and required secrets

To use `production.yml` (recommended if you want an approval gate and post-deploy verification), set these repository secrets and turn off Render auto-deploy:

| Secret | Value | Where it comes from |
| --- | --- | --- |
| `RENDER_DEPLOY_HOOK_URL` | the Render service deploy hook URL | Render dashboard, service, Settings, Deploy Hook |
| `PRODUCTION_API_URL` | the live backend URL | e.g. `https://conductor-api.onrender.com` |

For `staging.yml`, optionally:

| Secret | Value |
| --- | --- |
| `RENDER_STAGING_DEPLOY_HOOK_URL` | a staging service deploy hook (if you run one) |
| `STAGING_API_URL` | the staging backend URL |

Render deploy hooks are free. To switch from auto-deploy to orchestrated deploy, set `autoDeploy: false` in `render.yaml` (or toggle it off in the Render dashboard) so only `production.yml` triggers deploys.

`production.yml` behavior: trigger the Render deploy, then poll `/readyz` for up to about ten minutes (allowing for the cold start), then run a smoke test (`/livez` and `/openapi.json`). If the backend does not become healthy, the job fails, which is your signal that the deploy is bad. The `concurrency` group prevents two production deploys from overlapping.

## 5. GitHub environments and approval (public repo or paid plan)

If the repo is public (or you are on a paid plan), configure the approval gate:

1. Repo Settings, Environments, New environment, name it `production`.
2. Add a Required reviewers protection rule (yourself, or a teammate).
3. Now a run of `production.yml` pauses at the `deploy` job until approved.

Do the same for a `staging` environment if you want staging approvals. On a free private repo, skip this; the `workflow_dispatch` manual trigger is the substitute gate.

## 6. Frontend CI/CD

The frontend uses Vercel's Git integration for deploys (slice 3), so it needs no deploy workflow. This slice adds only a Dependabot config for npm and actions. The frontend's own `ci.yml` (typecheck, lint, build, test) remains the merge gate; Vercel deploys after merge.

## 7. Verify (local) and activate (your account)

Local: the workflow YAML is validated structurally in this slice. You cannot run Actions locally, but you can lint the YAML:

```bash
python3 -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('.github/workflows/*.yml')]; print('workflows parse')"
```

Activate (on GitHub, after merge):
1. The `security.yml` and Dependabot run automatically once merged (security on the next PR/push, Dependabot on its schedule). Trigger `security.yml` manually via the Actions tab to see the first run.
2. If using orchestrated deploy: add the secrets (section 4), set `autoDeploy: false`, and run `production-deploy` (manually or by pushing backend changes). Watch it deploy and verify health.
3. If public: enable CodeQL and add the `production` required reviewer (sections 2 and 5).

## 8. What is not claimed

These are the pipeline definitions and the exact secrets and settings to activate them. Nothing here runs against your live accounts until you merge and configure the secrets. The YAML is validated; the live pipeline behavior (deploy hook, health gate, scans) is verified by you running it on GitHub.
