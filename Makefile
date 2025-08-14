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
	pnpm test && pytest -q -m "not rls" -ra -q tests

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

db-up: ## start Postgres in Docker (idempotent)
	docker compose up -d db

db-reset: db-up db-wait ## re-apply Prisma migrations
	pnpm prisma migrate reset --force --skip-seed

.PHONY: export-env install lint test test-rls db-up db-reset

psql:
	psql "$(DB_URL)" -v ON_ERROR_STOP=1 -c "SELECT version();"

# ───────── MCP e2e helpers ─────────
COMPOSE_PROJECT := $(shell basename "$$(pwd)")
COMPOSE_NET     := $(COMPOSE_PROJECT)_default
MCP_IMAGE       ?= mcp-hub
MCP_CONT        ?= mcp-hub
DB_DSN          ?= postgresql://lobbyleaks:l0bby@db:5432/lobbyleaks

.PHONY: mcp-build mcp-up-db db-wait mcp-run mcp-wait mcp-test-e2e mcp-curl mcp-stop mcp-down mcp-dev

mcp-build:
	@docker build -t $(MCP_IMAGE) services/mcp-hub

mcp-up-db:
	@docker compose up -d db

# Espera a que Postgres esté healthy dentro del contenedor de compose
db-wait:
	@echo "⏳ Esperando a Postgres…"
	@for i in $$(seq 1 60); do \
	  docker compose exec -T db pg_isready -U lobbyleaks >/dev/null 2>&1 && { echo "✅ DB lista"; exit 0; }; \
	  sleep 1; \
	done; \
	echo "❌ DB no respondió a tiempo"; exit 1

# Lanza el hub una vez que la DB esté lista
mcp-run: mcp-build mcp-up-db db-wait
	-@docker rm -f $(MCP_CONT) >/dev/null 2>&1 || true
	@docker run -d --name $(MCP_CONT) \
	  --network $(COMPOSE_NET) \
	  -e DATABASE_URL=$(DB_DSN) \
	  -p 8000:8000 $(MCP_IMAGE)

# Espera a que el endpoint /rpc2 responda (501 con header o 400 sin header)
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

# Todo-en-uno: build + db + run + wait + tests y SIEMPRE parar el hub
mcp-test-e2e: mcp-run mcp-wait
	@set -e; \
	pytest -q services/mcp-hub/tests; \
	status=$$?; \
	$(MAKE) -s mcp-stop; \
	exit $$status

# Curls rápidos para comprobar 400/501 manualmente
mcp-curl:
	@echo "→ sin header (esperado 400)"; \
	curl -sS -i -d '{"jsonrpc":"2.0","id":1,"method":"fetch_pdf","params":{}}' http://localhost:8000/rpc2 | sed -n '1,3p'; \
	echo "→ con header (esperado 501)"; \
	curl -sS -i -H "X-Tenant-Id: CL" -d '{"jsonrpc":"2.0","id":1,"method":"fetch_pdf","params":{}}' http://localhost:8000/rpc2 | sed -n '1,3p'

# Apaga solo el contenedor mcp (mantiene DB para siguientes corridas)
mcp-stop:
	-@docker rm -f $(MCP_CONT) >/dev/null 2>&1 || true

# Apaga todo, incluyendo la DB
mcp-down: mcp-stop
	@docker compose down -v

# (Opcional) modo dev: uvicorn local con DB en docker
mcp-dev: mcp-up-db db-wait
	@uvicorn app.main:app --app-dir services/mcp-hub --reload

# ========= Atajos de “todo en uno” =========
.PHONY: bootstrap quick verify verify-clean

# 1) Instalar deps (repo + MCP hub)
bootstrap: install mcp-install

# 2) Ruta rápida para el día a día: lint + unit + e2e MCP
quick: lint test
	$(MAKE) -s mcp-test-e2e

# 3) Pipeline completo (incluye RLS)
verify: bootstrap db-up db-wait lint test
	# Ejecutar pruebas RLS (requiere DB)
	RUN_RLS=1 $(MAKE) -s test-rls
	# End-to-end del hub en Docker (arranca hub, espera /rpc2, corre tests, y apaga el hub)
	$(MAKE) -s mcp-test-e2e

# 4) Igual que verify, pero baja todo (incluye DB) al final
verify-clean: verify
	$(MAKE) -s mcp-down


