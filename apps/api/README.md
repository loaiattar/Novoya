# Novoya API

FastAPI backend. See [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md).

## Architecture: modules + Clean Architecture

The backend is a modular monolith. Each business module (`accounts`, `catalog`, `wishes`, `planning`, `quoting`) has the same Clean Architecture layers inside: domain, application (use cases and ports), infrastructure (adapters) and presentation (FastAPI). Dependencies only point inward, and modules talk to each other only through their `public.py`. **Read [docs/BACKEND.md](../../docs/BACKEND.md) before adding code.** `tests/test_architecture.py` fails if an import breaks the rules.

```
src/novoya_api/
  main.py                      creates the app, includes each module's router
  config.py                    settings from NOVOYA_* environment variables
  accounts/  catalog/  wishes/  planning/  quoting/
    public.py                  what other modules may use
    domain/                    entities, rules
    application/               ports/, use_cases/
    infrastructure/            db/models.py, adapters
    presentation/http/         router.py, schemas.py, dependencies.py
  health/                      the complete example module: copy it
  shared/                      errors, value objects, db session, LLM client
alembic/versions/              database migrations
tests/                         pytest
```

Each package's `__init__.py` says what goes in it and which issue adds it. To add a feature, follow [docs/BACKEND.md, section 8](../../docs/BACKEND.md#8-adding-a-feature-step-by-step).

## Run locally

Needs [uv](https://docs.astral.sh/uv/) and a Postgres (`docker compose up db` from the repo root).

```bash
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run python -m novoya_api.catalog.infrastructure.seed
uv run uvicorn novoya_api.main:app --reload
```

The API runs on http://localhost:8000. Interactive docs: http://localhost:8000/docs.

## Import the DÉTOUR catalog

The real catalog comes from the client's DÉTOUR sqlite export ([ADR 0014](../../docs/adr/0014-indicative-prices-and-detour-import.md)). Keep the file outside the repository (`*.sqlite` and `livraison/` are ignored), then:

```bash
uv run alembic upgrade head
uv run python -m novoya_api.catalog.infrastructure.detour --source /path/to/detour.sqlite
# prints the counts only: imported N partners, N offers, N reviews, N extras
```

It opens the file read-only and writes everything in one transaction: an invalid row stops the import and nothing is written. The error names the DÉTOUR table and id, never a name or an email. Running it again updates the same rows (stable ids), deletes the reviews that are no longer publishable, and deactivates (never deletes) the partners, offers and extras that left the export. Reviews come only from the view `avis_diffusables` (consented and pseudonymised). Once it has run, the development seed refuses to run, so made-up offers never mix with the client's.

### Use the client's data on your machine

Each developer has their own database (the `db-data` Docker volume on their computer); nothing is shared until the demo is deployed. The migrations give everyone the same tables, but the client's data is not in git: the export holds partner contacts and reviews, so it is personal data.

**If you run the app with `docker compose up`**, follow [Load the client's catalog](../../README.md#load-the-clients-catalog-détour) in the root README instead: the API container always uses the `novoya` database, so the steps below would not reach it.

Without Docker (the API runs with `uv` on your machine):

1. Ask a teammate for the DÉTOUR export (`DETOUR.zip`). Get it privately, never through git, an issue or a public channel, and keep it outside the repository.
2. Import it into a new, empty database, so the made-up seed partners don't mix with the client's:

   ```bash
   docker exec novoya-db-1 createdb -U novoya novoya_detour
   export NOVOYA_DATABASE_URL=postgresql+asyncpg://novoya:novoya@localhost:5432/novoya_detour
   uv run alembic upgrade head
   uv run python -m novoya_api.catalog.infrastructure.detour --source /path/to/DETOUR/livraison/detour.sqlite
   ```

3. Start the API in the same terminal (the exported URL wins over `.env`): `uv run uvicorn novoya_api.main:app --reload`.

To go back to the seed, `unset NOVOYA_DATABASE_URL`. To remove the client's data, `docker exec novoya-db-1 dropdb -U novoya novoya_detour`.

## Accounts and roles

Sign-up is by email and password; the account is a `client` and must confirm its email before signing in. Locally, the emails land in Mailpit: http://localhost:8025 (`docker compose up mailpit`).

Sign-in with Google needs `NOVOYA_GOOGLE_CLIENT_ID` and `NOVOYA_GOOGLE_CLIENT_SECRET` (ask the team; see #14). Without them, the rest of the app works and `/auth/google/login` sends the browser to `/login?error=unknown_provider`. The web app reaches the API through its own origin, at `/api` ([ADR 0011](../../docs/adr/0011-same-origin-api-proxy.md)): it links to `http://localhost:5173/api/auth/google/login?redirect_to=/wishes/new`, and Google comes back to `http://localhost:5173/api/auth/google/callback` (the redirect URI registered at Google), which sets the session cookie and goes to `redirect_to`. docker compose sets `NOVOYA_API_PUBLIC_URL` to `http://localhost:5173/api` for this. A first Google sign-in creates a `client`; an existing account with the same email is linked. While the Google app is in Testing, only its test users can sign in.

Roles are `client`, `agent`, `admin` and `super_admin` ([ADR 0015](../../docs/adr/0015-super-admin-role.md)). Super admins are named with a command only, on an account that already exists and has confirmed its email; after that, an admin changes the roles of clients and agents with `PATCH /admin/users/{id}/role`, only a super admin gives or takes the `admin` role, and only the command gives or takes `super_admin` (the API never acts on a super admin).

```bash
uv run python -m novoya_api.accounts.presentation.cli grant-role --email you@example.com --role super_admin
# or, with docker compose:
docker compose exec api python -m novoya_api.accounts.presentation.cli grant-role --email you@example.com --role super_admin
```

Other modules protect their routes with `require_client`, `require_agent` or `require_admin` from `accounts/public.py`, on the router (the admin and the super admin pass all three), and read the signed-in user with `CurrentUser`.

## Checks

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest
```

`tests/accounts/test_sql.py` needs PostgreSQL (`docker compose up db`) and is skipped without it. It works in a separate `novoya_test` database, created if needed, so it never empties the development data.

## Database migrations

Add the table in the module's `infrastructure/db/models.py` (Alembic loads every module's models), then:

```bash
uv run alembic revision --autogenerate -m "add users"
uv run alembic upgrade head
```

## OpenAPI file

The frontend generates its client from `openapi.json`. After changing an endpoint, regenerate it and commit it:

```bash
uv run python -m novoya_api.openapi > openapi.json
```

CI fails if the committed file is out of date.
