# 02-public-api — STATUS

**Last updated:** 2026-06-11
**Phase / status:** In progress — E3.0-S1 (search) shipped 2026-03-24 via PR #105; E3.0-S2 (graph endpoint) and E3.0-S3 (security/auth, rate limiting, full OpenAPI coverage) still open.

## State

The FastAPI app at [apps/api/](../../apps/api/) is live with a single
endpoint `GET /api/v1/search` that returns Person + Organisation matches
by `normalizedName` or `rut`, tenant-isolated, with a `limit` cap of 100.
The OpenAPI 3.1 contract is at [docs/openapi.yaml](../../docs/openapi.yaml)
and the TypeScript client is regenerated from it under
[clients/ts/](../../clients/ts/). Three test files cover the endpoint
(unit + integration + tenant isolation).

This module was created retroactively on 2026-06-11 after discovering
PR #105 had been merged to `main` back in March via the GitHub web UI
while local `main` on this clone never pulled it — `git pull --rebase`
during today's push integrated the work cleanly.

## TODOs

```
[x] E3.0-S1 — Search endpoint (Person/Organisation by name + RUT)
[x] OpenAPI 3.1 spec at docs/openapi.yaml
[x] Generated TypeScript client at clients/ts/
[x] Tenant resolution middleware (query param vs X-Tenant-Id header)
[ ] E3.0-S2 — Graph endpoint `GET /api/v1/graph` returning `{nodes, links}`
    sourced from mv_graph_nodes / mv_graph_links
[ ] E3.0-S3 — Security + auth (admin auth for write paths if any) + rate
    limiting + request logging + structured error model expansion
[ ] Add a `Source` field projection on search results once we want to show
    provenance (Person.source / Organisation.source now exists after
    migration 20260610 — see module 01)
[ ] Deploy target: Fly.io (covered in module 04-deployment-auth)
[ ] Wire `apps/api/Dockerfile` into a CI build job
```

## Key decisions

- **OpenAPI 3.1 (not 3.0).** Reason: nullable fields use the JSON Schema
  `type: ["string", "null"]` form rather than `nullable: true`. This is
  pinned by `fix(openapi)` in PR #105. How to apply: any new schema
  field that can be null must use the array-type form; never add
  `nullable: true`.

- **TypeScript client is generated, never hand-edited.** Reason: drift
  between spec and client kills consumers silently. Repo-level script
  `pnpm gen-sdk` regenerates from `docs/openapi.yaml`. How to apply:
  any spec change → run `pnpm gen-sdk` → commit both files in the same
  commit so the SDK never sits older than its spec.

- **Search reads `Person`/`Organisation` directly, NOT `mv_graph_nodes`.**
  Reason: search needs freshness (entities created during a sync should
  be findable within seconds, not after the next MV refresh). How to
  apply: only read paths that need a relational projection (graph,
  donations) should hit the MVs; lookup/identity paths read the canonical
  tables.

## Blockers

_None._ Stage 3 work is unblocked by the canonical data being loaded —
module 01's full sync is currently running.

## Notes

- The new column `source` on `Person` and `Organisation` (added by
  module 01's migration `20260610_add_source_to_canonical_entities`) is
  not yet exposed in the search response. Whether it should be is a
  product question — see open TODO above.
- `apps/api/` has its own venv and `requirements.txt`; don't try to
  share the `.venv` that lives at the repo root (which is the ingest
  services' venv).
