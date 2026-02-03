-- ============================================================================
-- Migration: Graph Materialized Views
-- Purpose: Create materialized views for graph visualization
-- Views:
--   - mv_graph_nodes: Union of Person, Organisation, Event nodes
--   - mv_graph_links: Edges between nodes (Event → Entity direction)
-- ============================================================================

-- ============================================================================
-- Materialized View: mv_graph_nodes
-- Aggregates all graph nodes (Person, Organisation, Event) for visualization.
-- Includes node_type to distinguish entity types.
-- ============================================================================

CREATE MATERIALIZED VIEW mv_graph_nodes AS
SELECT
    id AS node_id,
    'person' AS node_type,
    "tenantCode" AS tenant_code,
    "normalizedName" AS label
FROM "Person"

UNION ALL

SELECT
    id AS node_id,
    'organisation' AS node_type,
    "tenantCode" AS tenant_code,
    "normalizedName" AS label
FROM "Organisation"

UNION ALL

SELECT
    id AS node_id,
    'event' AS node_type,
    "tenantCode" AS tenant_code,
    "externalId" AS label
FROM "Event";

-- Unique index required for REFRESH MATERIALIZED VIEW CONCURRENTLY
CREATE UNIQUE INDEX mv_graph_nodes_node_id_idx ON mv_graph_nodes(node_id);

-- Index for tenant filtering (common query pattern)
CREATE INDEX mv_graph_nodes_tenant_code_idx ON mv_graph_nodes(tenant_code);

-- Index for type filtering
CREATE INDEX mv_graph_nodes_node_type_idx ON mv_graph_nodes(node_type);

-- ============================================================================
-- Materialized View: mv_graph_links
-- Edges from Event to Person/Organisation.
-- Direction: Event (source) → Entity (target)
-- Filters out edges with no destination (both toPersonId and toOrgId are null).
-- ============================================================================

CREATE MATERIALIZED VIEW mv_graph_links AS
SELECT
    e.id AS link_id,
    e."eventId" AS source_node_id,
    COALESCE(e."toPersonId", e."toOrgId") AS target_node_id,
    e."tenantCode" AS tenant_code,
    e.label AS label
FROM "Edge" e
WHERE e."toPersonId" IS NOT NULL OR e."toOrgId" IS NOT NULL;

-- Unique index required for REFRESH MATERIALIZED VIEW CONCURRENTLY
CREATE UNIQUE INDEX mv_graph_links_link_id_idx ON mv_graph_links(link_id);

-- Index for tenant filtering
CREATE INDEX mv_graph_links_tenant_code_idx ON mv_graph_links(tenant_code);

-- Index for source node lookups
CREATE INDEX mv_graph_links_source_node_id_idx ON mv_graph_links(source_node_id);

-- Index for target node lookups
CREATE INDEX mv_graph_links_target_node_id_idx ON mv_graph_links(target_node_id);

-- Index for label filtering (e.g., DONANTE, DONATARIO)
CREATE INDEX mv_graph_links_label_idx ON mv_graph_links(label);
