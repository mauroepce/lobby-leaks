from __future__ import annotations

from pydantic import BaseModel, Field


class EntityResult(BaseModel):
    id: str
    type: str  # "person" | "organisation"
    label: str
    rut: str | None


class SearchResponse(BaseModel):
    results: list[EntityResult]
    total: int


class GraphNode(BaseModel):
    """A node in the graph projection — person, organisation, or event."""

    id: str
    type: str  # "person" | "organisation" | "event"
    label: str


class GraphLink(BaseModel):
    """A link in the graph projection: source is always an event id, target
    is the entity that participates with the given role label."""

    source: str
    target: str
    label: str  # PASIVO | ACTIVO | REPRESENTADO | FINANCIADOR | DONANTE


class GraphResponse(BaseModel):
    """Subgraph centered on a person/organisation/event id.

    The graph is event-centric: every link goes Event → Entity (Person or
    Organisation). To traverse Entity-A → Entity-B you always pass through
    one intermediate Event node.
    """

    center: str
    depth: int = Field(..., description="1 = events touching center; 2 = + other entities in those events")
    truncated: bool = Field(
        ...,
        description="True if events touching the center exceeded limit_events and were capped",
    )
    nodes: list[GraphNode]
    links: list[GraphLink]
