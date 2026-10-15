# Assumptions and known implementation limits

- Workspace began empty; the implementation is being bootstrapped without pre-existing product requirements or identifiers.
- Runtime target is PostgreSQL 16 with PostGIS. Docker CLI is present, but the Docker Desktop engine was unavailable at build time and `psql` is not installed. Database migrations have not been executed in this environment.
- H3 is optional; the initial schema uses PostGIS geometry and geography indexing.
- Offline mode is the default. Geocoding through an external service is intentionally absent.
- Dossier content describes implemented mechanisms and flags incomplete paths. No prior-art citations or fabricated performance values are asserted.
- The current importer parses and validates mapped input and emits reports, but does not yet persist normalized records to PostgreSQL; API and matcher coverage is partial.
- The SQL optimizer component currently provides a Hungarian assignment helper and candidate feature view. It is not yet orchestrated into automatic match creation or min-cost-flow allocation.
- RLS policies and the SERIALIZABLE assignment path are authored but remain unverified against a live PostgreSQL server.
- The API now exposes an OpenAPI contract, CORS and endpoint request validation, but it does not implement end-user authentication or trusted role propagation to PostgreSQL. Public deployment is not safe until those controls exist.
- The API's person display name remains a plaintext field; full pgcrypto-backed PII handling is incomplete.
