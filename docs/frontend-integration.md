# Front-end integration contract

## Base URL and API description

The development server listens at `http://localhost:8000`. FastAPI publishes the machine-readable OpenAPI contract at `/openapi.json` and interactive docs at `/docs`. The API is versioned in metadata as `1.0.0` and replies with `X-SED-API-Version: 1`. The backend supports browser development origins `http://localhost:3000` and `http://localhost:5173`; set `SED_CORS_ORIGINS` to a comma-separated list of exact origins for deployment.

The browser must call the API only; it must never connect directly to PostgreSQL. Set `DATABASE_URL` for the service process and keep it private. `SED_DB_CONNECT_TIMEOUT` controls the connection timeout (default 5 seconds). `POSTGRES_PASSWORD` must be set to a private value outside local development.

## Request conventions

- JSON request and response bodies use `snake_case` fields.
- All mutating routes require an idempotency token, either `idempotency_key` in the JSON body or the `Idempotency-Key` header as shown in OpenAPI.
- Repeating the same key and payload returns the original response. Reusing a key with another operation or payload returns HTTP 409.
- Timestamps are RFC 3339/ISO 8601. Intervals are represented in the API as separate start/end timestamps.
- Errors use FastAPI validation details for invalid request shapes. Database conflicts return 409, constraint failures return 422, and unavailable database connections return 503 with `{ "error": { "code", "message" } }`.
- Import uploads use `multipart/form-data` fields `source` and `file`; maximum file size is 50 MiB. Successful imports return HTTP 202 and a `batch_id`.

## Main browser workflows

1. `POST /persons` with a pseudonym and explicit `inference_consent`; preserve the returned `id`.
2. `POST /signals` with that `person_id`, a catalog `signal_type`, occurrence timestamp, source and idempotency key.
3. Poll `GET /needs?status=suspected&area={area_id}` and render `GET /needs/{id}/explain` and `/history` for authorized staff.
4. Use `POST /simulate` to preview candidates. `POST /matches/assign` accepts a JSON body with need, volunteer/resource identifiers, quantity and idempotency key; this is an administrative assignment action.
5. A coordinator or volunteer uses the match accept/reject/complete route with a JSON idempotency key. Render `GET /matches` to refresh the queue.
6. Use `POST /imports` and then `GET /imports/{id}/report` for local registry imports.

Example signal request:

```json
{
  "signal_type": "missed_checkin",
  "person_id": 42,
  "occurred_at": "2026-10-15T09:30:00Z",
  "source": "community_checkin",
  "idempotency_key": "checkin-42-20261015",
  "payload": {"missed_count": 2}
}
```

## Operational boundary

This contract makes the API discoverable to a front end, but it does not implement end-user authentication or a complete role-authorization layer. Do not expose the service publicly until an authentication/authorization gateway and PostgreSQL role identity propagation are configured and reviewed. The migrations and API also still require integration testing against a live PostgreSQL 16/PostGIS instance; see `docs/assumptions.md`.
