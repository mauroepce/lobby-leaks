# ========= Config básica =========
ENV_FILE ?= .env
SHELL    := /bin/bash

# --- Python env pinneado (usa .venv siempre) ---
PY      := $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)
PIP     := $(PY) -m pip
PYTEST  := $(PY) -m pytest

.venv/bin/python:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip setuptools wheel

export-env: ## exporta variables si existe $(ENV_FILE)
	@if [ -f "$(ENV_FILE)" ]; then \
	   set -a; . "$(ENV_FILE)"; set +a; \
	fi

# ========= Utilidades =========
install: .venv/bin/python ## instala deps Node + Python en .venv
	pnpm install
	$(PIP) install -r requirements.txt

template-install: install ## instala deps Node + Python + template deps
	$(PIP) install -r services/_template/requirements.txt

lint: ## eslint
	pnpm run lint

# ========= Tests =========
test: install export-env
	$(PYTEST) -q -m "not rls" -ra tests

test-rls: export-env db-up db-wait seed
	$(PYTEST) -q -m rls tests/security

# ========= DB (Docker Compose) =========
db-up:
	@if [ -n "$$CI" ]; then \
	  echo "CI: saltando db-up (service db ya está levantado)"; \
	else \
	  docker compose up -d db; \
	fi

db-wait:
	@if [ -n "$$CI" ]; then \
	  echo "CI: saltando db-wait (el workflow ya espera con pg_isready)"; \
	else \
	  echo "⏳ Esperando a Postgres…"; \
	  for i in $$(seq 1 60); do \
	    docker compose exec -T db pg_isready -U lobbyleaks >/dev/null 2>&1 && { echo "✅ DB lista"; exit 0; }; \
	    sleep 1; \
	  done; \
	  echo "❌ DB no respondió a tiempo"; exit 1; \
	fi

# Aplica migraciones (no destruye datos)
migrate:
	npx prisma migrate deploy --schema=prisma/schema.prisma

seed: migrate
	npx prisma db execute --file scripts/seed.sql --schema=prisma/schema.prisma

# Reset destructivo + seed para desarrollo local
db-reset: db-up db-wait
	pnpm prisma migrate reset --force --schema=prisma/schema.prisma --skip-seed
	$(MAKE) -s seed

psql:
	psql "$${DATABASE_URL:?set DATABASE_URL}" -v ON_ERROR_STOP=1 -c "SELECT version();"

# ========= MCP e2e helpers =========
COMPOSE_PROJECT := $(shell basename "$$(pwd)")
COMPOSE_NET     := $(COMPOSE_PROJECT)_default
MCP_IMAGE       ?= mcp-hub
MCP_CONT        ?= mcp-hub
DB_DSN          ?= postgresql://lobbyleaks:l0bby@db:5432/lobbyleaks

mcp-build:
	@docker build -t $(MCP_IMAGE) services/mcp-hub

# alias que reutiliza db-up
mcp-up-db: db-up

# lanza el hub cuando la DB está lista
mcp-run: mcp-build
	-@docker rm -f $(MCP_CONT) >/dev/null 2>&1 || true
ifdef CI
	@echo "CI: ejecutando mcp-hub con --network=host y DATABASE_URL=$(DATABASE_URL)"
	@docker run -d --name $(MCP_CONT) \
	  --network host \
	  -e DATABASE_URL="$(DATABASE_URL)" \
	  $(MCP_IMAGE)
else
	$(MAKE) -s mcp-up-db db-wait
	@docker run -d --name $(MCP_CONT) \
	  --network $(COMPOSE_NET) \
	  -e DATABASE_URL=$(DB_DSN) \
	  -p 8000:8000 $(MCP_IMAGE)
endif

# espera a que /rpc2 responda (501 con header o 400 sin header)
mcp-wait:
	@echo "⏳ Esperando a mcp-hub…"
	@for i in $$(seq 1 60); do \
	  code=$$(curl -s -o /dev/null -w "%{http_code}" \
	    -H "X-Tenant-Id: CL" \
	    -d '{"jsonrpc":"2.0","id":1,"method":"fetch_pdf","params":{}}' \
	    http://127.0.0.1:8000/rpc2 || true); \
	  if [ "$$code" = "501" ] || [ "$$code" = "400" ]; then echo "✅ mcp-hub listo ($$code)"; exit 0; fi; \
	  sleep 0.5; \
	done; \
	echo "❌ mcp-hub no respondió a /rpc2 a tiempo"; exit 1

# build + db + run + wait + tests y SIEMPRE parar el hub
mcp-test-e2e: mcp-run mcp-wait
	@set -e; \
	$(PYTEST) -q services/mcp-hub/tests; \
	status=$$?; \
	$(MAKE) -s mcp-stop; \
	exit $$status

mcp-curl:
	@echo "→ sin header (esperado 400)"; \
	curl -sS -i -d '{"jsonrpc":"2.0","id":1,"method":"fetch_pdf","params":{}}' http://localhost:8000/rpc2 | sed -n '1,3p'; \
	echo "→ con header (esperado 501)"; \
	curl -sS -i -H "X-Tenant-Id: CL" -d '{"jsonrpc":"2.0","id":1,"method":"fetch_pdf","params":{}}' http://localhost:8000/rpc2 | sed -n '1,3p'

mcp-stop:
	-@docker rm -f $(MCP_CONT) >/dev/null 2>&1 || true

mcp-down: mcp-stop
	@docker compose down -v

# (opcional) modo dev: uvicorn local con DB en docker
mcp-dev: db-up db-wait
	@uvicorn app.main:app --app-dir services/mcp-hub --reload

# ========= Atajos “todo en uno” =========
bootstrap: install mcp-install ## instala deps del repo + del hub

quick: lint test ## lint + unit + e2e MCP
	$(MAKE) -s mcp-test-e2e

verify: bootstrap db-up db-wait lint test ## pipeline completo
	$(MAKE) -s seed
	$(MAKE) -s test-rls
	$(MAKE) -s mcp-test-e2e

verify-clean: verify ## igual que verify, pero baja todo al final
	$(MAKE) -s mcp-down

test-all: lint test template-test ## ejecuta todos los tests (main + template)
	$(MAKE) -s mcp-test-e2e

# ========= Helpers del hub local =========
mcp-install: .venv/bin/python
	$(PIP) install -r services/mcp-hub/requirements.txt

mcp-test:
	( \
	  uvicorn app.main:app --app-dir services/mcp-hub --host 127.0.0.1 --port 8000 & \
	  SERVER_PID=$$!; \
	  echo "⏳ Esperando a MCP…"; \
	  for i in $$(seq 1 20); do \
	    nc -z 127.0.0.1 8000 && break; \
	    sleep 0.5; \
	  done; \
	  $(PYTEST) -q services/mcp-hub/tests; \
	  kill $$SERVER_PID; \
	)

template-test: template-install ## run service template tests
	$(PYTEST) -q services/_template/tests -v

template-test-unit: template-install ## run only unit tests (mocked)
	$(PYTEST) -q services/_template/tests -v -m "not integration"

template-test-integration: template-install ## run only integration tests (real functionality)
	$(PYTEST) -q services/_template/tests -v -m integration

# ========= PHONY =========
.PHONY: migrate seed db-up db-wait db-reset verify
.PHONY: export-env install template-install lint test test-rls db-up db-wait seed db-reset psql \
        mcp-build mcp-up-db mcp-run mcp-wait mcp-test-e2e mcp-curl mcp-stop mcp-down mcp-dev \
        bootstrap quick verify verify-clean test-all mcp-install mcp-test template-test template-test-unit template-test-integration
