"""
Participation extraction for InfoLobby graph.

Extracts graph edges (Participation) linking events to canonical entities
(Person, Organisation) using exact normalized name matching.

This module:
- Defines ParticipationEdge dataclass
- Extracts participation edges from typed events
- Reports matched/unmatched references for metrics
- Does NOT create new entities (read-only against canonical tables)
- Does NOT use fuzzy matching (exact normalized name only)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Union

from .events import (
    AudienceEvent,
    BaseEvent,
    DonationEvent,
    TravelEvent,
)


# Entity types for participation
EntityType = Literal["person", "organisation"]

# Participation roles
Role = Literal["PASIVO", "ACTIVO", "REPRESENTADO", "FINANCIADOR", "DONANTE"]


@dataclass
class ParticipationEdge:
    """
    Graph edge linking an event to a canonical entity.

    Represents a participation relationship: who was involved in what event,
    and in what role.
    """
    event_external_id: str
    event_type: str  # "audience", "travel", "donation"
    entity_type: EntityType
    entity_id: str  # UUID from canonical table
    role: Role
    source: str = "infolobby_sparql"


@dataclass
class EntityRef:
    """
    Lightweight entity reference for lookup dictionaries.

    Used to pass Person/Organisation data without coupling to ORM models.
    """
    id: str
    normalized_name: str


@dataclass
class ParticipationResult:
    """
    Result of participation extraction with metrics.

    Contains extracted edges and tracking of unmatched references
    for reporting and debugging.
    """
    edges: List[ParticipationEdge] = field(default_factory=list)

    # Unmatched references (normalized names that didn't resolve)
    unmatched_persons: List[str] = field(default_factory=list)
    unmatched_orgs: List[str] = field(default_factory=list)

    # Metrics by role
    edges_by_role: Dict[str, int] = field(default_factory=dict)

    # Summary counts
    total_edges: int = 0
    total_skipped: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for JSON serialization."""
        return {
            "total_edges": self.total_edges,
            "total_skipped": self.total_skipped,
            "edges_by_role": self.edges_by_role,
            "unmatched_persons_count": len(self.unmatched_persons),
            "unmatched_orgs_count": len(self.unmatched_orgs),
            "unmatched_persons_sample": self.unmatched_persons[:10],
            "unmatched_orgs_sample": self.unmatched_orgs[:10],
        }


def _extract_audience_participations(
    event: AudienceEvent,
    persons: Dict[str, EntityRef],
    organisations: Dict[str, EntityRef],
    result: ParticipationResult,
) -> None:
    """
    Extract participation edges from an AudienceEvent.

    Roles:
    - pasivo_ref → Person → PASIVO
    - activos_refs → Person → ACTIVO
    - representados_refs → Organisation → REPRESENTADO
    """
    # Pasivo (public official)
    if event.pasivo_ref:
        if event.pasivo_ref in persons:
            entity = persons[event.pasivo_ref]
            result.edges.append(ParticipationEdge(
                event_external_id=event.external_id,
                event_type=event.event_type,
                entity_type="person",
                entity_id=entity.id,
                role="PASIVO",
            ))
            result.edges_by_role["PASIVO"] = result.edges_by_role.get("PASIVO", 0) + 1
            result.total_edges += 1
        else:
            result.unmatched_persons.append(event.pasivo_ref)
            result.total_skipped += 1

    # Activos (lobbyists)
    for activo_ref in event.activos_refs:
        if activo_ref in persons:
            entity = persons[activo_ref]
            result.edges.append(ParticipationEdge(
                event_external_id=event.external_id,
                event_type=event.event_type,
                entity_type="person",
                entity_id=entity.id,
                role="ACTIVO",
            ))
            result.edges_by_role["ACTIVO"] = result.edges_by_role.get("ACTIVO", 0) + 1
            result.total_edges += 1
        else:
            result.unmatched_persons.append(activo_ref)
            result.total_skipped += 1

    # Representados (organisations represented)
    for rep_ref in event.representados_refs:
        if rep_ref in organisations:
            entity = organisations[rep_ref]
            result.edges.append(ParticipationEdge(
                event_external_id=event.external_id,
                event_type=event.event_type,
                entity_type="organisation",
                entity_id=entity.id,
                role="REPRESENTADO",
            ))
            result.edges_by_role["REPRESENTADO"] = result.edges_by_role.get("REPRESENTADO", 0) + 1
            result.total_edges += 1
        else:
            result.unmatched_orgs.append(rep_ref)
            result.total_skipped += 1


