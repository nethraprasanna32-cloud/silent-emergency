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
8. Next: integrate staging/upsert, entity resolution and quality reports.
