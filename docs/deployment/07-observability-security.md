# Deployment 7: Observability and security ($0)

On a $0 stack, observability is assembled from several free tiers rather than one platform. This slice wires error tracking into the backend, documents the free uptime, log, and metrics options with their honest tradeoffs, and includes a security audit of the deployment.

## Files in this slice

Backend repo (`conductor`):
- `app/config/settings.py` (modified): a `sentry_dsn` setting.
- `app/infrastructure/observability/sentry.py` (new): guarded Sentry initialization.
- `app/main.py` (modified): initializes Sentry at app startup.
- `pyproject.toml` (modified): adds `sentry-sdk` (imported lazily; inert unless enabled).

## 1. Error tracking: Sentry (free Developer tier)

Sentry's free Developer tier is 5,000 errors per month, one user, 30-day retention, forever-free, which is appropriate for a solo portfolio app. The backend now initializes Sentry when `CONDUCTOR_OTEL_SENTRY_DSN` is set, and does nothing when it is not (the SDK is imported lazily, so it never affects startup or tests when disabled).

Key configuration choice: performance tracing is disabled (`traces_sample_rate=0.0`). On the free tier, performance events share the quota, so errors-only keeps all 5,000 events available for actual errors. This is the recommended free-tier setup.

Enable it:

1. Create a free Sentry account and a project (Python / FastAPI). Copy the DSN.
2. Set the DSN on the Render service:

   ```
   CONDUCTOR_OTEL_SENTRY_DSN = https://<key>@<org>.ingest.sentry.io/<project>
   ```

3. Redeploy. Unhandled exceptions and 500s now appear in Sentry with stack traces and request context.

To protect the quota against a bad deploy flooding errors, set a per-key rate limit in the Sentry project settings (for example ~170 events/day) so one incident cannot exhaust the month.

Frontend error tracking (optional): the Next.js frontend can add `@sentry/nextjs` via `npx @sentry/wizard@latest -i nextjs`, which is also free within the same 5,000-event tier. It is left as an optional follow-up rather than wired here, because the Next.js Sentry setup touches build config and is better run through the official wizard against your own project.

## 2. Uptime monitoring, and the honest tension with sleep-on-idle

Free options: UptimeRobot (50 monitors, 5-minute checks) or Better Stack's free uptime tier. Both ping a URL on a schedule and alert on downtime.

The tension to understand before configuring this: the backend is designed to sleep after 15 minutes idle to stay within Render's free 750 instance-hours. An uptime monitor that pings the backend every few minutes keeps it permanently awake. At a 5-minute interval that is roughly 744 hours per month, which is just under the 750-hour cap but leaves almost no headroom, and it defeats the sleep-on-idle design (though it does eliminate cold starts as a side effect).

Recommended approach:

- **Monitor the frontend** (`https://<app>.vercel.app`) as the primary uptime check. Vercel does not sleep, so pinging it costs nothing against any budget and confirms the user-facing surface is up.
- **Monitor the backend health endpoint** (`/livez`) at a **longer interval** (for example 15 to 30 minutes) if you want backend uptime data while still letting it sleep between checks, or accept that monitoring it frequently keeps it warm within the 750-hour budget. Choose deliberately; do not let a default 1-minute monitor silently consume the instance-hour budget.

Point monitors at `/livez` (liveness, no database) rather than `/readyz` so a brief database nap does not register as downtime.

## 3. Logs and metrics

The free baseline is the platform dashboards, which require no setup:

- **Render** shows backend logs and basic service metrics.
- **Vercel** shows frontend build and function logs.
- **Neon** shows database metrics and query insights.

The application also exposes richer signals that can be connected to free backends if you want more than the dashboards:

- **Structured logs**: the backend logs via structlog in JSON, so the platform log viewers are already structured and searchable. For aggregation and longer retention, Better Stack's free log tier can ingest them; this is optional and depends on the platform supporting a log drain.
- **Metrics**: the backend exposes a Prometheus `/metrics` endpoint. A free Grafana Cloud account can scrape or receive these for dashboards, optional and more setup than the free baseline warrants for a portfolio app.
- **Tracing**: OpenTelemetry tracing is already wired (`CONDUCTOR_OTEL_OTLP_ENDPOINT`); point it at a free OTLP-compatible backend if you want distributed traces. Off by default.