def _extract_travel_participations(
    event: TravelEvent,
    persons: Dict[str, EntityRef],
    organisations: Dict[str, EntityRef],
    result: ParticipationResult,
) -> None:
    """
    Extract participation edges from a TravelEvent.

    Roles:
    - pasivo_ref → Person → PASIVO (if present)
    - financiadores_refs → Organisation → FINANCIADOR
    """
    # Pasivo (traveler - public official)
    if event.pasivo_ref:
        if event.pasivo_ref in persons:
            entity = persons[event.pasivo_ref]
            result.edges.append(ParticipationEdge(
                event_external_id=event.external_id,
                event_type=event.event_type,
                entity_type="person",
                entity_id=entity.id,
                role="PASIVO",
            ))
            result.edges_by_role["PASIVO"] = result.edges_by_role.get("PASIVO", 0) + 1
            result.total_edges += 1
        else:
            result.unmatched_persons.append(event.pasivo_ref)
            result.total_skipped += 1

    # Financiadores (funders)
    for fin_ref in event.financiadores_refs:
        if fin_ref in organisations:
            entity = organisations[fin_ref]
            result.edges.append(ParticipationEdge(
                event_external_id=event.external_id,
                event_type=event.event_type,
                entity_type="organisation",
                entity_id=entity.id,
                role="FINANCIADOR",
            ))
            result.edges_by_role["FINANCIADOR"] = result.edges_by_role.get("FINANCIADOR", 0) + 1
            result.total_edges += 1
        else:
            result.unmatched_orgs.append(fin_ref)
            result.total_skipped += 1


def _extract_donation_participations(
    event: DonationEvent,
    persons: Dict[str, EntityRef],
    organisations: Dict[str, EntityRef],
    result: ParticipationResult,
) -> None:
    """
    Extract participation edges from a DonationEvent.

    Roles:
    - pasivo_ref → Person → PASIVO (recipient, if present)
    - donantes_refs → Organisation → DONANTE
    """
    # Pasivo (recipient - public official)
    if event.pasivo_ref:
        if event.pasivo_ref in persons:
            entity = persons[event.pasivo_ref]
            result.edges.append(ParticipationEdge(
                event_external_id=event.external_id,
                event_type=event.event_type,
                entity_type="person",
                entity_id=entity.id,
                role="PASIVO",
            ))
            result.edges_by_role["PASIVO"] = result.edges_by_role.get("PASIVO", 0) + 1
            result.total_edges += 1
        else:
            result.unmatched_persons.append(event.pasivo_ref)
            result.total_skipped += 1

    # Donantes (donors)
    for don_ref in event.donantes_refs:
        if don_ref in organisations:
            entity = organisations[don_ref]
            result.edges.append(ParticipationEdge(
                event_external_id=event.external_id,
                event_type=event.event_type,
                entity_type="organisation",
                entity_id=entity.id,
                role="DONANTE",
            ))
            result.edges_by_role["DONANTE"] = result.edges_by_role.get("DONANTE", 0) + 1
            result.total_edges += 1
        else:
            result.unmatched_orgs.append(don_ref)
            result.total_skipped += 1


