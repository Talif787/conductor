# Development Setup

This guide sets up the repository for development in Google Cloud Shell,
connects it to GitHub, and prepares keyless authentication to Google Cloud for
CI. It is written for Cloud Shell but the git and GitHub steps apply anywhere.

Cloud Shell note: only `$HOME` persists (about 5 GB). Anything outside it, and
any system packages you install, are wiped when the VM recycles. Keep the
repository and its virtualenv under `$HOME`, which these steps do.

## 1. One-time identity setup

```
# gcloud is already logged in as your Google account in Cloud Shell.
gcloud config set project YOUR_PROJECT_ID

# Git identity (persists in $HOME/.gitconfig)
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
git config --global init.defaultBranch main
git config --global pull.rebase true

# Authenticate the GitHub CLI (choose HTTPS)
gh auth login
gh auth status
```

## 2. Create or clone the repository

If the project is already a local folder (for example unzipped into `~`):

```
cd ~/conductor
git init
git add .
git commit -m "chore: initial import"
gh repo create conductor --private --source=. --remote=origin --push
```

If it already exists on GitHub, clone it:

```
cd ~
gh repo clone YOUR_USER/conductor
```

## 3. Python environment

Keep the virtualenv under `$HOME` so it survives session recycles.

```
cd ~/conductor/services/control-api
python3 --version                    # needs 3.12 or newer
python3 -m venv ~/conductor/.venv
source ~/conductor/.venv/bin/activate
make install                         # editable install plus dev tools
make test lint typecheck             # confirm a green baseline
```

If the shell prompt loses its `(.venv)` marker later, re-run the `source` line.

## 4. Local configuration

```
cd ~/conductor/services/control-api
cp .env.example .env                 # already gitignored
```

All configuration is read from the environment. See `.env.example` for the full
list. The default database URL points at `localhost:5432`, which matches the
Dockerized Postgres in `docker-compose.yml`.

## 5. Running and testing

See `services/control-api/docs/PHASE1_RUNBOOK.md` for the full run and test
walkthrough (three run modes, API examples, database inspection, and
observability checks).

## 6. Connecting CI to Google Cloud (keyless)

This prepares Workload Identity Federation so GitHub Actions can authenticate to
Google Cloud without any stored service-account key. It becomes active once
deploy or image-push steps are wired into CI in a later phase. The commands were
validated against the `google-github-actions/auth` v3 action, which treats
Direct Workload Identity Federation (no intermediate service account or key) as
the preferred setup.

Set working variables:

```
export PROJECT_ID="$(gcloud config get-value project)"
export PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
export REGION="us-east1"             # pick a region near you
export GH_OWNER="YOUR_USER"
export GH_REPO="YOUR_USER/conductor"
```

Enable the required APIs:

```
gcloud services enable \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  artifactregistry.googleapis.com \
  cloudresourcemanager.googleapis.com
```

Create an Artifact Registry Docker repository for CI images:

```
gcloud artifacts repositories create conductor \
  --repository-format=docker \
  --location="$REGION" \
  --description="Conductor container images"
```

Create the Workload Identity pool and an OIDC provider that trusts GitHub. The
attribute condition restricts admission to your GitHub owner, which is required
practice:

```
gcloud iam workload-identity-pools create github \
  --location="global" \
  --display-name="GitHub Actions Pool"

gcloud iam workload-identity-pools providers create-oidc conductor \
  --location="global" \
  --workload-identity-pool="github" \
  --display-name="GitHub OIDC" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
  --attribute-condition="assertion.repository_owner == '${GH_OWNER}'" \
  --issuer-uri="https://token.actions.githubusercontent.com"
```

Capture the identifiers CI needs, and grant the pool (scoped to this one
repository) permission to push images:

```
export WIF_POOL_ID="$(gcloud iam workload-identity-pools describe github \
  --location=global --format='value(name)')"

export WIF_PROVIDER="$(gcloud iam workload-identity-pools providers describe conductor \
  --location=global --workload-identity-pool=github --format='value(name)')"

gcloud artifacts repositories add-iam-policy-binding conductor \
  --location="$REGION" \
  --role="roles/artifactregistry.writer" \
  --member="principalSet://iam.googleapis.com/${WIF_POOL_ID}/attribute.repository/${GH_REPO}"
```

The condition admits your whole owner namespace, but the IAM binding scopes
write access to just `${GH_REPO}`, so only this repository can push images.

Store the values as GitHub Actions repository variables (they are not secrets):

```
gh variable set GCP_PROJECT_ID   --body "$PROJECT_ID"
gh variable set GCP_REGION       --body "$REGION"
gh variable set GCP_WIF_PROVIDER --body "$WIF_PROVIDER"
```

A GitHub Actions job authenticates with these using `google-github-actions/auth@v3`
and needs `permissions: id-token: write` so GitHub issues the OIDC token. Note
that a new pool, provider, and IAM binding can take a few minutes to propagate
before the first run succeeds.

## 7. Daily loop

```
cd ~/conductor
git switch main && git pull
git switch -c feat/short-description
source ~/conductor/.venv/bin/activate
# work in services/control-api, run: make test lint typecheck
git add -A
git commit -m "feat(scope): summary"
git push -u origin feat/short-description
gh pr create --fill --base main
```

See `CONTRIBUTING.md` for branch and commit conventions.
