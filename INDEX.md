# Workspace Index

<!--
  How to use: this is the bird's-eye view of every module in the workspace.
  Add a row per module (one line each). /new-project does this automatically.
-->

| Module | Status | Last updated | Detail |
|--------|--------|--------------|--------|
| [01-supabase-migration](modules/01-supabase-migration/) | In progress | 2026-06-11 | Schema deployed + canonical pipeline optimized 65× + full InfoLobby sync running |
| 02-public-api | Not started | — | Stage 3: FastAPI app at `apps/api/` exposing `/search` + `/graph` over `mv_graph_*`; depends on 01 finishing the sync |
| 03-frontend | Not started | — | Stage 4: search UI + Cosmograph viz + side panels + donation tables; consumes 02 |
| 04-deployment-auth | Not started | — | Fly.io for API + Vercel for frontend + admin auth + monitoring; depends on 02 + 03 |
