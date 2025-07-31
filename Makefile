ENV_FILE ?= .env
# overrideable: make ENV_FILE=ci.env test
SHELL     := /bin/bash

export-env: ## export vars only when $(ENV_FILE) exists
	@if [ -f "$(ENV_FILE)" ]; then \
	   set -a; \
	   . "$(ENV_FILE)"; \
	   set +a; \
	fi

# --- util -----------------------------------------------------------
install: ## install JS + Py deps
	pnpm install
	pip install -r requirements.txt --upgrade pip setuptools

lint:    ## eslint
	pnpm run lint

# --- tests ----------------------------------------------------------
test: install export-env ## Jest + Pytest (excl. RLS)
	pnpm test && pytest -q -m "not rls" tests

test-rls: export-env        ## Row-Level-Security smoke suite
	pytest -q -m rls tests/security/test_rls.py

# --- devops helpers -------------------------------------------------

mcp-install:
	python3 -m pip install --upgrade pip setuptools
	python3 -m pip install -r services/mcp-hub/requirements.txt

mcp-test:
	( \
	  uvicorn app.main:app --app-dir services/mcp-hub --host 127.0.0.1 --port 8000 & \
	  SERVER_PID=$$!; \
	  echo "⏳ Esperando a MCP…"; \
	  for i in $$(seq 1 20); do \
	    nc -z 127.0.0.1 8000 && break; \
	    sleep 0.5; \
	  done; \
	  pytest -q services/mcp-hub/tests; \
	  kill $$SERVER_PID; \
	)

db-up: ## start Postgres in Docker, fail if port busy
	@if lsof -i:5432 -sTCP:LISTEN >/dev/null ; then \
	    echo "Port 5432 already in use — stop local Postgres or change mapping." ;\
	    exit 1 ;\
	  fi
	docker compose up -d db

db-reset: db-up             ## re-apply Prisma migrations
	pnpm prisma migrate reset --force --skip-seed

.PHONY: export-env install lint test test-rls db-up db-reset

psql:
	psql "$(DB_URL)" -v ON_ERROR_STOP=1 -c "SELECT version();"
