# 0013. Host the demo on Render: static web app, Docker API, managed PostgreSQL

- **Status:** Proposed
- **Date:** 2026-10-21
- **Issue / PR:** #48, deployed by #101

## Context

The demo (Sprint 3, Thu 22 Oct) must run online with the same flow as locally: the web app,
the API and PostgreSQL over HTTPS, real emails (sign-up, quote #53) and the quote PDF (#52).
What forces the choice:

- The browser reaches the API under `/api` on the web app's origin
  ([0011](0011-same-origin-api-proxy.md)), so the web host must rewrite `/api/*` to the API.
- The API needs a Docker image (WeasyPrint system libraries), about 512 MB of RAM,
  `alembic upgrade head` before it starts, and a shell for `grant-role` and the seed.
- Emails go out over SMTP (`NOVOYA_SMTP_*`). Many free tiers block outbound SMTP ports.
- No migration uses pgvector: any managed PostgreSQL 17 works.
- Three developers, one day left: as little server work as possible, and anyone on the team
  must be able to redeploy.

## Decision

We host the demo on Render, region Frankfurt (data stays in the EU), described in one
Blueprint file, `render.yaml`, at the root of the repository:

| Part | Render service | Plan | Price |
|---|---|---|---|
| `apps/web` | Static site: `pnpm build`, rewrite `/api/*` to the API's public URL, then `/*` to `/index.html` | Free | $0 |
| `apps/api` | Web service from `apps/api/Dockerfile`, pre-deploy `alembic upgrade head` | Starter (512 MB, 0.5 CPU) | $7/month |
| PostgreSQL 17 | Render Postgres | Basic-256mb, 1 GB | about $6.30/month |
| Emails | Brevo SMTP relay, port 587 with STARTTLS | Free (300 emails/day) | $0 |
| LLM | OpenRouter, `:free` models as today | 10 credits bought once: 1,000 free requests/day instead of 50 | $10 once |

About $13 a month, and $10 once. Render bills by the second, so a week of demo costs about
$3; we delete the services after the course. The web app keeps its `*.onrender.com` address:
thanks to 0011 we need no custom domain.

The API must be on a paid plan: a free Render web service sleeps after 15 minutes (about one
minute to wake up, in the middle of the demo), blocks SMTP ports 25, 465 and 587, and has no
pre-deploy command or shell. The free PostgreSQL would do for the demo day, but it is deleted
after 30 days and has no backups.

## Options considered

- **Render, everything free:** $0, but no email, a sleeping API and no pre-deploy: #101
  cannot be done.
- **Vercel (web) + Render (API) + Neon (database):** works, but three accounts and three sets
  of secrets for nothing, since Render's static sites are free too.
- **One Hetzner VPS with docker compose and Caddy:** about €4.50/month and the closest to
  local, but TLS, firewall, backups and a production web image are ours to run. Too much for
  the day before the demo.
- **Railway (Hobby):** about $5 plus usage, and its forum says outbound SMTP needs the Pro plan.
- **Fly.io:** no gain over Render for more setup (`fly.toml`, a separate PostgreSQL).

## Consequences

- **The disk is wiped on every deploy.** The quote PDF (#52) must not live only in a file at
  `pdf_path`: store its bytes in PostgreSQL, or render it again on each `GET /quotes/{id}/pdf`.
- `apps/api/Dockerfile` must install the WeasyPrint system libraries (#52, #101).
- Render gives a `postgresql://` URL. `NOVOYA_DATABASE_URL` must use the `postgresql+asyncpg://`
  scheme, so change the scheme when you copy the URL.
- **The proxy's address is not fixed**, so `FORWARDED_ALLOW_IPS` is `*` on Render, against
  0011's rule. A client could then fake its IP and dodge the rate limits. We accept it for the
  demo; a real launch needs a host with a known proxy address.
- Each environment has its own Google redirect URI. While the Google consent screen is in
  "Testing", only the test users listed there can sign in with Google: add the demo accounts.
- Brevo must verify the sender address of `NOVOYA_MAIL_FROM`, or emails are refused or land
  in spam.
- Check during #101 that the static site's rewrite forwards request bodies and `Set-Cookie`,
  and keeps the `Location` of the Google callback. If it does not, put the web app behind the
  API instead, or on Vercel with the same rewrite.

## Deploy steps

1. On Render, create the workspace (Hobby), add a card, and connect GitHub to
   `loaiattar/Novoya`.
2. **New > Blueprint** on the branch to deploy (`main` for the demo). Render reads
   `render.yaml` (added by #101) and creates the database, the API and the web app.
3. Set the API's environment variables. Secrets stay in Render, never in git:

   | Variable | Value |
   |---|---|
   | `NOVOYA_ENV` | `production` |
   | `NOVOYA_DATABASE_URL` | the database's internal URL, scheme changed to `postgresql+asyncpg://` |
   | `NOVOYA_FRONTEND_URL` | `https://<web>.onrender.com` |
   | `NOVOYA_API_PUBLIC_URL` | `https://<web>.onrender.com/api` |
   | `NOVOYA_CORS_ORIGINS` | `["https://<web>.onrender.com"]` |
   | `NOVOYA_SESSION_COOKIE_SECURE` | `true` |
   | `FORWARDED_ALLOW_IPS` | `*` (see Consequences) |
   | `NOVOYA_SMTP_HOST`, `_PORT`, `_USERNAME`, `_PASSWORD` | Brevo's SMTP relay, port `587` |
   | `NOVOYA_SMTP_START_TLS` | `true` |
   | `NOVOYA_MAIL_FROM` | the sender verified at Brevo |
   | `NOVOYA_OPENROUTER_API_KEY`, `NOVOYA_LLM_MODEL`, `NOVOYA_LLM_FALLBACK_MODELS` | as in the root `.env` |
   | `NOVOYA_GOOGLE_CLIENT_ID`, `NOVOYA_GOOGLE_CLIENT_SECRET` | from the Google Cloud project (#14) |

4. In the Google Cloud console, add `https://<web>.onrender.com/api/auth/google/callback` to the
   OAuth client's redirect URIs.
5. From the API's **Shell** tab on Render, load the catalog and create the first admin:

   ```bash
   python -m novoya_api.catalog.infrastructure.seed
   python -m novoya_api.accounts.presentation.cli grant-role --email you@example.com --role admin
   ```

   To load the client's catalog instead of the seed, sign in as that admin and upload
   `detour.sqlite` on `/admin/import` (#132). The file is deleted once imported. Check that
   the static site's `/api` rewrite lets a request body of that size through.

6. Smoke test on `https://<web>.onrender.com`: sign up and get the verification email, sign in
   with Google, send a wish, get a plan, send a quote and open its PDF.
7. To redeploy: merge into the deployed branch; Render builds and runs the migrations. To
   roll back: **Rollback** on the service's last good deploy.
