from __future__ import annotations

from psycopg_pool import AsyncConnectionPool

from .schemas import EntityResult, GraphLink, GraphNode

SEARCH_SQL = """
SELECT id, 'person' AS type, "normalizedName" AS label, rut
FROM "Person"
WHERE "tenantCode" = %(tenant)s
  AND ("normalizedName" ILIKE %(pattern)s OR "rut" ILIKE %(pattern)s)

UNION ALL

SELECT id, 'organisation' AS type, "normalizedName" AS label, rut
FROM "Organisation"
WHERE "tenantCode" = %(tenant)s
  AND ("normalizedName" ILIKE %(pattern)s OR "rut" ILIKE %(pattern)s)

ORDER BY label
LIMIT %(limit)s
"""

COUNT_SQL = """
SELECT
  (SELECT count(*) FROM "Person"
   WHERE "tenantCode" = %(tenant)s
     AND ("normalizedName" ILIKE %(pattern)s OR "rut" ILIKE %(pattern)s))
  +
  (SELECT count(*) FROM "Organisation"
   WHERE "tenantCode" = %(tenant)s
     AND ("normalizedName" ILIKE %(pattern)s OR "rut" ILIKE %(pattern)s))
AS total
"""


async def search_entities(
    pool: AsyncConnectionPool,
    tenant: str,
    query: str,
    limit: int = 20,
) -> tuple[list[EntityResult], int]:
    """Search Person and Organisation tables by normalizedName or rut."""
    pattern = f"%{query}%"
    params = {"tenant": tenant, "pattern": pattern, "limit": limit}

    async with pool.connection() as conn:
        # Fetch matching rows
        cursor = await conn.execute(SEARCH_SQL, params)
        rows = await cursor.fetchall()
        results = [
            EntityResult(id=r[0], type=r[1], label=r[2], rut=r[3])
            for r in rows
        ]

        # Fetch total count
        cursor = await conn.execute(COUNT_SQL, params)
        row = await cursor.fetchone()
        total = row[0] if row else 0

    return results, total


# ── /graph queries ────────────────────────────────────────────────────────
#
# Reads `mv_graph_nodes` and `mv_graph_links` rather than the canonical
# tables because the graph projection is what the frontend needs, and the
# MVs already collapse the event-centric pattern into a single source-target
# shape. Refresh cadence for the MVs is managed in services/graph_refresh.

# Depth-2 query: one round-trip, returns both nodes and links tagged in a
# `row_kind` column. The CTEs build the link sets first (cheap, all index
# lookups) and the final SELECT joins back to mv_graph_nodes for labels.
SUBGRAPH_SQL_D2 = """
WITH
direct AS (
    SELECT link_id,
           source_node_id AS event_id,
           target_node_id,
           label
    FROM mv_graph_links
    WHERE tenant_code = %(tenant)s
      AND target_node_id = %(center)s
    LIMIT %(limit_events)s
),
related AS (
    SELECT l.link_id,
           l.source_node_id AS event_id,
           l.target_node_id,
           l.label
    FROM mv_graph_links l
    WHERE l.tenant_code = %(tenant)s
      AND l.source_node_id IN (SELECT event_id FROM direct)
      AND l.target_node_id <> %(center)s
),
all_links AS (
    SELECT link_id, event_id, target_node_id, label FROM direct
    UNION ALL
    SELECT link_id, event_id, target_node_id, label FROM related
),
all_node_ids AS (
    SELECT %(center)s::text AS node_id
    UNION
    SELECT event_id FROM all_links
    UNION
    SELECT target_node_id FROM all_links
)
SELECT 'node'::text AS row_kind,
       n.node_id::text AS a,
       n.node_type::text AS b,
       n.label::text AS c,
       NULL::text AS d
FROM mv_graph_nodes n
JOIN all_node_ids ids USING (node_id)
WHERE n.tenant_code = %(tenant)s

UNION ALL

SELECT 'link'::text AS row_kind,
       al.link_id::text AS a,
       al.event_id::text AS b,
       al.target_node_id::text AS c,
       al.label::text AS d
FROM all_links al
"""

