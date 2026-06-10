# 01-supabase-migration — STATUS

**Last updated:** 2026-06-05
**Phase / status:** Blocked — Supabase project ref `hsbejlidtugjazuqjutd` not found in any region pooler (likely auto-paused after 7-day inactivity on free tier; project created ~2026-05-14, no activity since).

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
[ ] Commit the .gitignore + URL-encoding + .nvmrc + module skeleton changes
[ ] **USER**: Unpause Supabase project in dashboard (or confirm project ref / recreate in sa-east-1 if deleted)
[ ] Re-test connection: psql "$DIRECT_URL" -c "SELECT 1;"
[ ] Run `pnpm prisma:deploy` and verify tables + materialized views exist
[ ] Write thin orchestrator at services/info_lobby_sync/run_sync.py (or scripts/sync_infolobby.py)
[ ] Run InfoLobby sync end-to-end (audiencias + donativos + viajes)
[ ] Run `make refresh-graph` to populate mv_graph_nodes / mv_graph_links
[ ] Smoke test: count rows in Person, Organisation, Event, Edge, mv_graph_*
[ ] Register this module's outcome in root INDEX.md
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

## Blockers

- **Supabase project paused or missing.** Project ref `hsbejlidtugjazuqjutd`
  returns `tenant/user ... not found` from all three regional poolers tested
  (`aws-1-sa-east-1`, `aws-0-us-east-1`, `aws-0-us-east-2`). Most likely the
  free-tier auto-pause kicked in (project created 2026-05-14, no activity since
  → exceeded 7-day inactivity threshold). User must restore from dashboard, or
  if deleted, recreate in São Paulo and share the new connection strings.

## Notes

- `.env` is currently untracked but still on disk with old local-Postgres creds.
  Will be overwritten with Supabase creds in the next step.
- Existing migration `20251112_add_canonical_graph_models` creates `Person`,
  `Organisation`, `Event`, `Edge` as raw SQL — they are NOT declared as Prisma
  models in `schema.prisma`. This is intentional: Python services read via
  SQLAlchemy. Prisma Client just doesn't know about them. Don't try to "fix"
  this without a real reason.
