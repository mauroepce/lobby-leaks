# 01-supabase-migration — STATUS

**Last updated:** 2026-06-11
**Phase / status:** In progress — full canonical pipeline green end-to-end against InfoLobby SPARQL. With `--limit 10` smoke: Person=25, Organisation=30, Event=30, Edge=55 (PASIVO/ACTIVO/REPRESENTADO/FINANCIADOR/DONANTE), MVs populated. Ready to write the production orchestrator and run an unbounded sync.

<!--
  LIVE state. Update at the end of every productive session.
-->

## State

User created a Supabase project under `admin@lobbyleaks.org` (institutional
email forwarded via Namecheap to personal Gmail). The project is ready to
receive Prisma migrations. Local `.env` was previously tracked in git (security
issue fixed today: `.gitignore` updated, file untracked via `git rm --cached`).
No data loaded yet. `services/info_lobby_sync` lacks a CLI entry point — a
thin orchestrator script will be written during this milestone.

## TODOs

```
[x] Fix .gitignore so .env is properly ignored
[x] Untrack .env from git (git rm --cached, file preserved on disk)
[x] URL-encode password special chars in .env (@→%40, !→%21)
[x] Switch DIRECT_URL from db.* host (IPv6-only) to Session Pooler port 5432 (IPv4-compatible)
[x] Pin Node 20 with .nvmrc (workspace requires Node ≥18.12; user had v16 globally)
[x] Free disk space (deleted 9.1 GB Yarn cache; was 100% full → now 13 GB free)
[x] Commit toolchain pins + Leak migration fix + module skeleton (98708ca)
[x] User unpaused Supabase project; Session Pooler started serving in ~60s after restore
[x] Apply Prisma migrations (13 original + new 20260610 for missing `source` column)
[x] Seed Tenant (CL, UY) + Leak + User via `scripts/seed.sql`
[x] Install Python 3.11 via Homebrew (Intel Mac, source build ~10 min)
[x] Create `.venv` with Python 3.11 + install `services/info_lobby_sync/requirements.txt`
[x] Write smoke-test orchestrator at `scripts/sync_infolobby_smoke.py` (limit=10, 1 req/s)
[x] Run smoke test → 25 Persons + 30 Organisations inserted; status=ok
[x] Refresh materialized views → mv_graph_nodes=55, mv_graph_links=55 after full pipeline run
[x] Wire Event persister into `info_lobby_sync`
      → added `services/info_lobby_sync/event_persistence.py`
      → natural key (tenantCode, externalId, kind); per-subtype fields in JSONB metadata
[x] Fix existing bugs surfaced by smoke test:
      → `participation.load_persons_dict / load_organisations_dict` queried `tenant_code` /
        `normalized_name` (snake_case) against camelCase columns; rewritten with
        `"tenantCode"` / `"normalizedName"`
      → `participation_persistence._persist_edge` mixed psycopg `%(name)s` and
        SQLAlchemy `:name::jsonb` placeholders; switched to `CAST(:metadata AS jsonb)`
[ ] Write production orchestrator `services/info_lobby_sync/run_sync.py` (no `--limit`,
    rate-limited, JSON metrics, cron-safe exit 0)
[ ] Run full InfoLobby sync (audiencias + viajes + donativos, all pages)
[ ] Consolidate canonical upsert into `services/canonical/` once `servel_sync` reaches the
    same shape (third use case justifies the abstraction)
[ ] Decide: SERVEL CSV ingest in this module or defer to a sibling module
[ ] Register module outcome in root `INDEX.md`
```

## Key decisions

- **Supabase over self-hosted Postgres.** Reason: managed backups + connection
  pooler + RLS + free tier sufficient for MVP. How to apply: use Supabase for
  all environments during MVP; revisit when scale or cost demands it.
- **Pooler + direct URLs, two env vars.** Reason: transaction-mode pooling
  breaks Prisma migrations because they need session-level state. How to apply:
  always use `DIRECT_URL` for migrations and DDL; use `DATABASE_URL` for runtime
  application queries.
- **InfoLobby SPARQL as the only initial data source.** Reason: SERVEL has no
  API, requires manual Excel downloads — adds friction without changing the
  architecture. How to apply: load real data from InfoLobby first, prove the
  graph end-to-end, then add SERVEL as a dedicated later milestone.
- **Don't rewrite git history for the .env leak.** Reason: historic creds are
  Postgres `localhost` — not exploitable from outside. Filter-repo + force-push
  carries higher operational risk than the residual exposure. How to apply: for
  any future cloud-credential leak, ALWAYS rewrite history AND rotate keys.

