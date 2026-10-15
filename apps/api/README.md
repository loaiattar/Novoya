# Novoya API

FastAPI backend. See [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md).

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

Add models in `src/novoya_api/models.py`, then:

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
