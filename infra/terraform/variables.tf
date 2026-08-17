variable "github_owner" {
  type        = string
  description = "GitHub account or org that owns the repositories."
  default     = "Talif787"
}

variable "backend_repo" {
  type        = string
  description = "Backend repository name."
  default     = "conductor"
}

variable "frontend_repo" {
  type        = string
  description = "Frontend repository name."
  default     = "conductor-web"
}

variable "ci_status_checks" {
  type        = list(string)
  description = "Required status check (job) names on main for the backend repo."
  default     = ["quality", "integration"]
}

# --- DNS (optional; only when a custom domain is in use) ---

variable "enable_dns" {
  type        = bool
  description = "Create Cloudflare DNS records. Leave false to use free platform subdomains."
  default     = false
}

variable "cloudflare_zone_id" {
  type        = string
  description = "Cloudflare zone ID for the custom domain."
  default     = ""
}

variable "vercel_cname_target" {
  type        = string
  description = "CNAME target for the Vercel frontend."
  default     = "cname.vercel-dns.com"
}

variable "render_hostname" {
  type        = string
  description = "Render backend hostname for the api subdomain, e.g. conductor-api.onrender.com."
  default     = ""
}
