# Novoya frontend

pnpm, Vite, React, TanStack Router / Query / Form. Architecture is unchanged.

- Screens (Atomic Design): [docs/ATOMIC.md](docs/ATOMIC.md)
- Business rules (`src/domain/`): [docs/DOMAIN.md](docs/DOMAIN.md)
- React hooks (`src/hooks/`): [docs/HOOKS.md](docs/HOOKS.md)

## Commands

Node 22+. Use pnpm 12.4.1 (`corepack prepare pnpm@12.4.1 --activate`, or `npm exec pnpm@12.4.1`).

```bash
pnpm install
pnpm dev
pnpm test
pnpm lint
pnpm typecheck
```

`pnpm gen` rebuilds the OpenAPI client (`src/api/generated`) and the route tree (`src/routeTree.gen.ts`). Dev, test and build run it first.

## Wiring (where packages live)

| Package | Where | Not in |
|---|---|---|
| TanStack Router | `src/routes/`, `src/main.tsx` | `components/`, `domain/` |
| TanStack Query | `src/api/queryClient.ts`, providers in `main.tsx` | `domain/`, atoms |
| TanStack Form | later, on pages / molecules that are forms | `domain/` |
| `@hey-api/openapi-ts` | `openapi.json` → `src/api/generated/` | hand-edited files |
| Vitest | `src/test/` | |
| oxlint | `pnpm lint` | |

Pages stay the only glue. Components still do not fetch.
