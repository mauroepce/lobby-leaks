"""
Persistence layer for participation edges.

Persists ParticipationEdge objects into the Edge table, linking events
to persons/organisations in the graph.

This module:
- Resolves event_external_id to Event.id
- Creates Edge records with Event → Entity direction
- Uses UPSERT for idempotency
- Stores source in metadata JSON
- Does NOT create new entities or events
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import json
import uuid

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .participation import ParticipationEdge


@dataclass
class ParticipationPersistResult:
    """Result of participation persistence operation with metrics."""
    inserted_edges: int = 0
    skipped_missing_event: int = 0
    skipped_duplicates: int = 0
    edges_by_role: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    @property
    def duration_seconds(self) -> float:
        """Calculate duration in seconds."""
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return 0.0

    @property
    def total_processed(self) -> int:
        """Total edges processed (inserted + skipped)."""
        return self.inserted_edges + self.skipped_missing_event + self.skipped_duplicates

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "inserted_edges": self.inserted_edges,
            "skipped_missing_event": self.skipped_missing_event,
            "skipped_duplicates": self.skipped_duplicates,
            "edges_by_role": self.edges_by_role,
            "total_processed": self.total_processed,
            "errors": self.errors,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_seconds": self.duration_seconds,
        }


def _load_events_dict(
    conn,
    tenant_code: str,
) -> Dict[str, str]:
    """
    Load events from DB into lookup dictionary.

    Returns dict mapping (externalId, kind) tuple key to event id.
    Key format: "{externalId}:{kind}"
    """
    query = text("""
        SELECT id, "externalId", kind
        FROM "Event"
        WHERE "tenantCode" = :tenant_code
    """)

    events: Dict[str, str] = {}
    result = conn.execute(query, {"tenant_code": tenant_code})

    for row in result:
        if hasattr(row, '_mapping'):
            event_id = row._mapping['id']
            external_id = row._mapping['externalId']
            kind = row._mapping['kind']
        else:
            event_id = row[0]
            external_id = row[1]
            kind = row[2]

        # Key is "externalId:kind" for unique lookup
        key = f"{external_id}:{kind}"
        events[key] = event_id

    return events


def _map_event_type_to_kind(event_type: str) -> str:
    """
    Map ParticipationEdge.event_type to Event.kind.

    event_type uses our internal naming, kind uses DB naming.
    """
    # Currently they match, but this provides a clear mapping point
    mapping = {
        "audience": "audience",
        "travel": "travel",
        "donation": "donation",
    }
    return mapping.get(event_type, event_type)


def persist_participations(
    edges: List[ParticipationEdge],
    engine: Engine,
    tenant_code: str = "CL",
) -> ParticipationPersistResult:
    """
    Persist participation edges to the Edge table.

    Each ParticipationEdge is persisted as an Edge record linking
    an Event to a Person or Organisation.

    Convention:
    - eventId = always set (required)
    - fromPersonId = NULL (never used for participations)
    - fromOrgId = NULL (never used for participations)
    - toPersonId = set if entity_type == "person"
    - toOrgId = set if entity_type == "organisation"
    - label = role (PASIVO, ACTIVO, etc.)
    - metadata = {"source": "infolobby_sparql"}

    Args:
        edges: List of ParticipationEdge from extract_participations()
        engine: SQLAlchemy database engine
        tenant_code: Tenant code for filtering (default "CL")

    Returns:
        ParticipationPersistResult with operation counts

    Example:
        >>> from services.info_lobby_sync.participation_persistence import (
        ...     persist_participations
        ... )
        >>> result = persist_participations(edges, engine)
        >>> print(f"Inserted: {result.inserted_edges}")
        >>> print(f"Skipped (no event): {result.skipped_missing_event}")
    """
    result = ParticipationPersistResult(started_at=datetime.utcnow())

    if not edges:
        result.finished_at = datetime.utcnow()
        return result

    try:
        with engine.begin() as conn:
            # Load events lookup
            events_lookup = _load_events_dict(conn, tenant_code)

            for edge in edges:
                try:
                    outcome = _persist_edge(conn, edge, events_lookup, tenant_code)

                    if outcome == "inserted":
                        result.inserted_edges += 1
                        # Track by role
                        role = edge.role
                        result.edges_by_role[role] = result.edges_by_role.get(role, 0) + 1
                    elif outcome == "missing_event":
                        result.skipped_missing_event += 1
                    elif outcome == "duplicate":
                        result.skipped_duplicates += 1

                except Exception as e:
                    result.errors.append(
                        f"Edge {edge.event_external_id}->{edge.entity_id}: {str(e)}"
                    )

    except Exception as e:
        result.errors.append(f"Database error: {str(e)}")

    result.finished_at = datetime.utcnow()
    return result


def _persist_edge(
    conn,
    edge: ParticipationEdge,
    events_lookup: Dict[str, str],
    tenant_code: str,
) -> str:
    """
    Persist a single participation edge.

    Returns: "inserted", "missing_event", or "duplicate"
    """
    # Resolve event_id from external_id + kind
    kind = _map_event_type_to_kind(edge.event_type)
    event_key = f"{edge.event_external_id}:{kind}"
    event_id = events_lookup.get(event_key)

    if not event_id:
        return "missing_event"

    # Validate XOR: exactly one of person/org
    if edge.entity_type == "person":
        to_person_id = edge.entity_id
        to_org_id = None
    elif edge.entity_type == "organisation":
        to_person_id = None
        to_org_id = edge.entity_id
    else:
        raise ValueError(f"Invalid entity_type: {edge.entity_type}")

    # Prepare metadata with source
    metadata = json.dumps({"source": edge.source})

    now = datetime.utcnow()
    new_id = str(uuid.uuid4())

    # UPSERT with ON CONFLICT DO NOTHING
    # The unique constraint is on (eventId, fromPersonId, fromOrgId, toPersonId, toOrgId, label)
    insert_query = text("""
        INSERT INTO "Edge" (
            id, "tenantCode", "eventId",
            "fromPersonId", "fromOrgId",
            "toPersonId", "toOrgId",
            label, metadata,
            "createdAt", "updatedAt"
        )
        VALUES (
            :id, :tenant_code, :event_id,
            NULL, NULL,
            :to_person_id, :to_org_id,
            :label, :metadata::jsonb,
            :created_at, :updated_at
        )
        ON CONFLICT ("eventId", "fromPersonId", "fromOrgId", "toPersonId", "toOrgId", "label")
        DO NOTHING
        RETURNING id
    """)

    result = conn.execute(insert_query, {
        "id": new_id,
        "tenant_code": tenant_code,
        "event_id": event_id,
        "to_person_id": to_person_id,
        "to_org_id": to_org_id,
        "label": edge.role,
        "metadata": metadata,
        "created_at": now,
        "updated_at": now,
    })

    row = result.fetchone()
    return "inserted" if row else "duplicate"


def load_events_for_persistence(
    engine: Engine,
    tenant_code: str = "CL",
) -> Dict[str, str]:
    """
    Load events from DB for external use.

    Returns dict mapping "{externalId}:{kind}" to event id.
    Useful for checking which events exist before calling persist_participations.

    Args:
        engine: SQLAlchemy database engine
        tenant_code: Tenant code for filtering

    Returns:
        Dict mapping event key to event id
    """
    with engine.connect() as conn:
        return _load_events_dict(conn, tenant_code)
