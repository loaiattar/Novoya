# Novoya API

FastAPI backend. See [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md).

## Clean Architecture

The code follows Clean Architecture: four layers, and source code dependencies only point inward.

```
presentation/  ──►  application/  ──►  domain/
infrastructure/ ──►  application/  ──►  domain/
```

| Layer | What it holds | May import |
|---|---|---|
| `domain/` | Entities (User, Offer, Wish, Plan, Quote), value objects, business rules, domain errors | Only the domain and the standard library |
| `application/` | Use cases, one per user action, and ports: the interfaces they need (repositories, LLM, PDF, email) | Domain |
| `infrastructure/` | Adapters that implement the ports: SQLAlchemy, OpenRouter, WeasyPrint, SMTP, Google OAuth | Application, domain |
| `presentation/` | FastAPI routers and Pydantic schemas: turn HTTP into use case calls | Application, domain |

`main.py` and `presentation/http/dependencies.py` are the composition root: the only places that plug infrastructure adapters into use cases. `tests/test_architecture.py` fails if any import breaks these rules, and runs in CI.

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

### Adding a feature, step by step

`/health/db` is the worked example. For a new feature, for example "ask for a quote" (#50):

1. **Domain**: add the rule to the entity, `Plan.request_quote()`, which raises `InvalidTransition` unless the plan is `proposed`.
2. **Application**: write the use case `use_cases/request_quote.py`. It takes a `PlanRepository` port, loads the plan, calls the rule and saves it. Test it with a fake repository.
3. **Infrastructure**: implement `PlanRepository` in `db/repositories/plans.py` with SQLAlchemy.
4. **Presentation**: add the schema and the route in `routers/plans.py`; wire the use case in `dependencies.py`.

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
