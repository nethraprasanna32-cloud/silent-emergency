# Silent Emergency Database (SED)

PostgreSQL/PostGIS-first prototype for consent-gated silent-need inference and assistance allocation. Python exposes a thin FastAPI API and a local-file importer. The current repository is an incomplete implementation foundation, not a validated final submission.

## Requirements

- Docker Engine with Compose (PostgreSQL 16 + PostGIS image)
- Python 3.12+ for the API/importer (tested here with Python 3.14.5)

## Start

```powershell
python -m pip install -r requirements.txt
docker compose up -d --build
```

Open the integrated front end at `http://localhost:8000/ui/`. It calls the same FastAPI origin, so local use does not require a separate front-end server or CORS setup. When the database is unavailable the page falls back to its clearly labeled demo data.

The database is published on host port `5433` by default because port `5432` is often already used by another local PostgreSQL service. Set `SED_DB_HOST_PORT=5432` only when that port is free.

On a new database volume, the SQL files in `db/migrations` are applied by the Postgres image in filename order. To rebuild from zero, run `docker compose down -v` and then `docker compose up -d --build`.

Run the local unit tests with `python -m pytest -q`. The importer supports `python -m importers.run --source ngos --file path.csv --dry-run`; without `--dry-run`, it records source rows in PostgreSQL staging tables. Source-specific core entity upserts are not yet implemented.

## Implemented foundation

- Spatial/entity schema, temporal need history, signal and rule catalogs, transactional change-event triggers.
- Decay scoring and bounded event worker functions, initial candidate feature view and SciPy assignment helper.
- Reservation, audit chain, lifecycle hooks, initial FastAPI endpoints and config-driven import parsing/staging.
- Patent dossier drafts under `docs/patent` describe the design and call out missing pieces.

## Validation status

Python checks include API/OpenAPI and SQL grammar checks; PostgreSQL migration statements parse with `pglast`. Database migrations, SQL assertions, concurrency, RLS, performance benchmarks and crash recovery have not been run: Docker CLI is installed in the authoring environment, but no Docker Desktop executable/daemon or local `psql` is available. No performance or patentability claims are made. See `docs/assumptions.md` and `docs/loop_log.md` for gaps.

Front-end routes, OpenAPI schema, CORS defaults and request conventions are documented in [docs/frontend-integration.md](docs/frontend-integration.md). The API is not safe for public exposure until authentication and authorization are integrated.
