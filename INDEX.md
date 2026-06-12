# Workspace Index

<!--
  How to use: this is the bird's-eye view of every module in the workspace.
  Add a row per module (one line each). /new-project does this automatically.
-->

| Module | Status | Last updated | Detail |
|--------|--------|--------------|--------|
| [01-supabase-migration](modules/01-supabase-migration/) | In progress | 2026-06-11 | Canonical store on Neon Pro (sa-east-1); full InfoLobby sync v2 loaded 84k persons / 90k orgs / 267k events / 539k edges; MVs refreshed |
| [02-public-api](modules/02-public-api/) | In progress | 2026-06-11 | Stage 3 — `GET /api/v1/search` + `GET /api/v1/graph` (PR #109) shipped; auth/rate-limiting (E3.0-S3) still open |
| [03-frontend](modules/03-frontend/) | In progress | 2026-06-12 | Stage 4 — Next.js 14 at `apps/frontend/` with search + Cosmograph graph viz; side panels + donation tables + auth deferred |
| 04-deployment-auth | Not started | — | Fly.io for API + Vercel for frontend + admin auth + monitoring; depends on 02 + 03 |
