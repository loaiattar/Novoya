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
uv run uvicorn novoya_api.main:app --reload
```

The API runs on http://localhost:8000. Interactive docs: http://localhost:8000/docs.

## Checks

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest
```

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
