# Graph Materialized Views

This document describes the materialized views and analysis views used for graph visualization.

## Overview

The graph visualization system uses two layers:
1. **Materialized Views (MVs)**: Pre-computed tables for fast graph queries
2. **Analysis Views**: Business intelligence views built on top of the graph data

## Materialized Views

### `mv_graph_nodes`

Aggregates all graph nodes (Person, Organisation, Event) into a single queryable structure.

| Column | Type | Description |
|--------|------|-------------|
| `node_id` | TEXT | Unique node identifier (UUID) |
| `node_type` | TEXT | Entity type: 'person', 'organisation', 'event' |
| `tenant_code` | TEXT | Tenant code for data isolation |
| `label` | TEXT | Display label (normalizedName or externalId) |

**Source tables:**
- `Person` (node_type='person', label=normalizedName)
- `Organisation` (node_type='organisation', label=normalizedName)
- `Event` (node_type='event', label=externalId)

**Indexes:**
- `mv_graph_nodes_node_id_idx` (UNIQUE) - Required for REFRESH CONCURRENTLY
- `mv_graph_nodes_tenant_code_idx` - Tenant filtering
- `mv_graph_nodes_node_type_idx` - Type filtering

### `mv_graph_links`

Contains edges between events and entities (persons/organisations).

| Column | Type | Description |
|--------|------|-------------|
| `link_id` | TEXT | Unique link identifier (Edge.id) |
| `source_node_id` | TEXT | Source node (always Event.id) |
| `target_node_id` | TEXT | Target node (Person.id or Organisation.id) |
| `tenant_code` | TEXT | Tenant code for data isolation |
| `label` | TEXT | Edge label (DONANTE, DONATARIO, PASIVO, ACTIVO, etc.) |

**Direction:** Event → Entity (never reversed)

**Indexes:**
- `mv_graph_links_link_id_idx` (UNIQUE) - Required for REFRESH CONCURRENTLY
- `mv_graph_links_tenant_code_idx` - Tenant filtering
- `mv_graph_links_source_node_id_idx` - Source lookups
- `mv_graph_links_target_node_id_idx` - Target lookups
- `mv_graph_links_label_idx` - Label filtering

## Analysis Views

### `v_donations_graph`

Flattened view of donation events with donor and candidate information.

| Column | Type | Description |
|--------|------|-------------|
| `event_id` | TEXT | Donation event ID |
| `tenant_code` | TEXT | Tenant code |
| `external_id` | TEXT | SERVEL external ID (format: `SERVEL:{checksum}`) |
| `donation_date` | DATE | Date of donation |
| `amount` | BIGINT | Donation amount in CLP |
| `campaign_year` | INT | Election campaign year |
| `donor_name` | TEXT | Donor name (from metadata) |
| `donor_id` | TEXT | Matched donor entity ID (nullable) |
| `donor_type` | TEXT | 'person' or 'organisation' |
| `donor_matched_by` | TEXT | Matching method: 'RUT', 'NAME', 'NONE' |
| `candidate_name` | TEXT | Candidate name (from metadata) |
| `candidate_id` | TEXT | Matched candidate person ID |
| `candidate_matched_by` | TEXT | Matching method: 'RUT', 'NAME', 'NONE' |
| `election_type` | TEXT | Type of election |
| `candidate_party` | TEXT | Political party |
| `created_at` | TIMESTAMP | Record creation time |

**Filter:** Only events where `kind = 'donation'`

### `v_top_donors_by_candidate`

Aggregates donations by candidate and donor pairs.

| Column | Type | Description |
|--------|------|-------------|
| `tenant_code` | TEXT | Tenant code |
| `candidate_id` | TEXT | Candidate person ID |
| `candidate_name` | TEXT | Candidate name |
| `donor_id` | TEXT | Donor entity ID |
| `donor_name` | TEXT | Donor name |
| `donor_type` | TEXT | 'person' or 'organisation' |
| `total_amount` | BIGINT | Sum of donation amounts |
| `donation_count` | BIGINT | Number of donations |

**Order:** Descending by `total_amount`

