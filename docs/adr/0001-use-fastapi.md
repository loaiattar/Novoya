# 0001. Use FastAPI for the backend

- **Status:** Accepted (written down after the decision)
- **Date:** 2026-10-17
- **Issue / PR:** #4 (M0 setup)

## Context

The backend has to serve a REST API to the React app, call an LLM during requests, read and
write PostgreSQL, and render a PDF quote. The team writes Python, and the LLM SDK
(`openai`) and the PDF tool (WeasyPrint) are Python libraries. The frontend wants typed API
calls without writing the types twice.

## Decision

We build `apps/api` with Python 3.12 and FastAPI, with Pydantic v2 for the request and
response schemas, SQLAlchemy 2 (async) for the database and Alembic for migrations. `uv`
manages the dependencies.

FastAPI writes the OpenAPI file (`apps/api/openapi.json`); the web app generates its
TypeScript client from it with `@hey-api/openapi-ts`.

## Consequences

- Types are shared through `openapi.json`. CI fails when the committed file is out of date,
  so every endpoint change regenerates it.
- Pydantic also checks the JSON the LLM returns (`run_structured`), not only the HTTP input.
- Everything is async, from the route to the database and the LLM call, so one slow model
  answer does not block other requests.
- FastAPI's dependency injection is where each module plugs its adapters into its use cases
  (`presentation/http/dependencies.py`, see [0002](0002-modular-monolith.md)).
