# Deployment 6: Infrastructure as Code ($0)

This slice adds Infrastructure as Code for the parts of the stack where Terraform is genuinely real and free, and it is explicit about the parts where Terraform would be fake, redundant, or conflict with a better native tool. No configuration is written for resources it cannot actually create.

## The honest IaC boundary

Not everything in a $0 stack should be, or can be, managed by Terraform. Here is what manages what, and why:

| Component | Managed by | Why |
| --- | --- | --- |
| Backend service (Render) | `render.yaml` Blueprint (native IaC) | Render recommends Blueprints and says to use its Terraform provider only when mixing in non-Render infra. Terraforming it would duplicate and fight the Blueprint. |
| Database (Neon) | Dashboard / CLI (documented) | Created once; a Terraform provider exists but adds an API token and state for a single database. CLI/dashboard is simpler and equally $0. |
| Frontend (Vercel) | `vercel.json` + dashboard | Project config is minimal (one env var); Vercel's Git integration handles deploys. Terraform would add a token and state for little gain. |
| DNS (custom domain) | Terraform (`cloudflare/cloudflare`) | Genuinely real and free. Provided here, inert until a domain is added. |
| Repo governance (GitHub) | Terraform (`integrations/github`) | Genuinely real and free (on public repos; see caveat). Branch protection and environments as code. |
| Secrets | `gh` CLI (documented) | Deliberately NOT Terraform: secret values would sit in local state as plaintext. |

The principle: use each platform's own IaC where it has one (Render Blueprint), Terraform where it is the right free tool (Cloudflare DNS, GitHub governance), and the CLI where Terraform would only add a token and a state file without benefit (Neon, Vercel, secrets). This avoids writing Terraform that cannot apply or that conflicts with a native model.

## Cost and state

- **Terraform CLI is free and open source** and runs with **local state** at no cost. HCP Terraform (remote state) is not required; its free tier caps at 500 managed resources, which this does not approach anyway.
- **Provider tokens are free**: a GitHub personal access token and (only if using DNS) a Cloudflare API token, both free to create.
- State is kept local and gitignored. It can contain sensitive values, so it is never committed. Secrets are kept out of state entirely by setting them via the CLI rather than Terraform resources.

## Files in this slice

Under `infra/terraform/` in the backend repo:
- `versions.tf`: Terraform and provider version pins; providers authenticate from environment variables.
- `variables.tf`: inputs (repo names, CI check names, optional DNS settings).
- `github.tf`: branch protection on `main` and the `production` / `staging` environments for the backend repo.
- `cloudflare_dns.tf`: DNS records for a custom domain, created only when `enable_dns = true`.
- `terraform.tfvars.example`: sample inputs to copy to `terraform.tfvars` (gitignored).
- `.gitignore`: excludes state and real tfvars.

## Private-repo caveat (same as slice 5)

Branch protection specifics and environment required-reviewer rules may require a paid plan or public repository visibility on GitHub. On a public repo they are free. The `github.tf` here applies cleanly on a public repo; on a free private repo, `terraform plan` may show that some protections cannot be set, in which case either make the repo public (recommended for a portfolio) or narrow the config to what the plan accepts. This is the same public-vs-private tradeoff documented in the CI/CD slice.

## Setup and use

Prerequisites: install Terraform (or OpenTofu), and create the tokens.

```bash
# tokens (free); export them so they never touch state or tfvars
export GITHUB_TOKEN=...          # scopes: repo, admin:repo_hook
# only if managing DNS:
export CLOUDFLARE_API_TOKEN=...  # Zone:DNS edit for your zone

cd infra/terraform
cp terraform.tfvars.example terraform.tfvars   # edit values; this file is gitignored
```

Initialize and validate (this is the real check; it downloads providers and verifies the config):

```bash
terraform init        # downloads the github and cloudflare providers, writes .terraform.lock.hcl
terraform fmt -check   # formatting
terraform validate     # schema and reference validation
terraform plan         # shows exactly what would change; review before applying
```

Because Terraform is managing settings on repositories that already exist (not creating them), the GitHub environment and branch-protection resources apply directly. If a resource reports it already exists, import it rather than recreate it, for example:

```bash
terraform import github_repository_environment.production conductor:production
```

Apply when the plan looks right:

```bash
terraform apply
```

Commit `.terraform.lock.hcl` (provider version lock) so applies are reproducible; do not commit `terraform.tfvars` or any `*.tfstate`.

## Secrets via the CLI (kept out of state)

Set the deploy and app secrets with the `gh` CLI rather than Terraform, so plaintext never enters state:

```bash
gh secret set RENDER_DEPLOY_HOOK_URL  --repo Talif787/conductor    # from Render dashboard
gh secret set PRODUCTION_API_URL      --repo Talif787/conductor    # https://<service>.onrender.com
gh secret set NEON_DATABASE_URL       --repo Talif787/conductor    # libpq form, for backups
```

## DNS: only when you add a domain

By default `enable_dns = false` and no DNS is created; the app uses `*.vercel.app` and `*.onrender.com` with their automatic SSL, which is fully $0. A custom domain is the one unavoidable paid item (the domain registration itself), and Cloudflare DNS to point it is free. When you have a domain in Cloudflare:

1. Set `enable_dns = true`, `cloudflare_zone_id`, and `render_hostname` in `terraform.tfvars`.
2. Export `CLOUDFLARE_API_TOKEN`.
3. `terraform plan` then `terraform apply` to create the apex (frontend to Vercel) and `api` (to Render) records.
4. Add the custom domain in the Vercel and Render dashboards so their TLS certificates are issued for it.

The records are DNS-only (unproxied) so the platforms' TLS works; enabling Cloudflare's proxy in front of Vercel is possible but should be done deliberately after verifying compatibility.

## Neon and Vercel: why CLI, not Terraform

Both have Terraform providers, and using them is possible and free, but each was created once through its dashboard and needs little ongoing change. Managing them in Terraform would add an API token and state for a single project apiece without real benefit, and the database provider in particular pulls connection details into state. The honest choice for this stack is to keep them as documented dashboard/CLI steps (slices 3 and 4). If the stack grows to where they change often, adding their providers is a reasonable future step; it is not warranted now.

## Verification (local) and apply (your accounts)

Local: the HCL is written to standard, version-pinned schemas; validate it yourself with `terraform init && terraform validate && terraform plan` (the sandbox has no Terraform and no network to download providers, so this step is yours). `terraform plan` with no apply is safe and shows exactly what would change.

Apply (your accounts): run `terraform apply` after a clean plan to set branch protection and environments; set secrets via `gh`; enable DNS only when you add a domain.

## What is not claimed

This provides real, validate-able Terraform for the resources where it is the right free tool, and documented native-IaC or CLI paths for the rest. It does not apply anything to your accounts; `terraform plan`/`apply` and the `gh secret set` commands are yours to run. No Terraform is written for resources it cannot create, and no secret values are placed in state.