## 4. What is not free (observability)

Stated plainly:

- **Full APM / distributed tracing backend**: paid on the major vendors. Substituted by Sentry errors plus the free OTLP hook if you supply a free collector.
- **Long log retention and high-frequency uptime checks**: reduced on free tiers. The platform dashboards plus a free uptime monitor cover the essentials.
- **Alerting depth**: free tiers alert on basics (downtime, error spikes via Sentry). Rich on-call routing is paid.

## 5. Security audit

A review of the deployment's security posture, what is in place, and the honest gaps with free mitigations.

### In place

- **Transport security**: HTTPS everywhere with automatic certificates (Vercel, Render, Neon). HSTS is sent by the frontend (slice 3).
- **Security headers**: `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, and HSTS on the frontend; `X-Powered-By` disabled (slice 3).
- **Authentication and authorization**: JWT access/refresh tokens with refresh-on-401, and RBAC permission checks on every protected route. The production settings guard rejects the default dev secret, so a real `CONDUCTOR_AUTH_SECRET` is required in production.
- **Secrets management**: all secrets live in platform environment variables and GitHub Actions secrets, never in code or Terraform state (slice 6 keeps them out of state deliberately). The database connection uses TLS (slice 4).
- **Supply chain**: Trivy, gitleaks, and Bandit scan on every PR; Dependabot proposes dependency updates weekly (slice 5).
- **Data exposure**: the AI provider key is server-side only and never reaches the browser; the frontend receives no secrets.

### Gaps and free mitigations

- **Rate limiting**: the API has no application-level rate limiting, so it is exposed to brute-force and abuse. Free mitigations: add a lightweight middleware (for example `slowapi`) for per-IP limits on auth endpoints, or, if you add a custom domain behind Cloudflare, enable Cloudflare's free rate-limiting and bot protection at the edge. Recommended as the next hardening step.
- **Web application firewall (WAF)**: none. Free mitigation: Cloudflare's free tier provides basic WAF and DDoS protection if the app is proxied through it (requires a custom domain).
- **CORS**: currently permissive by default because the same-origin proxy means the browser never makes a cross-origin call. If you switch to direct browser-to-backend calls, set `CONDUCTOR_CORS_ALLOW_ORIGINS` to the exact frontend origin (do not leave it as `*` with credentials).
- **Secret rotation**: no automated rotation. Free mitigation: rotate the `CONDUCTOR_AUTH_SECRET` and provider keys manually on a schedule; Render regenerates the auth secret if you clear it.
- **Dependency-scan visibility**: on a private repo, findings surface as failing CI jobs rather than in the Security tab (Advanced Security is paid). Making the repo public unlocks the Security tab and CodeQL for free.
- **Audit logging**: application actions are logged, but there is no tamper-evident audit trail. Acceptable for a portfolio; a real product would add one.

### Priority recommendation

The single highest-value free hardening is **rate limiting on the auth endpoints**, because they are the most abusable surface and the mitigation is a small middleware with no cost. It is called out as the recommended next step rather than bundled here, since it is an application change worth doing deliberately with its own tests.

## 6. Verify (local) and enable (your accounts)

Local: the backend change compiles and the Sentry path is inert unless a DSN is set, so the existing suite passes unchanged.

```bash
cd services/control-api && source ../../.venv/bin/activate
make lint typecheck test
```

Enable (your accounts):
1. Create a Sentry project, set `CONDUCTOR_OTEL_SENTRY_DSN` on Render, redeploy; trigger a test error and confirm it appears in Sentry.
2. Create UptimeRobot (or Better Stack) monitors on the frontend URL and `/livez`, minding the interval tradeoff in section 2.
3. Review the security gaps; schedule the rate-limiting hardening.

## What is not claimed

This wires backend error tracking and documents the free observability stack and the security posture. It does not create your Sentry or uptime accounts, and it does not add rate limiting (flagged as the recommended next step). The code compiles and stays inert until you provide a DSN; the live telemetry is verified by you enabling it.
