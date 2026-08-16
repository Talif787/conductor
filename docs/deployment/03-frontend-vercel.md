# Deployment 3: Frontend on Vercel ($0)

The frontend (`conductor-web`, Next.js 15) deploys to Vercel's free Hobby tier. Vercel builds Next.js natively, gives automatic HTTPS on a `*.vercel.app` subdomain, and provides a preview deployment for every pull request at no cost. This document covers the configuration, the environment wiring, the pull-request-to-production flow, and one honest caveat about cold starts.

Nothing here is a live deployment; it is the configuration plus the exact steps for you to run against your own Vercel account.

## Files in this slice

- `conductor-web/next.config.mjs` (modified): adds security headers alongside the existing API rewrite and next-intl plugin.
- `conductor-web/vercel.json` (new): pins the framework to Next.js.
- `conductor-web/.env.production.example` (new): documents the one required production variable.

## 1. Connect the repository

In the Vercel dashboard, import the `conductor-web` repository (New Project, then select the repo). Vercel auto-detects Next.js; the `vercel.json` makes that explicit. The build command (`next build`) and output are detected automatically, so no overrides are needed.

Set the Node.js version to match CI (Node 22). Either add an `engines` field to `package.json`:

```bash
cd ~/conductor-web
npm pkg set engines.node="22.x"
```

or set the Node version in the Vercel project settings (Settings, General, Node.js Version). Using `package.json` keeps it in version control, which is preferred.

## 2. Environment variables and scopes

The frontend needs exactly one production variable: `CONDUCTOR_API_ORIGIN`, the origin the Next rewrite proxies `/api/v1/*` to. Vercel scopes environment variables to Production, Preview, and Development independently, which is how the environments stay separated without sharing credentials.

Set these in the Vercel dashboard (Settings, Environment Variables):

| Variable | Scope | Value |
| --- | --- | --- |
| `CONDUCTOR_API_ORIGIN` | Production | `https://<your-render-service>.onrender.com` |
| `CONDUCTOR_API_ORIGIN` | Preview | the same Render URL, or a preview backend if you run one |

Where the value comes from: the Render backend URL from deployment slice 2 (the `onrender.com` subdomain Render assigns the web service). There is no build-time secret here; the API origin is the only wiring the frontend needs, and no AI or database credentials ever reach the frontend (those live only on the backend).

Local development is unaffected: `.env.local` keeps `CONDUCTOR_API_ORIGIN=http://localhost:8000`, and the committed `.env.production.example` documents the production shape.

## 3. The pull-request to production flow

Vercel's Git integration provides the three-stage flow the deployment brief asks for, for free and automatically:

- **Pull request, then Preview.** Every pull request against the repository gets its own preview deployment at a unique URL, built with the Preview-scoped environment variables. This is the frontend staging surface. Reviewers see the real, deployed UI per PR.
- **Merge to the production branch, then Production.** Merging to `main` (the production branch) triggers a production deployment to the primary domain with the Production-scoped variables.

No GitHub Actions workflow is needed for the frontend deploy: Vercel's own Git integration performs the builds and deployments. This keeps the frontend deployment entirely on Vercel's free tier and avoids spending GitHub Actions minutes (which matter on private repositories). The application CI (lint, typecheck, tests, build) still runs in GitHub Actions as a merge gate; Vercel deploys after the branch is in the state you want.

## 4. Security headers

`next.config.mjs` now sends a safe, broadly compatible set of security headers on every response: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, a `Referrer-Policy`, a restrictive `Permissions-Policy`, and HSTS (`Strict-Transport-Security`). `poweredByHeader` is disabled so the `X-Powered-By` header is not advertised.

A strict Content-Security-Policy is deliberately not enforced here. Next.js injects inline scripts for hydration, so a correct CSP requires per-request nonces set through middleware; an incorrect CSP silently breaks the app. Enforcing CSP is a worthwhile follow-up, done with a nonce-based middleware and validated in a preview deployment before it reaches production. A reasonable starting policy to iterate on (in report-only mode first, so it never breaks the app while you tune it) is:

```
Content-Security-Policy-Report-Only:
  default-src 'self';
  script-src 'self' 'unsafe-inline';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data:;
  connect-src 'self';
  frame-ancestors 'none';
  base-uri 'self';
```

HSTS note: the `Strict-Transport-Security` header instructs browsers to use HTTPS for the domain for two years. Vercel serves HTTPS by default, so this is safe on `*.vercel.app`. If you later add a custom domain, confirm HTTPS is working on it before relying on the `preload` directive.

## 5. The cold-start caveat (honest tradeoff)

The backend sleeps after 15 minutes idle and cold starts in 30 to 60 seconds (deployment slice 1). The frontend reaches the backend through the Next rewrite, which means the request is proxied through Vercel to Render. On the first request after the backend has gone to sleep, that proxied call can approach or exceed Vercel's proxy timeout while Render wakes, so the very first load after an idle period may fail and succeed on a retry once the backend is warm.

For a portfolio or demo deployment this is acceptable, and a small "waking up, please retry" affordance in the UI makes it read as intentional. If a smoother first-load experience matters, the $0 alternative is to have the browser call the Render backend directly (bypassing the Vercel proxy), so the browser's own generous timeout absorbs the cold start. That requires pointing the frontend at the absolute backend URL and enabling CORS on the backend (`CONDUCTOR_CORS_ALLOW_ORIGINS` set to the Vercel origin, which the backend already supports). This trades the same-origin simplicity for cold-start robustness; it is documented here as an option rather than applied, because it changes the frontend's API base and adds a CORS surface.

## 6. Verify (local) and deploy (your account)

Local verification of the configuration, which is all that can be checked without a Vercel account:

```bash
cd ~/conductor-web
npm run build        # confirms the config (headers, rewrite, next-intl) compiles
```

Live deployment steps, run against your account:

1. Import the repo in Vercel and set the Node version (section 1).
2. Add `CONDUCTOR_API_ORIGIN` in the Production and Preview scopes (section 2).
3. Open a pull request and confirm a preview deployment is created.
4. Merge to `main` and confirm the production deployment goes live on the `*.vercel.app` domain.
5. Load the production URL, confirm the login page renders and (once the backend is warm) sign-in works end to end.

## What is not claimed

This provides the frontend deployment configuration and the exact steps. It does not deploy the app; that requires your Vercel account. The build compiles locally; the live preview-to-production flow is verified by you executing steps 1 through 5 above.
