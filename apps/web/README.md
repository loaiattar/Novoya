# Novoya web

React + TypeScript + Vite, with TanStack Router (file-based routes), TanStack Query and TanStack Form. See [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md).

## Run locally

Needs Node 22 and pnpm. The API should run on http://localhost:8000.

```bash
cp .env.example .env
pnpm install
pnpm dev
```

The app runs on http://localhost:5173.

## Generated code

Both are created by `pnpm gen`, which `dev`, `build`, `typecheck` and `test` run first. They are not committed.

- `src/api/generated/`: the typed API client and TanStack Query helpers, from `../api/openapi.json`.
- `src/routeTree.gen.ts`: the route tree, from the files in `src/routes/`.

To call an endpoint, use the generated query options:

```tsx
import { useQuery } from '@tanstack/react-query'
import { getHealthOptions } from '../api/generated/@tanstack/react-query.gen'

const { data } = useQuery(getHealthOptions())
```

## Checks

```bash
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```
