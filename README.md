# Novoya

Un agent IA premium et personnalisable pour créer des voyages sur mesure.

## Run it locally

Needs Docker with Compose.

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Web (React) | http://localhost:5173 |
| API (FastAPI) | http://localhost:8000, docs at http://localhost:8000/docs |
| PostgreSQL | localhost:5432 (user, password and database: `novoya`) |
| Redis | localhost:6379 |

If a port is already taken on your machine, override it: `API_PORT=8001 docker compose up`.

To work without Docker, see [apps/api](apps/api/README.md) and [apps/web](apps/web/README.md). The architecture is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Contributing

`main` is protected. The team works on `dev`, and every feature lives on its own branch that is merged into `dev` through a pull request. See [CONTRIBUTING.md](CONTRIBUTING.md).
