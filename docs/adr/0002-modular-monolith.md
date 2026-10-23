# 0002. One repository, and a modular monolith with Clean Architecture

- **Status:** Accepted (written down after the decision)
- **Date:** 2026-10-17
- **Issue / PR:** #4 (M0 setup)

## Context

Three developers have five days to build one product: a web app and its API. The project is
graded on Clean Architecture. Several people work on the backend at the same time, so each
part of the business must have an owner and change without breaking the others.

## Decision

**One repository** holds both apps and the shared setup:

- `apps/web`: React + TanStack (pnpm), laid out in Atomic Design.
- `apps/api`: FastAPI (uv).
- `docs/`, `docker-compose.yml` (PostgreSQL, API, web, Mailpit) and the CI workflows.

**The backend is a modular monolith:** one application and one database, split into
business modules (`accounts`, `catalog`, `wishes`, `planning`, `quoting`), plus `health` as
the example and `shared` for what all modules use. Inside each module, the same Clean
Architecture layers: domain, application (use cases and ports), infrastructure (adapters),
presentation (router, schemas, composition root). Dependencies only point inward.

A module uses another one only through its `public.py`, and only from its infrastructure,
its presentation or its own `public.py`.

## Options considered

- **Microservices:** one service per module would mean several deployments, network calls
  and data copies for a five-day project. The module boundaries give the same separation
  inside one process.
- **One flat backend (no modules):** quicker to start, but every developer would touch the
  same files and the layers would leak into each other.

## Consequences

- `tests/test_architecture.py` reads every import and fails in CI when a layer or a module
  breaks the rules.
- One pull request can change the API and the web app together, and `openapi.json` stays in
  line with both.
- A module can be split out later, since its only entry point is `public.py`.
- More files per feature than a flat backend. [BACKEND.md](../BACKEND.md) explains the
  layout, and `health` is the complete example to copy.
