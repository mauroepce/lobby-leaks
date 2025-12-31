"""
Event extraction for InfoLobby data.

Transforms parsed records into typed event objects for graph persistence.
Events are facts with normalized entity references for later linking.

This module:
- Defines BaseEvent and typed event subclasses
- Extracts events from parsed SPARQL records
- Normalizes entity references for deterministic linking in S2
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Literal, Optional, Union

from services.info_lobby_sync.merge import normalize_for_matching
from services.info_lobby_sync.parser import (
    ParsedAudiencia,
    ParsedDonativo,
    ParsedViaje,
)


EventType = Literal["audience", "travel", "donation"]


@dataclass
class BaseEvent:
    """
    Base class for all event types.

    Events are facts extracted from source data. They contain:
    - Identity: external_id from source system
    - Timing: date_start, optional date_end
    - Provenance: source identifier
    - References: normalized names for linking to entities

    Events do NOT contain:
    - Foreign keys to internal entities
    - Matching/resolution logic
    """
    external_id: str
    event_type: EventType
    date_start: Optional[date]
    date_end: Optional[date] = None
    source: str = "infolobby_sparql"

    # Entity references as normalized names (for linking in S2)
    pasivo_ref: Optional[str] = None
    activos_refs: List[str] = field(default_factory=list)
    representados_refs: List[str] = field(default_factory=list)


@dataclass
class AudienceEvent(BaseEvent):
    """
    Audience (meeting) event.

    Represents a registered meeting between a public official (pasivo)
    and lobbyists or representatives (activos).
    """
    event_type: EventType = field(default="audience", init=False)

    # Specific fields
    lugar: Optional[str] = None
    forma: Optional[str] = None  # presencial, virtual, etc.
    materias: List[str] = field(default_factory=list)
    descripcion: Optional[str] = None
    observaciones: Optional[str] = None


@dataclass
class TravelEvent(BaseEvent):
    """
    Travel event.

    Represents a trip taken by a public official, potentially
    funded by external parties.
    """
    event_type: EventType = field(default="travel", init=False)

    # Specific fields
    destino: Optional[str] = None
    motivo: Optional[str] = None
    costo_total: Optional[int] = None
    financiadores_refs: List[str] = field(default_factory=list)


@dataclass
class DonationEvent(BaseEvent):
    """
    Donation/gift event.

    Represents a gift or donation received by a public official.
    """
    event_type: EventType = field(default="donation", init=False)

    # Specific fields
    tipo_donativo: Optional[str] = None
    descripcion: Optional[str] = None
    ocasion: Optional[str] = None
    donantes_refs: List[str] = field(default_factory=list)


def _normalize_ref(name: Optional[str]) -> Optional[str]:
    """
    Normalize a name for entity reference.

    Returns None if name is empty or whitespace-only after normalization.
    """
    if not name:
        return None
    normalized = normalize_for_matching(name)
    return normalized if normalized else None


def _normalize_ref_list(names: List[str]) -> List[str]:
    """Normalize a list of names, filtering out empty results."""
    result = []
    for name in names:
        normalized = _normalize_ref(name)
        if normalized:
            result.append(normalized)
    return result


def _parse_materias(materias_str: Optional[str]) -> List[str]:
    """
    Parse materias string into list.

    InfoLobby uses various separators: comma, semicolon, newline.
    """
    if not materias_str:
        return []

    # Split by common separators
    items = []
    for part in materias_str.replace(";", ",").replace("\n", ",").split(","):
        cleaned = part.strip()
        if cleaned:
            items.append(cleaned)

    return items


def _parse_representados(representados_str: Optional[str]) -> List[str]:
    """
    Parse representados string into list of organization names.

    Format varies: comma-separated, dash-separated, etc.
    """
    if not representados_str:
        return []

    # Try common separators
    names = []
    # First try splitting by common separators
    for sep in [" - ", ", ", "; ", "\n"]:
        if sep in representados_str:
            names = [n.strip() for n in representados_str.split(sep)]
            break

    # If no separator found, treat as single name
    if not names:
        names = [representados_str.strip()]

    return [n for n in names if n]


def _parse_financistas(financistas_str: Optional[str]) -> List[str]:
    """Parse financistas string into list of funder names."""
    if not financistas_str:
        return []

    # Similar logic to representados
    names = []
    for sep in [" - ", ", ", "; ", "\n"]:
        if sep in financistas_str:
            names = [n.strip() for n in financistas_str.split(sep)]
            break

    if not names:
        names = [financistas_str.strip()]

    return [n for n in names if n]


def _parse_donantes(donantes_str: Optional[str]) -> List[str]:
    """Parse donantes string into list of donor names."""
    if not donantes_str:
        return []

    names = []
    for sep in [" - ", ", ", "; ", "\n"]:
        if sep in donantes_str:
            names = [n.strip() for n in donantes_str.split(sep)]
            break

    if not names:
        names = [donantes_str.strip()]

    return [n for n in names if n]


def extract_audience_event(audiencia: ParsedAudiencia) -> AudienceEvent:
    """
    Extract an AudienceEvent from a ParsedAudiencia.

    Args:
        audiencia: Parsed audiencia record from SPARQL

    Returns:
        AudienceEvent with normalized entity references
    """
    # Get date from datetime
    date_start = None
    if audiencia.fecha_evento:
        date_start = audiencia.fecha_evento.date() if isinstance(
            audiencia.fecha_evento, datetime
        ) else audiencia.fecha_evento

    # Normalize pasivo reference
    pasivo_ref = None
    if audiencia.pasivo:
        pasivo_ref = _normalize_ref(audiencia.pasivo.nombre)

    # Normalize activos references
    activos_refs = _normalize_ref_list(audiencia.activos)

    # Parse and normalize representados
    representados = _parse_representados(audiencia.representados)
    representados_refs = _normalize_ref_list(representados)

    # Parse materias
    materias = _parse_materias(audiencia.materias)

    return AudienceEvent(
        external_id=audiencia.codigo_uri,
        date_start=date_start,
        pasivo_ref=pasivo_ref,
        activos_refs=activos_refs,
        representados_refs=representados_refs,
        lugar=None,  # Not in current SPARQL data
        forma=audiencia.tipo,
        materias=materias,
        descripcion=audiencia.descripcion,
        observaciones=audiencia.observaciones,
    )


def extract_travel_event(viaje: ParsedViaje) -> TravelEvent:
    """
    Extract a TravelEvent from a ParsedViaje.

    Args:
        viaje: Parsed viaje record from SPARQL

    Returns:
        TravelEvent with normalized entity references
    """
    # Parse financistas and normalize
    financistas = _parse_financistas(viaje.financistas)
    financiadores_refs = _normalize_ref_list(financistas)

    # Build destination from available fields
    destino = None
    if viaje.objetos:
        destino = viaje.objetos

    return TravelEvent(
        external_id=viaje.codigo_uri,
        date_start=viaje.fecha_evento,
        pasivo_ref=None,  # Viajes don't have explicit pasivo in SPARQL
        destino=destino,
        motivo=viaje.razones,
        costo_total=viaje.costo,
        financiadores_refs=financiadores_refs,
    )


def extract_donation_event(donativo: ParsedDonativo) -> DonationEvent:
    """
    Extract a DonationEvent from a ParsedDonativo.

    Args:
        donativo: Parsed donativo record from SPARQL

    Returns:
        DonationEvent with normalized entity references
    """
    # Parse donantes and normalize
    donantes = _parse_donantes(donativo.donantes)
    donantes_refs = _normalize_ref_list(donantes)

    return DonationEvent(
        external_id=donativo.codigo_uri,
        date_start=donativo.fecha_evento,
        pasivo_ref=None,  # Donativos don't have explicit pasivo in SPARQL
        tipo_donativo=None,  # Not in current SPARQL data
        descripcion=donativo.descripcion,
        ocasion=donativo.ocasion,
        donantes_refs=donantes_refs,
    )


def extract_events(
    audiencias: Optional[List[ParsedAudiencia]] = None,
    viajes: Optional[List[ParsedViaje]] = None,
    donativos: Optional[List[ParsedDonativo]] = None,
) -> List[Union[AudienceEvent, TravelEvent, DonationEvent]]:
    """
    Extract events from parsed SPARQL records.

    Transforms parsed records into typed event objects with normalized
    entity references for later linking in the graph.

    Args:
        audiencias: List of parsed audiencia records
        viajes: List of parsed viaje records
        donativos: List of parsed donativo records

    Returns:
        List of extracted events (AudienceEvent, TravelEvent, DonationEvent)

    Example:
        >>> from services.info_lobby_sync.parser import parse_all_audiencias
        >>> from services.info_lobby_sync.events import extract_events
        >>>
        >>> raw_records = fetch_audiencias(client, limit=100)
        >>> parsed = parse_all_audiencias(raw_records)
        >>> events = extract_events(audiencias=parsed)
        >>> print(f"Extracted {len(events)} audience events")
    """
    events: List[Union[AudienceEvent, TravelEvent, DonationEvent]] = []

    # Extract audience events
    if audiencias:
        for audiencia in audiencias:
            events.append(extract_audience_event(audiencia))

    # Extract travel events
    if viajes:
        for viaje in viajes:
            events.append(extract_travel_event(viaje))

    # Extract donation events
    if donativos:
        for donativo in donativos:
            events.append(extract_donation_event(donativo))

    return events
