# Terraform CLI with local state is free and open source (no HCP account needed).
# Providers are pinned for reproducibility. Auth comes from environment variables
# so no tokens are ever written to state or committed:
#   GITHUB_TOKEN           (repo + admin:repo_hook scope)
#   CLOUDFLARE_API_TOKEN   (Zone:DNS edit, only if managing DNS)
terraform {
  required_version = ">= 1.6"
  required_providers {
    github = {
      source  = "integrations/github"
      version = "~> 6.0"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.0"
    }
  }
}

provider "github" {
  owner = var.github_owner
  # token read from the GITHUB_TOKEN environment variable
}

provider "cloudflare" {
  # api token read from the CLOUDFLARE_API_TOKEN environment variable
}
