# LobbyLeaks — Master Project Context & Engineering Roadmap

> Imported from a project context PDF on 2026-05-14.
>
> ⚠️ **The CODE in this repository is the source of truth, not this document.**
> This file captures direction and intent (vision, invariants, target roadmap)
> but may be inconsistent with what is actually implemented. Treat
> "completed" / "uses X" / "lives at Y" statements as hypotheses to verify
> against the code, migrations, tests, and `STATUS.md` files before acting.
>
> Living progress is tracked per-module in `STATUS.md` files and at the root
> in `INDEX.md`.

## Overview

LobbyLeaks is an open-source investigative transparency platform designed to
expose networks of political influence by connecting multiple public datasets
into a unified graph model.

Focus areas:
- Political donations
- Lobby meetings
- Public contracts
- Company ownership
- Government entities
- Politicians and public officials

Starts with Chile (`tenantCode = "CL"`) — multi-tenant by design.

## Core Vision

Reveal patterns such as:
- Companies donating to political campaigns
- Companies receiving public contracts after political relationships
- Lobby meetings between private actors and public officials
- Hidden ownership structures behind donor companies
- Repeated influence patterns between organizations and politicians

The system is **not** intended to accuse automatically. Purpose:
investigative transparency, public accountability, relationship discovery,
evidence aggregation.

## Architectural Philosophy

### Event-Centric Graph (invariant)

All relationships are anchored through Event nodes. **Never** entity → entity.

```
Company → DONANTE → DonationEvent → DONATARIO → Politician
Lobbyist → PARTICIPATED_IN → LobbyMeetingEvent
Company → SUPPLIES → ContractEvent → GovernmentEntity
```

### Canonical Data Model

- **Person** — politicians, lobbyists, donors, representatives, officials
- **Organisation** — companies, NGOs, parties, gov institutions
- **Event** — donation, lobby meeting, contract, travel, gift
- **Edge** — `eventId` + `from{Person|Org}Id` + `to{Person|Org}Id` + `label` + `metadata`

Common edge labels: `DONANTE`, `DONATARIO`, `PARTICIPATED_IN`, `REPRESENTS`,
`SUPPLIES`, `OWNS`, `FINANCIADOR`.

### Multi-Tenant

Every query MUST filter `WHERE tenantCode = :tenant`. Cross-tenant leakage is
forbidden.

## Graph Projection Layer

Materialized views: `mv_graph_nodes`, `mv_graph_links`.
- `mv_graph_links.source_node_id = Event.id`
- `mv_graph_links.target_node_id = Entity.id`

Analysis views: `v_donations_graph`, `v_top_donors_by_candidate`.

## Stack

**Backend**: Python 3.12, FastAPI, SQLAlchemy, psycopg3, PostgreSQL, Prisma
schema, Materialized Views.
**Frontend (planned)**: Next.js, Cosmograph.
**Infra**: Docker, GitHub Actions, Makefile; Supabase / Fly.io / Vercel possible.

## Project Structure

```
services/
  _template/
  info_lobby_sync/
  servel_sync/
  graph_refresh/
  lobby_collector/
  mcp-hub/
apps/
  api/        # planned (currently empty `backend/`)
  frontend/   # planned (currently empty)
prisma/
  schema.prisma
docs/
```

## Engineering Principles

- Deterministic pipelines (repeated runs → same result).
- Idempotent persistence (externalId, checksums, ON CONFLICT, UPSERT).
- Read-optimized graph API uses `mv_graph_nodes` / `mv_graph_links`.
- Async-first backend.
- Test-driven (every major story ships with tests).

## Sources Investigated

### SERVEL (campaign donations) — implemented
CSV/Excel parsing, deterministic merge, event + donation graph persistence.
Tolerant alias mapping for variable column names. Deterministic IDs via
checksums.

### InfoLobby — implemented (major shift)
Exposes RDF ontology + SPARQL endpoint.

- Endpoint: `http://datos.infolobby.cl/sparql`
- Main graph: `http://datos.infolobby.cl/infolobby`

Project now uses SPARQL/RDF/ontology-driven extraction (not HTML scraping).

Ontology key classes: `RegistroAudiencia`, `Donativo`, `Viaje`, `Persona`,
`Entidad`, `Pasivo`, `Activo`.
Relationships: `participa`, `financia`, `donadoPor`, `otorgadoA`,
`trabajoPara`, `representadoPor`.

