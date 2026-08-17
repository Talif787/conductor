# Repository governance as code. These manage settings on the EXISTING repos;
# they do not create repositories. Secrets are intentionally NOT managed here
# (that would place plaintext secret values in local state); set them with the
# gh CLI instead (see the IaC doc).
#
# Note on free private repos: branch protection specifics and environment
# required-reviewer rules may require a paid plan or public visibility. On a
# public repo these apply for free. See the IaC doc for the visibility note.

resource "github_branch_protection" "backend_main" {
  repository_id  = var.backend_repo
  pattern        = "main"
  enforce_admins = false

  required_pull_request_reviews {
    required_approving_review_count = 1
  }

  required_status_checks {
    strict   = true
    contexts = var.ci_status_checks
  }
}

resource "github_repository_environment" "production" {
  repository  = var.backend_repo
  environment = "production"
}

resource "github_repository_environment" "staging" {
  repository  = var.backend_repo
  environment = "staging"
}
