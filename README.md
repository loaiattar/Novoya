# Novoya

Un agent IA premium et personnalisable pour créer des voyages sur mesure.

## How we work

We use Scrum with two-day sprints and XP practices (test first, pairing, continuous integration). See [docs/PROCESS.md](docs/PROCESS.md).

## Run it locally

Needs Docker with Compose.

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Web (React) | http://localhost:5173. The app reaches the API through it, at http://localhost:5173/api |
| API (FastAPI) | http://localhost:8000, docs at http://localhost:8000/docs |
| PostgreSQL | localhost:5432 (user, password and database: `novoya`) |

If a port is already taken on your machine, override it: `API_PORT=8001 docker compose up`.

The AI features need an OpenRouter key. Put it in a `.env` file at the repo root (it is not committed): `NOVOYA_OPENROUTER_API_KEY=sk-or-...`. Without it, the API still starts, but every LLM call fails. To change the models, set `NOVOYA_LLM_MODEL` and `NOVOYA_LLM_FALLBACK_MODELS` in the same file; [apps/api/.env.example](apps/api/.env.example) explains them.

After a `git pull`, keep `--build`: the API image holds the Python packages, and a new one is missing until you rebuild (`ModuleNotFoundError`).

## Load the client's catalog (DÉTOUR)

Without it, the app has no destinations, offers or reviews. They come from the client's export, a `detour.sqlite` file. **It is not in git or in `docker-compose.yml`**: it holds partner contacts and reviews, which are personal data. Each of us imports it into their own local database, once.

1. Ask a teammate for `DETOUR.zip`, privately: never through git, an issue or a public channel. Unzip it **outside** the repository, for example in `~/Downloads/DETOUR`. Find the folder that holds `detour.sqlite` (it is called `livraison`).
2. Start the app with the latest image: `docker compose up -d --build`.
3. Import the file. Put the path of **your** `livraison` folder before `:/detour`:

   ```bash
   docker compose run --rm -v "$HOME/Downloads/DETOUR/livraison:/detour:ro,z" api \
     python -m novoya_api.catalog.infrastructure.detour --source /detour/detour.sqlite
   ```

   It prints `imported 396 partners, 792 offers, 54 reviews, 104 extras`. The `-v` part lends the folder to the container for this one command, read-only.
4. Reload http://localhost:5173: the destinations, offers and reviews are now the client's.

When a teammate shares a newer export, run step 3 again: it updates the same rows. An admin can also upload it on http://localhost:5173/admin/import, which runs the same import and keeps no copy of the file. If you ran the made-up seed (`python -m novoya_api.catalog.infrastructure.seed`) on this database before, its partners stay next to the client's. To start clean, run `docker compose down -v`, then steps 2 and 3. This also deletes your local accounts.

To work without Docker, see [apps/api](apps/api/README.md) and [apps/web](apps/web/README.md). The architecture is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), and the backend (modules + Clean Architecture) is explained in [docs/BACKEND.md](docs/BACKEND.md).

## Contributing

`main` is protected. The team works on `dev`, and every feature lives on its own branch that is merged into `dev` through a pull request. See [CONTRIBUTING.md](CONTRIBUTING.md).
