# Silent Emergency front end

This static UI is integrated with the FastAPI service in the parent repository.

## Run locally

From the parent `DBMS` directory:

```powershell
python -m pip install -r requirements.txt
$env:DATABASE_URL="postgresql://sed_admin:your_password@localhost:5432/sed"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Then open `http://localhost:8000/ui/`. The UI calls the FastAPI service on the same origin. Start the database first so its SQL migrations run. Configure `DATABASE_URL` and `POSTGRES_PASSWORD` for the backend environment as described in the parent README.

The UI is served by FastAPI at `http://localhost:8000/ui/`. Install PostgreSQL 16 with PostGIS locally and apply the SQL files in `db/migrations` in filename order before using database-backed features. If the database is unavailable, the UI shows demo data; demo assignments do not write to the database.

## API mapping

- Needs and their linked signals: `GET /needs`
- Stock and owners: `GET /resources`
- Volunteer roster/availability: `GET /volunteers`
- Ranked candidates: `GET /needs/{id}/matches`
- Atomic assignment: `POST /matches/assign`
- Detection queue drain: `POST /scan`
- Activity and seven-day counts: `GET /history`, `GET /stats`

`script.js` contains the frontend response mapping. FastAPI's authoritative contract is available at `http://localhost:8000/openapi.json` while running.
