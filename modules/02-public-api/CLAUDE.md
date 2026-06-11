# 02-public-api — Conventions

## Type

Public-facing HTTP API milestone (Stage 3 of the roadmap). Exposes
canonical graph data — search, then graph projections — for the
frontend and any third-party consumer. Lives at `apps/api/`.

## Stack / tooling

- Python 3.12 (per roadmap E3)
- FastAPI 0.111
- psycopg 3 + psycopg-pool for async Postgres access (Supabase)
- pytest + pytest-asyncio
- OpenAPI 3.1 spec at [docs/openapi.yaml](../../docs/openapi.yaml)
- Generated TypeScript client at [clients/ts/](../../clients/ts/)

## Conventions

- Tenant input: `tenant` query param OR `X-Tenant-Id` header. Query
  param wins on conflict; a mismatch returns `400 Conflicting tenant`.
- Every endpoint MUST honour tenant isolation in SQL
  (`WHERE "tenantCode" = :tenant`) — never trust the client.
- Read paths consume the materialized views `mv_graph_nodes` and
  `mv_graph_links` once `/graph` lands, NOT the canonical tables
  directly. Search is the exception (it reads `Person` + `Organisation`
  directly for freshness).
- TypeScript client is REGENERATED from `docs/openapi.yaml`; do not
  hand-edit anything under `clients/ts/`.
- OpenAPI spec is OAS **3.1** (nullable via `type: ["string", "null"]`).
- Inserts/migrations are NOT this module's concern — `01-supabase-
  migration` owns the schema. If a query needs a new column or index,
  add it in module 01 first.

## File layout

```
apps/api/
├── Dockerfile
├── pytest.ini
├── requirements.txt
└── app/
    ├── __init__.py
    ├── main.py            # FastAPI app factory + pool lifecycle
    ├── db.py              # Async psycopg pool + entity queries
    ├── middleware.py      # resolve_tenant dependency
    ├── schemas.py         # Pydantic response models
    └── routers/
        ├── __init__.py
        └── search.py      # GET /api/v1/search

clients/ts/                # generated TS client (do not hand-edit)
docs/openapi.yaml          # source of truth for the public contract
```

## How to run / reproduce

```bash
# Install deps (a separate venv from the ingest services)
cd apps/api
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Run locally (needs DATABASE_URL or pool config in env)
.venv/bin/uvicorn app.main:app --reload --port 8000

# Tests
.venv/bin/pytest -v

# Smoke-call /search
curl 'http://localhost:8000/api/v1/search?q=corfo&tenant=CL'

# Regenerate TS client after editing docs/openapi.yaml
pnpm gen-sdk        # via repo-root package.json
```
