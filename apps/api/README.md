# Novoya API

FastAPI backend. See [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md).

## Clean Architecture

The code follows Clean Architecture: domain, application (use cases and ports), infrastructure (adapters) and presentation (FastAPI), with dependencies pointing only inward. **Read [docs/BACKEND.md](../../docs/BACKEND.md) before adding code**: it explains each layer, the ports, a request end to end, the tests and how to add a feature. `tests/test_architecture.py` fails if an import breaks the rules.

```
src/novoya_api/
  main.py                      creates the app, includes the routers
  config.py                    settings from NOVOYA_* environment variables
  domain/
    entities/  value_objects/  errors.py
  application/
    ports/                     interfaces (typing.Protocol)
    use_cases/                 one module per action
  infrastructure/
    db/                        base, session, models/, repositories/, seed/
    llm/                       OpenRouter client, orchestrator, tools/, prompts/
    pdf/                       quote PDF (Jinja2 + WeasyPrint), templates/
    email/                     "your quote is ready" over SMTP, templates/
    auth/                      Google OAuth
  presentation/http/
    routers/  schemas/  dependencies.py
alembic/versions/              database migrations
tests/                         pytest
```

Each package's `__init__.py` says what goes in it and which issue adds it.

To add a feature, follow the steps in [docs/BACKEND.md, section 9](../../docs/BACKEND.md#9-adding-a-feature-step-by-step).

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

Add a model in `src/novoya_api/infrastructure/db/models/` (one file per table) and import it in that package's `__init__.py`, then:

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
