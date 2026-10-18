# Silent Emergency Database (SED)

PostgreSQL/PostGIS-first prototype for consent-gated silent-need inference and assistance allocation. Python exposes a thin FastAPI API and a local-file importer. The current repository is an incomplete implementation foundation, not a validated final submission.

## Requirements

- Python 3.12+ for the API/importer (tested here with Python 3.14.5)
- PostgreSQL 16 with the PostGIS extension for database-backed workflows

## Start

```powershell
python -m pip install -r requirements.txt
$env:DATABASE_URL = "postgresql://sed_admin:your_password@localhost:5432/sed"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open the integrated front end at `http://localhost:8000/ui/`. It calls the same FastAPI origin, so local use does not require a separate front-end server or CORS setup. When the database is unavailable the page falls back to its clearly labeled demo data.

Apply the SQL files in `db/migrations` in filename order to the local database before using database-backed features. The Docker Compose files remain available as an optional deployment path, but Docker is not required for local API/UI debugging.

Run the local unit tests with `python -m pytest -q`. The importer supports `python -m importers.run --source ngos --file path.csv --dry-run`; without `--dry-run`, it records source rows in PostgreSQL staging tables. Source-specific core entity upserts are not yet implemented.

## Implemented foundation

- Spatial/entity schema, temporal need history, signal and rule catalogs, transactional change-event triggers.
- Decay scoring and bounded event worker functions, initial candidate feature view and SciPy assignment helper.
- Reservation, audit chain, lifecycle hooks, initial FastAPI endpoints and config-driven import parsing/staging.
- Patent dossier drafts under `docs/patent` describe the design and call out missing pieces.

## Validation status

Python checks include API/OpenAPI and SQL grammar checks; PostgreSQL migration statements parse with `pglast`. No performance or patentability claims are made. See `docs/assumptions.md` and `docs/loop_log.md` for gaps.
