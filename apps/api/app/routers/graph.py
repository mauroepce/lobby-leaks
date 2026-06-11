"""GET /api/v1/graph — subgraph projection centered on an entity or event."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..db import load_graph_subgraph
from ..middleware import resolve_tenant
from ..schemas import GraphResponse

router = APIRouter(prefix="/api/v1")

MAX_LIMIT_EVENTS = 200


@router.get("/graph", response_model=GraphResponse)
async def graph(
    request: Request,
    center: str = Query(..., min_length=1, description="Node id (Person, Organisation, or Event) to center the subgraph on"),
    depth: int = Query(2, ge=1, le=2, description="1 = direct events only; 2 = + entities co-occurring in those events"),
    limit_events: int = Query(
        50,
        ge=1,
        le=MAX_LIMIT_EVENTS,
        description=f"Max direct events to include (capped at {MAX_LIMIT_EVENTS} for response size)",
    ),
    tenant: str = Depends(resolve_tenant),
) -> GraphResponse:
    """Return a subgraph projection around the given center node.

    The graph is event-centric (Entity → Event → Entity), so every link in
    the response goes from an Event id to an Entity id. To traverse between
    two entities you always pass through one intermediate Event node.
    """
    pool = request.app.state.pool
    nodes, links, truncated, center_type = await load_graph_subgraph(
        pool, tenant=tenant, center=center, depth=depth, limit_events=limit_events
    )
    if center_type is None:
        raise HTTPException(
            status_code=404,
            detail=f"Center node {center!r} not found for tenant {tenant!r}",
        )
    return GraphResponse(
        center=center,
        depth=depth,
        truncated=truncated,
        nodes=nodes,
        links=links,
    )
