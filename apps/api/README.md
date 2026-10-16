# Novoya API

FastAPI backend. See [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md).

## Folders

```
src/novoya_api/
  main.py          creates the FastAPI app and includes the routers
  config.py        settings from NOVOYA_* environment variables
  db.py            SQLAlchemy engine, session, Base
  openapi.py       prints openapi.json for the frontend
  routers/         HTTP endpoints, one module per resource (thin)
  schemas/         Pydantic request and response models
  services/        business logic: coverage, panels, plans, quotes, accounts
  models/          SQLAlchemy models, one file per table
  auth/            Google sign-in, sessions, client and agent roles
  agent/           OpenRouter client and tool-calling orchestrator
    tools/         travel tools: covered_destinations, search_offers
    prompts/       system prompts
  pdf/             quote PDF (Jinja2 + WeasyPrint)
    templates/
  emails/          "your quote is ready" emails over SMTP
    templates/
  seed/            partners and offers for local development
alembic/versions/  database migrations
tests/             pytest
```

Each package's `__init__.py` says what goes in it and which issue adds it. A request goes router → service → models, and the router returns a schema.

## Run locally

Needs [uv](https://docs.astral.sh/uv/) and a Postgres (`docker compose up db` from the repo root).

```bash
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run uvicorn novoya_api.main:app --reload
```

The API runs on http://localhost:8000. Interactive docs: http://localhost:8000/docs.

## Checks

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest
```

## Database migrations

Add a model in `src/novoya_api/models/` (one file per table) and import it in `models/__init__.py`, then:

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
