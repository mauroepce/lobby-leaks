# 03-frontend — Conventions

## Type

Public-facing investigative UI (Stage 4 of the roadmap). Consumes the
public API (`apps/api/`) to surface searchable entities and an
interactive graph visualization. Lives at `apps/frontend/`.

## Stack / tooling

- Next.js 14 (App Router, RSC, Server Actions)
- TypeScript (strict)
- Tailwind CSS for styling — no Shadcn yet, no CSS-in-JS
- `@cosmograph/react` for graph visualization (WebGL, scales to 500k+ nodes)
- Native `fetch` (no Tanstack Query) — RSC handles caching and revalidation
- Generated TypeScript SDK at [clients/ts/](../../clients/ts/) — types
  are reused, but the SDK's runtime is heavy for our use case so we
  call the API with thin `lib/api.ts` wrappers

## Conventions

- **No client components by default.** Anything that doesn't need
  browser-only APIs (interactive state, refs, event handlers) stays in
  RSC. The graph page is a `"use client"` because Cosmograph needs the
  DOM; everything else streams from the server.
- **Tenant lives in the URL or a cookie**, not local state. For MVP we
  hardcode `tenant=CL`; once we have multi-country traffic, a tenant
  selector flips it. Never read tenant from request body.
- **Data fetched in Server Components**, passed as props to Client
  Components. The Client Components are pure viz / interaction.
- **Tailwind only**, no custom CSS. Component composition over abstraction
  until we have 3+ duplications.
- **Routes are dumb URLs**: `/` (search), `/graph/[id]` (focus on an
  entity), no query-string state for v1.
- **The TS SDK is auto-generated**; do not hand-edit anything under
  `clients/ts/`. If you need a new field in a response, change
  `docs/openapi.yaml`, run `pnpm gen-sdk`, and use the new type.
- The API needs **CORS** enabled for the frontend's dev origin
  (`localhost:3000`) and production origin — handled in `apps/api`.

## File layout

```
apps/frontend/
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── next.config.mjs
├── postcss.config.mjs
├── README.md
└── src/
    ├── app/
    │   ├── layout.tsx           # root layout + Tailwind globals
    │   ├── page.tsx             # search page (RSC)
    │   ├── globals.css
    │   └── graph/
    │       └── [id]/
    │           ├── page.tsx     # graph page shell (RSC, fetches data)
    │           └── graph-view.tsx  # Cosmograph wrapper ("use client")
    ├── lib/
    │   ├── api.ts               # thin fetch wrappers around /search and /graph
    │   └── env.ts               # API_BASE_URL etc, validated at startup
    └── components/
        ├── search-input.tsx
        ├── search-results.tsx
        └── role-legend.tsx
```

## How to run / reproduce

```bash
# Frontend deps (its own node_modules — Next can't share with the root pnpm one)
cd apps/frontend
pnpm install

# Dev server (needs API_BASE_URL pointing at a running apps/api)
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 pnpm dev

# Build
pnpm build

# Production
pnpm start
```

In another shell, start the API:

```bash
cd apps/api
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Open http://localhost:3000.
