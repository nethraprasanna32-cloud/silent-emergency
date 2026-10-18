.PHONY: dev test import api docker-up docker-down
dev:
	python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
test:
	python -m pytest -q
api:
	$(MAKE) dev
import:
	python -m importers.run --source $(SOURCE) --file $(FILE)

# Optional container workflow; local development does not depend on Docker.
docker-up:
	docker compose up -d --build
docker-down:
	docker compose down