## APIs Used

**Working well**:
- InfoLobby SPARQL — highly valuable, semantic graph, official linked data.
- SERVEL datasets — direct political financing data.

**Problematic**:
- Ley del Lobby API — frequent 401s, unstable. Now **best-effort fallback only**.

### Important Architectural Shift

- **Was**: Ley del Lobby API = primary source.
- **Now**: InfoLobby SPARQL = primary; Ley del Lobby = optional fallback.

## External Open-Source References

- **ChileCompra**: `open-contracting/kingfisher-collect` (OCDS standard).
- **SERVEL**: `serveliza`, `servel_scraper` (reference only; custom ingestion preferred).
- **SII**: Rich ecosystem — can identify company ownership, representatives,
  hidden financing.

## Epics Completed

| Epic | Scope |
|------|-------|
| **E1.0** | Ingestion framework (HTTPX, retries, pydantic settings, structlog, PG, UPSERT, Docker, CI, Makefile) |
| **E1.2** | InfoLobby Sync (SPARQL fetch, RDF parse, merge, persistence, 122+ tests) |
| **E1.3** | Event extraction (typed Event + Participation + edge persistence) |
| **E1.4** | SERVEL donations (CSV/Excel parsing, merge, orchestrator, graph persistence) |
| **E2.0-S3** | Graph views (materialized views, donation views, refresh service, CLI, indexes, tests) |

## Current Status

Ingestion ✅ · canonical persistence ✅ · graph persistence ✅ · graph projections ✅ · donation graph ✅ · SPARQL integration ✅.

**Next stage: Public API + Frontend.**

## Roadmap

### Stage 3 — Public Graph API

- **E3.0-S1** — Search endpoint (Person/Organisation by name, RUT).
- **E3.0-S2** — Graph endpoint (`{nodes, links}`) consuming `mv_graph_nodes` / `mv_graph_links`.
- **E3.0-S3** — Security + OpenAPI (tenant isolation, middleware, logging, rate limiting, tests).

### Stage 4 — Frontend

Global search · Cosmograph visualization · side panels · donation tables · relationship navigation.

### Future high-priority epics

- **E1.6** — Firmography / ownership: `Organisation → OWNS/REPRESENTS → Person` (sources: SII, Diario Oficial).
- **E1.7** — ChileCompra: `Organisation → SUPPLIES → ContractEvent` (enables "donates → wins contracts").

### Long-term investigative goals

- Donor companies linked to politicians
- Repeated lobbying before procurement
- Circular influence structures
- Ownership hiding political financing
- Timing correlations donations ↔ contracts

## Design Rules (invariants)

1. **NEVER** create direct entity-to-entity edges. Always Entity → Event → Entity.
2. **ALWAYS** enforce tenant isolation: `WHERE tenantCode = :tenant`.
3. **NEVER** bypass idempotency. Repeated runs must be safe.
4. **NEVER** invert graph direction. `source_node_id = Event.id`.
5. **USE** materialized views for graph exploration, not raw canonical tables.

## API Decisions

- Public API lives at `apps/api/` (separate FastAPI app, not the MCP hub).
- Tenant input: `tenant` query param OR `X-Tenant-Id` header. Query param wins;
  mismatch returns 400.
- Python 3.12.

## Known Risks

- **Data quality**: missing RUTs, stable IDs, consistent names. Current
  approach: deterministic normalization + exact matching + collision-safe
  merges. Future: embeddings / fuzzy matching / entity resolution.
- **Political data gaps**: not all corruption is recorded. Focus on evidence
  aggregation and pattern discovery, not automatic accusations.

## Suggested Future Features

- **User uploads**: PDFs, contracts, leaked documents → `Document → DOCUMENTS → Event`.
- **OCR pipelines**: PaddleOCR / Textract / DocAI.
- **MCP tools**: `summarise-entity`, `fetch-pdf`, `ocr-pdf`, `entity-link`.

## Current Priority Order

1. Stage 3 — Public Graph API
2. Frontend + Cosmograph
3. ChileCompra + ownership triangulation

## Philosophy

LobbyLeaks aims to be: an investigative platform · a graph of political
influence · a public transparency tool · a research infrastructure.

The goal is not sensationalism — it is **making influence networks visible
through structured, explainable, reproducible data.**
