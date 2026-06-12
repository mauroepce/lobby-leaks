# 03-frontend — STATUS

**Last updated:** 2026-06-11
**Phase / status:** Bootstrapping — Next.js 14 scaffold + search + Cosmograph-backed `/graph/[id]` shipped as the first MVP. Auth, donation tables, mobile polish, tests all deferred.

## State

`apps/frontend/` is a Next.js 14 App Router app with two routes:

- `/` — search input that calls `/api/v1/search?q=...&tenant=CL` from a
  Server Component, renders a results list (person/organisation chips +
  rut), and links each row to `/graph/[id]`.
- `/graph/[id]` — server-side fetches `/api/v1/graph?center=[id]&tenant=CL&depth=2`
  and renders a `@cosmograph/react` canvas with role-coloured links and
  a legend. Truncation banner appears when the API flags it.

API needs CORS for `http://localhost:3000` (dev) and the prod origin —
added in `apps/api/app/main.py`.

## TODOs

```
[x] Scaffold Next.js 14 App Router at apps/frontend/
[x] Tailwind CSS + globals
[x] lib/api.ts thin wrappers around /search and /graph
[x] Search page (RSC, no client interactivity needed yet)
[x] Graph page (RSC for data, Client Component for Cosmograph)
[x] Add CORS middleware to apps/api
[x] Role-coloured links + legend on the graph page
[ ] Interactive node click → navigate to that node's graph
[ ] Side panel showing the center entity's metadata (cargo, source, etc.)
[ ] Donation tables (E1.4 data is loaded but not surfaced yet)
[ ] Empty / loading / error skeletons (today's MVP shows raw error messages)
[ ] Mobile-responsive layout (today's MVP is desktop-first)
[ ] Tenant selector (currently hardcoded to CL)
[ ] Playwright e2e tests (manual browser smoke test only for now)
[ ] Auth UI for the future admin section (Module 04 territory)
[ ] Deploy target: Vercel (Module 04)
```

## Key decisions

- **Next.js 14 App Router over Pages Router.** Reason: RSC moves the
  network calls server-side so the browser doesn't see API tokens or
  hostname rewrites; it's also the framework's current direction. How
  to apply: every new page starts as a Server Component; flip to
  `"use client"` only when you need browser-only APIs (Cosmograph,
  event handlers, refs).

- **Native `fetch` + thin `lib/api.ts` wrappers over the generated
  TypeScript SDK runtime.** Reason: the auto-generated runtime carries
  ~30 KB of OpenAPI plumbing the App Router doesn't need; we still
  reuse the SDK's TYPES (re-exporting from `clients/ts/`) so the
  compile-time contract holds, but the request side stays minimal. How
  to apply: any new endpoint gets a typed wrapper in `lib/api.ts`; the
  generated runtime stays out of `apps/frontend/` imports.

- **Cosmograph wins over D3 / Sigma / react-flow.** Reason: roadmap
  named it, and our v1 graph payloads can reach ~10k nodes (depth-2
  around a hot center); WebGL handles that without dropping frames.
  How to apply: graph-shaped visualizations use Cosmograph; non-graph
  data viz (donation tables, timelines) uses plain HTML / Tailwind.

- **Tenant hardcoded to `CL` in v1.** Reason: we have one tenant of
  real data right now; building a tenant selector before there's a
  second tenant is premature. How to apply: when we onboard Uruguay
  or another country, the tenant flips to a URL segment (`/cl/...`,
  `/uy/...`) and a top-bar selector; do that refactor in one PR, not
  piecemeal now.

- **The TypeScript SDK is consumed type-only**, not runtime-only.
  Reason: described above (SDK runtime is heavy); also keeps the
  frontend free of an extra build step if the SDK ever changes shape.
  How to apply: imports from `clients/ts/models/*` are fine; imports
  from `clients/ts/apis/*` or `clients/ts/runtime` are NOT — wrap
  those endpoints in `lib/api.ts` instead.

## Blockers

_None._ The API is up on Neon, CORS is wired, the SDK types are
already generated.

## Notes

- For dev you run BOTH `apps/api` and `apps/frontend` in parallel
  shells; the README has the commands. Production deployment is
  Module 04 territory (Fly.io for API, Vercel for frontend).
- The TS SDK `clients/ts/` is generated; if you change
  `docs/openapi.yaml`, re-run `pnpm gen-sdk` and the new types appear
  automatically. Don't hand-edit anything in `clients/ts/`.
