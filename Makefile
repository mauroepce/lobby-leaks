ENV_FILE := .env

export-env:
	@if [ -f .env ]; then \
	  set -o allexport; . .env; set +o allexport; \
	fi

install:
	pnpm install
	python3 -m pip install --upgrade pip setuptools
	python3 -m pip install -r requirements.txt

lint:
	pnpm run lint

.ONESHELL:

test: install export-env
	pnpm test &&
	pytest -q -m "not rls" tests

test-rls: install export-env
	pytest -q -m rls tests/security/test_rls.py

mcp-install:
	python3 -m pip install --upgrade pip setuptools
	python3 -m pip install -r services/mcp-hub/requirements.txt

mcp-test:
	uvicorn app.main:app --app-dir services/mcp-hub --host 0.0.0.0 --port 8000 & \
	SERVER_PID=$$!; \
	sleep 2; \
	pytest -q services/mcp-hub/tests; \
	kill $$SERVER_PID

db-up:
	./scripts/db-up.sh

db-wait:
	./scripts/db-wait.sh

db-reset: db-up db-wait
	./scripts/db-reset.sh

db-smoke:
	./scripts/db-smoke.sh

psql:
	psql "$(DB_URL)" -v ON_ERROR_STOP=1 -c "SELECT version();"
