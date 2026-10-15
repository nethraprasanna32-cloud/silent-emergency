# Iteration log

## I1 — Core schema and spatial foundation
1. Goal: establish normalized entities, geographic types and integrity constraints.
2. Files: `db/migrations/001_core.sql`, Compose, initial dossier diagrams.
3. Proving checks: clean PostgreSQL 16/PostGIS rebuild; SQL assertions for key constraints.
4. Verification: migration syntax and spatial index definitions reviewed; runtime rebuild unavailable because Docker daemon is stopped.
5. Fix cycles: not run; blocker recorded as environment limitation, no claims of test success.
6. Docs: architecture, ER, normalization and assumptions describe implemented schema only.
7. Result: base entities and indexes added. Runtime metrics unavailable.
8. Next: complete import persistence, ECA processing and SQL matching; validate in live database.

## I2 — Import reader and mapping foundation
1. Goal: read common local formats and apply source YAML transformations.
2. Files: `importers/run.py`, `importers/mappings/*.yml`, unit tests.
3. Proving checks: pytest for conversion/default/required behavior.
4. Verification: DB staging and provenance are schema-only; end-to-end importer not proven.
5. Fix cycles: tests run once; record outcome after execution.
6. Docs: document offline/no-network importer behavior and persistence gap.
7. Result: command supports CSV, XLSX, JSON, GeoJSON, dry-run and row rejection report.
8. Next: integrate source-specific core upsert, entity resolution and quality reports.

## I1/I2 verification addendum
- Python tests: `2 passed`; compileall passed.
- SQL rebuild and EXPLAIN: not run because no Docker daemon or local psql. No SQL-runtime assertion claimed.
- Importer now persists raw and normalized staging rows, errors and per-batch metadata when DATABASE_URL points at an initialized database. Core upsert remains pending.
- Commit I1: `44ec259`.
- Commit I2: `249a0a3`.

## I7 partial — Candidate cost and assignment solver
1. Goal: create SQL candidate features and global assignment primitive.
2. Files: `db/migrations/004_matching.sql`, `app/matching.py`, simulation route.
3. Proving checks: unit assignment matrix test and static compilation.
4. Verification: database view, query plan, and end-to-end transaction not run (engine unavailable).
5. Fix cycles: one code review pass; limitations remain documented.
6. Docs: patent description marks optimizer orchestration as incomplete.
7. Result: candidate view and SciPy linear-sum assignment helper exist; fairness cost is parameterized.
8. Next: finish source-specific import upsert, complete API and transaction retry, then run full DB suite.

## I12 partial — API and lifecycle endpoints
1. Goal: expose the database workflow through thin FastAPI handlers.
2. Files: `app/main.py`, `db/migrations/005_api_lifecycle.sql`.
3. Proving checks: Python compilation and unit suite.
4. Verification: live route integration cannot run without PostgreSQL; API coverage incomplete.
5. Fix cycles: one review pass; transaction-retry assignment route uses SERIALIZABLE connections.
6. Docs: dossier does not claim full API or product readiness.
7. Result: signal/person/household write, needs/history/explain, match lifecycle, metrics, heatmap, idle resources and audit endpoints exist.
8. Next: implement upload persistence and source upserts; start database for migration and concurrency verification.

## I14 partial — Packaging and verification blocker
1. Goal: package setup instructions and record the actual validation boundary.
2. Files: `README.md`, migration set, test suite and dossier.
3. Proving checks: `python -m pytest -q` and Python compileall.
4. Verification: 4 Python tests pass; Docker engine/executable and psql are absent, so no database rebuild, SQL assertions, EXPLAIN, crash test or benchmark ran.
5. Fix cycles: no SQL-runtime cycle possible in this environment; no fabricated workaround or metric was added.
6. Docs: patent effect section makes no numerical claim; assumptions enumerate incomplete functionality.
7. Result: packaged runnable setup instructions, but exit criteria are not met.
8. Next: run with a live PostgreSQL 16/PostGIS environment and finish unimplemented matching, importer, privacy and benchmark requirements.

## Follow-up — Front-end contract hardening
- Added browser CORS configuration, API-version response header, upload endpoint, resource/availability/consent routes, audit paging and OpenAPI contract tests.
- Added advisory-lock-backed idempotency-key payload binding for API write workflows and stable database error responses.
- Added `docs/frontend-integration.md`; documented that public auth/RBAC, encrypted display-name storage, full importer upserts, live SQL validation and benchmark exit criteria remain incomplete.
- Verification: `10 passed`; compileall passed; `pglast` parsed all five migration files. This is a grammar check only and does not execute SQL or validate PL/pgSQL function bodies.
