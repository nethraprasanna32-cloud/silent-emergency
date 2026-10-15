.PHONY: up down migrate test demo import
up:
	docker compose up -d --build
down:
	docker compose down
migrate:
	docker compose exec -T db psql -U sed_admin -d sed -f /dev/stdin < db/migrations/001_core.sql
test:
	python -m pytest -q
import:
	python -m importers.run --source $(SOURCE) --file $(FILE)
demo: up
	python -m importers.run --source beneficiaries --file data/samples/beneficiaries.csv --dry-run