# Depth-1 variant: skip the "related" CTE — only events directly touching
# the center node are returned, no co-participants. Cheaper, smaller payload.
SUBGRAPH_SQL_D1 = """
WITH
direct AS (
    SELECT link_id,
           source_node_id AS event_id,
           target_node_id,
           label
    FROM mv_graph_links
    WHERE tenant_code = %(tenant)s
      AND target_node_id = %(center)s
    LIMIT %(limit_events)s
),
all_node_ids AS (
    SELECT %(center)s::text AS node_id
    UNION
    SELECT event_id FROM direct
)
SELECT 'node'::text AS row_kind,
       n.node_id::text AS a,
       n.node_type::text AS b,
       n.label::text AS c,
       NULL::text AS d
FROM mv_graph_nodes n
JOIN all_node_ids ids USING (node_id)
WHERE n.tenant_code = %(tenant)s

UNION ALL

SELECT 'link'::text AS row_kind,
       d.link_id::text AS a,
       d.event_id::text AS b,
       d.target_node_id::text AS c,
       d.label::text AS d
FROM direct d
"""

# Counts how many events touch the center node at depth 1, ignoring
# limit_events. Used to decide whether to set `truncated=true` in the
# response when direct events were capped.
COUNT_DIRECT_EVENTS_SQL = """
SELECT count(*)
FROM mv_graph_links
WHERE tenant_code = %(tenant)s
  AND target_node_id = %(center)s
"""

# Validates the center node belongs to this tenant — also returns its
# node_type for the 404/400 distinction in the router. NULL = not found.
CENTER_TYPE_SQL = """
SELECT node_type::text
FROM mv_graph_nodes
WHERE tenant_code = %(tenant)s
  AND node_id = %(center)s
LIMIT 1
"""


async def load_graph_subgraph(
    pool: AsyncConnectionPool,
    tenant: str,
    center: str,
    depth: int = 2,
    limit_events: int = 50,
) -> tuple[list[GraphNode], list[GraphLink], bool, str | None]:
    """Load a subgraph centered on a given entity or event.

    Returns:
        (nodes, links, truncated, center_type)
        center_type is None when the center node doesn't exist for this
        tenant; callers turn that into a 404. truncated is True iff the
        center has more direct events than `limit_events`.
    """
    sql = SUBGRAPH_SQL_D2 if depth == 2 else SUBGRAPH_SQL_D1
    params = {"tenant": tenant, "center": center, "limit_events": limit_events}

    async with pool.connection() as conn:
        # First — does the center exist in this tenant? Cheap by-id lookup.
        cursor = await conn.execute(CENTER_TYPE_SQL, params)
        row = await cursor.fetchone()
        if not row:
            return [], [], False, None
        center_type = row[0]

        # Pull the subgraph (nodes + links in one tagged result set).
        cursor = await conn.execute(sql, params)
        rows = await cursor.fetchall()

        nodes: list[GraphNode] = []
        links: list[GraphLink] = []
        for row_kind, a, b, c, d in rows:
            if row_kind == "node":
                nodes.append(GraphNode(id=a, type=b, label=c))
            else:
                links.append(GraphLink(source=b, target=c, label=d))

        # Truncation check: a separate count avoids paying for it on every
        # request body — only fire it when we returned exactly limit_events
        # direct events (the cap was hit, so there MIGHT be more).
        truncated = False
        direct_events = {l.source for l in links}
        if len(direct_events) >= limit_events:
            cursor = await conn.execute(
                COUNT_DIRECT_EVENTS_SQL,
                {"tenant": tenant, "center": center},
            )
            count_row = await cursor.fetchone()
            total_direct = count_row[0] if count_row else 0
            truncated = total_direct > limit_events

    return nodes, links, truncated, center_type