def extract_participations(
    events: List[Union[AudienceEvent, TravelEvent, DonationEvent]],
    persons: Dict[str, EntityRef],
    organisations: Dict[str, EntityRef],
) -> ParticipationResult:
    """
    Extract participation edges from events.

    Matches event references against canonical entities using exact
    normalized name matching. Creates ParticipationEdge for each
    successful match. Unmatched references are tracked for reporting.

    Args:
        events: List of typed events (AudienceEvent, TravelEvent, DonationEvent)
        persons: Dict mapping normalized_name → EntityRef for persons
        organisations: Dict mapping normalized_name → EntityRef for organisations

    Returns:
        ParticipationResult with edges and metrics

    Example:
        >>> from services.info_lobby_sync.participation import (
        ...     extract_participations, EntityRef
        ... )
        >>>
        >>> # Load entities from DB (done by caller)
        >>> persons = {"juan perez": EntityRef(id="uuid-1", normalized_name="juan perez")}
        >>> orgs = {"empresa abc": EntityRef(id="uuid-2", normalized_name="empresa abc")}
        >>>
        >>> # Extract participations
        >>> result = extract_participations(events, persons, orgs)
        >>> print(f"Created {result.total_edges} edges")
        >>> print(f"Skipped {result.total_skipped} unmatched refs")
    """
    result = ParticipationResult()

    for event in events:
        if isinstance(event, AudienceEvent):
            _extract_audience_participations(event, persons, organisations, result)
        elif isinstance(event, TravelEvent):
            _extract_travel_participations(event, persons, organisations, result)
        elif isinstance(event, DonationEvent):
            _extract_donation_participations(event, persons, organisations, result)

    return result


def load_persons_dict(engine: Any, tenant_code: str = "CL") -> Dict[str, EntityRef]:
    """
    Load persons from canonical table into lookup dictionary.

    Helper function to load Person entities for participation extraction.
    The caller is responsible for providing the database engine.

    Args:
        engine: SQLAlchemy engine
        tenant_code: Tenant filter (default "CL")

    Returns:
        Dict mapping normalized_name → EntityRef
    """
    from sqlalchemy import text

    query = text("""
        SELECT id, normalized_name
        FROM "Person"
        WHERE tenant_code = :tenant_code
        AND normalized_name IS NOT NULL
    """)

    persons: Dict[str, EntityRef] = {}

    with engine.connect() as conn:
        rows = conn.execute(query, {"tenant_code": tenant_code})
        for row in rows:
            # Handle both tuple and mapping results
            if hasattr(row, '_mapping'):
                entity_id = str(row._mapping['id'])
                normalized_name = row._mapping['normalized_name']
            else:
                entity_id = str(row[0])
                normalized_name = row[1]

            if normalized_name:
                persons[normalized_name] = EntityRef(
                    id=entity_id,
                    normalized_name=normalized_name,
                )

    return persons


def load_organisations_dict(engine: Any, tenant_code: str = "CL") -> Dict[str, EntityRef]:
    """
    Load organisations from canonical table into lookup dictionary.

    Helper function to load Organisation entities for participation extraction.
    The caller is responsible for providing the database engine.

    Args:
        engine: SQLAlchemy engine
        tenant_code: Tenant filter (default "CL")

    Returns:
        Dict mapping normalized_name → EntityRef
    """
    from sqlalchemy import text

    query = text("""
        SELECT id, normalized_name
        FROM "Organisation"
        WHERE tenant_code = :tenant_code
        AND normalized_name IS NOT NULL
    """)

    orgs: Dict[str, EntityRef] = {}

    with engine.connect() as conn:
        rows = conn.execute(query, {"tenant_code": tenant_code})
        for row in rows:
            if hasattr(row, '_mapping'):
                entity_id = str(row._mapping['id'])
                normalized_name = row._mapping['normalized_name']
            else:
                entity_id = str(row[0])
                normalized_name = row[1]

            if normalized_name:
                orgs[normalized_name] = EntityRef(
                    id=entity_id,
                    normalized_name=normalized_name,
                )

    return orgs