- **Use Session Pooler (port 5432 via `*.pooler.supabase.com`) for `DIRECT_URL`,
  not the `db.*` direct host.** Reason: Supabase's `db.<ref>.supabase.co` only
  resolves over IPv6, and most consumer ISPs / Mac default networking are
  IPv4-only — `getaddrinfo` returns NXDOMAIN. The Session Pooler offers the
  same session-level features Prisma migrations need but over IPv4. How to
  apply: any time you need a "direct" Postgres connection from an IPv4 network,
  use the Session Pooler URL (port 5432, hostname `aws-*.pooler.supabase.com`,
  user format `postgres.<project_ref>`).

- **URL-encode special chars in connection-string passwords.** Reason: Supabase
  generated a password containing `@` and `!`. Unencoded, the `@` is parsed as
  the user/host separator and Prisma tries to connect to the wrong host. How to
  apply: always %-encode passwords (`@`→`%40`, `!`→`%21`, `#`→`%23`, `/`→`%2F`,
  `:`→`%3A`, `?`→`%3F`, ` `→`%20`) when pasting into `.env`.

- **Pin Node via `.nvmrc`.** Reason: workspace requires Node ≥18.12 (current
  pnpm version), user had v16.18 active globally. Without a pin, every fresh
  shell or new contributor hits the same wall. How to apply: `.nvmrc` at repo
  root with `20`; `nvm use` (no args) reads it; GitHub Actions `setup-node`
  reads it; one source of truth.

- **The Leak migration's `GRANT anonymous TO lobbyleaks` is wrapped in a
  conditional `DO` block.** Reason: Supabase has no `lobbyleaks` role; the
  unconditional grant aborted `prisma migrate deploy` with code 42704. The
  wrapper grants to whichever of `lobbyleaks` / `postgres` actually exists
  in the target DB. How to apply: any role-management statement in a migration
  that targets BOTH local Docker (`lobbyleaks` user) AND Supabase (`postgres`)
  must be guarded by `IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = ...)`.

- **Smoke test before full sync.** Reason: full InfoLobby sync would fetch
  thousands of records, hit the Fortinet WAF, and write a lot to Supabase. A
  silent bug (like the missing `source` column) wastes minutes of fetch time
  per attempt. How to apply: any new ingestion pipeline gets a `--limit 10`
  smoke test that exercises every stage (fetch, parse, merge, persist, count)
  before unleashing the full thing.

- **Prefer `DIRECT_URL` over `DATABASE_URL` for ad-hoc Python scripts.** Reason:
  the transaction pooler (DATABASE_URL, port 6543) rejects `?pgbouncer=true`
  with psycopg v3 and needs prepared-statement workarounds. The Session Pooler
  (DIRECT_URL, port 5432) accepts vanilla SQLAlchemy + psycopg with no special
  config. How to apply: app code that runs many short-lived queries (API
  handlers) should still use the transaction pooler with the right config; one-
  off scripts (sync, migrations, seeds) should use DIRECT_URL.

- **Use `postgresql+psycopg://` (v3) in SQLAlchemy URLs.** Reason:
  `info_lobby_sync/requirements.txt` installs `psycopg[binary]` (v3), not
  `psycopg2`. SQLAlchemy's default `postgresql://` scheme reaches for psycopg2
  and `ModuleNotFoundError` follows. How to apply: rewrite `postgresql://` →
  `postgresql+psycopg://` at the entry point (the smoke script does this in
  ~3 lines) — don't ask contributors to remember.

- **Missing `source` column was a real schema bug, not a config issue.**
  `services/info_lobby_sync/persistence.py` writes a `source` column on every
  `Person`/`Organisation` upsert but no migration ever created the column. Added
  via `20260610_add_source_to_canonical_entities` (nullable, so existing rows
  backfill to NULL). Lesson: when persistence code references a column, grep
  the migrations to confirm it exists — don't trust the code alone.

- **Chose Option 1 (per-service event persister) over Option 2 (cross-service
  reuse) for the event gap.** Reason: `info_lobby_sync` already has its own
  Person/Org persister (different from `lobby_collector`'s). Adding a
  cross-service import for only events/edges would camouflage coupling and
  produce a mixed pattern within a single service. Per-service persister
  completes the existing shape (persistence.py → event_persistence.py →
  participation_persistence.py) and keeps the service self-contained. The
  consolidation refactor remains a valid future move once `servel_sync`
  reaches the same point (third use case justifies abstraction). How to
  apply: when adding a new ingest service, mirror the InfoLobby per-service
  shape until you have ≥3 services duplicating logic; only then extract.

## Blockers

_None._ The canonical pipeline is unblocked end-to-end; remaining work is
breadth (full sync, production orchestrator, SERVEL) not depth.

## Notes

- `.env` is currently untracked but still on disk with old local-Postgres creds.
  Will be overwritten with Supabase creds in the next step.
- Existing migration `20251112_add_canonical_graph_models` creates `Person`,
  `Organisation`, `Event`, `Edge` as raw SQL — they are NOT declared as Prisma
  models in `schema.prisma`. This is intentional: Python services read via
  SQLAlchemy. Prisma Client just doesn't know about them. Don't try to "fix"
  this without a real reason.
