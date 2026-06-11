# 01-supabase-migration — Conventions

<!--
  Stable conventions and reference for this milestone.
  Live state lives in STATUS.md.
-->

## Type

Infrastructure milestone — migrate the canonical Postgres schema and graph
materialized views from local Docker Postgres to a managed Supabase project,
then load real data from InfoLobby SPARQL.

## Scope

In scope:
- Supabase project provisioning (one-time, manual via dashboard).
- Apply Prisma migrations (`prisma migrate deploy`) against Supabase.
- Configure `.env` with pooler + direct connection strings.
- Run `services/info_lobby_sync` pipeline → load audiencias / donativos / viajes.
- Refresh materialized views (`services/graph_refresh`).
- Smoke tests: row counts in canonical tables + mv_graph_*.

Out of scope (handled in later modules):
- SERVEL CSV loading.
- Public API (`apps/api/`).
- Frontend (`apps/frontend/`).
- Deployment of API to Fly.io / frontend to Vercel.

## Architectural decisions (locked in for this milestone)

1. **Supabase region**: South America (São Paulo). Closest to Chile, single-digit
   ms RTT to Santiago. The next region west is `us-east-1` Virginia (~150ms RTT).

2. **Two connection strings**: `DATABASE_URL` points to the **pooler** (port
   6543, transaction mode) for application code; `DIRECT_URL` points to the
   direct Postgres (port 5432) for Prisma migrations and any DDL.
   - Why two: PgBouncer in transaction mode multiplexes connections (good for
     short-lived API calls in serverless/concurrent contexts) but does not
     support session-level features like `LISTEN/NOTIFY`, advisory locks, or
     `SET LOCAL` across statements. Prisma migrations need direct access.

3. **Multi-tenant isolation**: enforced at the application layer with a
   `WHERE "tenantCode" = :tenant` filter on every query. Database-level RLS
   (Row Level Security) is layered on top in a later module. For now the pre-
   existing RLS migrations (`20250901*`, `20250909*`) will apply automatically.

4. **InfoLobby SPARQL as primary source**: per project memory, Ley del Lobby
   API is degraded and feature-flagged off (`ENABLE_LOBBY_API=false`).

## How to reproduce

```bash
# 1. Apply migrations (requires DIRECT_URL in .env)
pnpm prisma:deploy

# 2. Verify schema
psql "$DIRECT_URL" -c "\dt"          # tables
psql "$DIRECT_URL" -c "\dm"          # materialized views
psql "$DIRECT_URL" -c "\dv"          # views

# 3. Run InfoLobby sync (script TBD in STATUS.md — written during this milestone)
python -m scripts.sync_infolobby   # or equivalent

# 4. Refresh materialized views
make refresh-graph

# 5. Smoke tests
psql "$DATABASE_URL" -c 'SELECT count(*) FROM "Person";'
psql "$DATABASE_URL" -c 'SELECT count(*) FROM "Event";'
psql "$DATABASE_URL" -c 'SELECT count(*) FROM mv_graph_nodes;'
```

## Key references

- `prisma/schema.prisma` + `prisma/migrations/`
- `services/info_lobby_sync/README.md`
- `services/info_lobby_sync/settings.py`
- `services/graph_refresh/refresh_graph.py`
- `docs/project-roadmap.md`