## Refreshing Views

### Programmatic Refresh

```python
from services.graph_refresh import refresh_graph_views
from sqlalchemy import create_engine

engine = create_engine(database_url)
result = refresh_graph_views(engine, concurrent=True)

print(f"Nodes: {result.nodes_count}")
print(f"Links: {result.links_count}")
print(f"Duration: {result.duration_seconds:.2f}s")
```

### CLI Refresh

```bash
# Standard refresh (exclusive lock)
make refresh-graph

# Concurrent refresh (allows reads during refresh)
make refresh-graph-concurrent

# With custom database URL
DATABASE_URL=postgresql://... python -m services.graph_refresh.refresh_graph --concurrent
```

### RefreshResult

The refresh operation returns detailed metrics:

```python
@dataclass
class RefreshResult:
    nodes_count: int       # Total nodes in mv_graph_nodes
    links_count: int       # Total links in mv_graph_links
    duration_seconds: float
    concurrent_refresh: bool
    refreshed_at: datetime
    errors: list[str]
    nodes_by_type: dict[str, int]    # Breakdown by type
    links_by_label: dict[str, int]   # Breakdown by label
```

## Query Examples

### Get graph for tenant

```sql
-- Get all nodes for tenant
SELECT node_id, node_type, label
FROM mv_graph_nodes
WHERE tenant_code = 'CL';

-- Get all links for tenant
SELECT link_id, source_node_id, target_node_id, label
FROM mv_graph_links
WHERE tenant_code = 'CL';
```

### Get donations to a candidate

```sql
SELECT
    donor_name,
    donor_type,
    amount,
    campaign_year
FROM v_donations_graph
WHERE candidate_id = :candidate_id
  AND tenant_code = 'CL'
ORDER BY amount DESC;
```

### Get top donors by candidate

```sql
SELECT
    candidate_name,
    donor_name,
    donor_type,
    total_amount,
    donation_count
FROM v_top_donors_by_candidate
WHERE tenant_code = 'CL'
ORDER BY total_amount DESC
LIMIT 20;
```

## Deployment

### Apply Migrations

```bash
# Apply all pending migrations
make migrate

# Or explicitly
npx prisma@6.12.0 migrate deploy --schema=prisma/schema.prisma
```

### Initial Data Load

After migrations, refresh the MVs to populate them:

```bash
make refresh-graph
```

## Testing

```bash
# Run all graph_refresh tests (unit tests only)
make graph-refresh-test

# Run integration tests (requires DATABASE_URL)
make graph-refresh-test-integration
```

### Test Files

| File | Description |
|------|-------------|
| `test_mv_exists.py` | Verifies materialized views exist with correct structure |
| `test_views_exist.py` | Verifies analysis views exist with correct columns |
| `test_donations_view_semantics.py` | Tests data semantics in v_donations_graph |
| `test_refresh_graph.py` | Tests refresh_graph module (unit + integration) |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Base Tables                              │
├─────────────────┬─────────────────┬─────────────────────────────┤
│     Person      │   Organisation  │    Event    │     Edge      │
└────────┬────────┴────────┬────────┴──────┬──────┴───────┬───────┘
         │                 │               │              │
         └────────┬────────┴───────────────┼──────────────┘
                  │                        │
                  ▼                        ▼
         ┌────────────────┐      ┌────────────────┐
         │ mv_graph_nodes │      │ mv_graph_links │
         └────────┬───────┘      └────────┬───────┘
                  │                       │
                  └───────────┬───────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │    v_donations_graph    │
                 └────────────┬────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │ v_top_donors_by_candidate│
                 └─────────────────────────┘
```

## Performance Notes

1. **REFRESH CONCURRENTLY**: Use `--concurrent` flag to allow reads during refresh. Requires unique index on all rows.

2. **Tenant Filtering**: Always filter by `tenant_code` first to leverage indexes.

3. **Label Filtering**: For specific edge types (DONANTE, DONATARIO), add label filter to queries.

4. **Refresh Frequency**: Schedule refreshes based on data ingestion frequency (e.g., after SERVEL sync).
