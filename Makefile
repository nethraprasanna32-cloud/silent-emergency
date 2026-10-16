.PHONY: up down migrate test demo import api
up:
	docker compose up -d --build
down:
	docker compose down
migrate:
	docker compose exec -T db psql -U sed_admin -d sed -f /dev/stdin < db/migrations/001_core.sql
test:
	python -m pytest -q
api:
	python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
import:
	python -m importers.run --source $(SOURCE) --file $(FILE)
demo: up
	python -m importers.run --source beneficiaries --file data/samples/beneficiaries.csv --dry-run
