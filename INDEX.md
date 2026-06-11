# Workspace Index

<!--
  How to use: this is the bird's-eye view of every module in the workspace.
  Add a row per module (one line each). /new-project does this automatically.
-->

| Module | Status | Last updated | Detail |
|--------|--------|--------------|--------|
| [01-supabase-migration](modules/01-supabase-migration/) | In progress | 2026-06-11 | Canonical store on Neon Pro (sa-east-1); full InfoLobby sync v2 loaded 84k persons / 90k orgs / 267k events / 539k edges; MVs refreshed |
| [02-public-api](modules/02-public-api/) | In progress | 2026-06-11 | Stage 3 — `GET /api/v1/search` shipped (PR #105, Mar 2026); `/graph` + security/auth still open |
| 03-frontend | Not started | — | Stage 4: search UI + Cosmograph viz + side panels + donation tables; consumes 02 |
| 04-deployment-auth | Not started | — | Fly.io for API + Vercel for frontend + admin auth + monitoring; depends on 02 + 03 |
