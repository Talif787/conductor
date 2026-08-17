# Optional DNS for a custom domain. Created only when enable_dns = true.
# Default deployment uses free platform subdomains (*.vercel.app, *.onrender.com)
# with their own automatic SSL, so no DNS is required and this stays inert.
#
# DNS-only (unproxied) records are used so the platforms' own TLS terminates
# correctly. If you later want Cloudflare's proxy in front of the frontend,
# enable it deliberately after confirming it works with Vercel.

resource "cloudflare_record" "frontend_root" {
  count   = var.enable_dns ? 1 : 0
  zone_id = var.cloudflare_zone_id
  name    = "@"
  type    = "CNAME"
  content = var.vercel_cname_target
  proxied = false
  comment = "Frontend apex -> Vercel (CNAME flattening)"
}

resource "cloudflare_record" "api" {
  count   = var.enable_dns && var.render_hostname != "" ? 1 : 0
  zone_id = var.cloudflare_zone_id
  name    = "api"
  type    = "CNAME"
  content = var.render_hostname
  proxied = false
  comment = "API subdomain -> Render"
}
