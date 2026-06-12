# LobbyLeaks — Frontend

Next.js 14 App Router app that consumes the public API (`apps/api`) to
expose two routes:

- `/` — search input over Person and Organisation
- `/graph/[id]` — Cosmograph-backed subgraph centered on the given entity

## Dev setup

```bash
# 1. Install deps (separate from the root pnpm — Next manages its own)
cd apps/frontend
pnpm install

# 2. Configure
cp .env.example .env
# tweak NEXT_PUBLIC_API_BASE_URL if the API isn't on localhost:8000

# 3. Run dev server
pnpm dev
```

Open http://localhost:3000.

In a separate shell, start the API (it must be reachable at the URL above):

```bash
cd apps/api
.venv/bin/uvicorn app.main:app --reload --port 8000
```

The API reads `DATABASE_URL` from the repo-root `.env` — make sure that's
pointing at Neon (or another canonical store).

## Production build

```bash
pnpm build
pnpm start
```

Deployment target: Vercel (handled in module 04). The build output is a
standard Next.js app; no special server requirements beyond Node 20+.

## Architecture

- **Server Components by default.** Data fetched in RSC; only the
  `GraphView` is `"use client"` because Cosmograph needs the DOM.
- **No state library.** Search uses URL params; the graph page reads
  `[id]` from the route. Cosmograph holds its own internal state.
- **Types reused from the generated SDK** at `clients/ts/models/`.
  Runtime requests use thin fetch wrappers in `src/lib/api.ts` so we
  skip the SDK's heavier OpenAPI-generator base class.
- **Tailwind only**, no Shadcn yet — keep the dependency surface small
  until we have actual reusable components to extract.

See [modules/03-frontend/CLAUDE.md](../../modules/03-frontend/CLAUDE.md)
for the full convention set and
[modules/03-frontend/STATUS.md](../../modules/03-frontend/STATUS.md) for
the live to-do list.
