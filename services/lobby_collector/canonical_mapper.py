"""
Canonical entity mapper: extracts Person, Organisation, Event, Edge from staging.

Maps staging VIEW rows to canonical graph entities for relationship analysis.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from uuid import uuid4

from services.lobby_collector.staging import (
    normalize_person_name,
    normalize_rut,
    extract_rut_from_raw,
)


class EntityBundle:
    """
    Bundle of canonical entities extracted from a single staging row.

    Represents all entities (Person, Org, Event, Edges) that should be
    created/updated from one lobby event.
    """

    def __init__(self):
        self.persons: List[Dict[str, Any]] = []
        self.organisations: List[Dict[str, Any]] = []
        self.events: List[Dict[str, Any]] = []
        self.edges: List[Dict[str, Any]] = []

    def add_person(
        self,
        tenant_code: str,
        nombres: str,
        apellidos: str,
        cargo: Optional[str] = None,
        rut: Optional[str] = None,
    ) -> str:
        """
        Add a Person entity to the bundle.

        Returns the person's ID (UUID) for creating edges.
        """
        person_id = str(uuid4())
        normalized_name = normalize_person_name(nombres, apellidos)

        self.persons.append({
            "id": person_id,
            "tenantCode": tenant_code,
            "rut": rut,
            "normalizedName": normalized_name,
            "nombres": nombres,
            "apellidos": apellidos,
            "nombresCompletos": f"{nombres} {apellidos}".strip(),
            "cargo": cargo,
        })

        return person_id

    def add_organisation(
        self,
        tenant_code: str,
        name: str,
        tipo: Optional[str] = None,
        rut: Optional[str] = None,
    ) -> str:
        """
        Add an Organisation entity to the bundle.

        Returns the organisation's ID (UUID) for creating edges.
        """
        org_id = str(uuid4())
        normalized_name = name.strip().lower() if name else ""

        self.organisations.append({
            "id": org_id,
            "tenantCode": tenant_code,
            "rut": rut,
            "normalizedName": normalized_name,
            "name": name,
            "tipo": tipo,
        })

        return org_id

    def add_event(
        self,
        tenant_code: str,
        external_id: str,
        kind: str,
        fecha: Optional[datetime] = None,
        descripcion: Optional[str] = None,
    ) -> str:
        """
        Add an Event entity to the bundle.

        Returns the event's ID (UUID) for creating edges.
        """
        event_id = str(uuid4())

        self.events.append({
            "id": event_id,
            "tenantCode": tenant_code,
            "externalId": external_id,
            "kind": kind,
            "fecha": fecha,
            "descripcion": descripcion,
        })

        return event_id

    def add_edge(
        self,
        tenant_code: str,
        event_id: str,
        label: str,
        from_person_id: Optional[str] = None,
        from_org_id: Optional[str] = None,
        to_person_id: Optional[str] = None,
        to_org_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Add an Edge entity to the bundle.

        Edge must have exactly one 'from' entity (person or org) and
        exactly one 'to' entity (person or org).
        """
        # Validate edge has exactly one from and one to
        from_count = sum([from_person_id is not None, from_org_id is not None])
        to_count = sum([to_person_id is not None, to_org_id is not None])

        if from_count != 1 or to_count != 1:
            raise ValueError(
                f"Edge must have exactly one from and one to entity. "
                f"Got from_count={from_count}, to_count={to_count}"
            )

        edge_id = str(uuid4())

        self.edges.append({
            "id": edge_id,
            "tenantCode": tenant_code,
            "eventId": event_id,
            "label": label,
            "fromPersonId": from_person_id,
            "fromOrgId": from_org_id,
            "toPersonId": to_person_id,
            "toOrgId": to_org_id,
            "metadata": metadata,
        })


def map_staging_row(row: Dict[str, Any], raw_data: Dict[str, Any]) -> EntityBundle:
    """
    Map a staging VIEW row to canonical entities.

    Args:
        row: Row from lobby_events_staging VIEW
        raw_data: Full raw JSONB data from LobbyEventRaw

    Returns:
        EntityBundle with Person, Org, Event, and Edge entities

    Edge rules by kind:
    - audiencia: Person MEETS Person/Org (sujeto activo meets sujeto pasivo)
    - viaje: Person TRAVELS_TO Org (person travels to destination org)
    - donativo: Org CONTRIBUTES Person (donor org contributes to recipient person)
    """
    bundle = EntityBundle()
    tenant_code = row["tenantCode"]
    kind = row["kind"]

    # Create Event entity
    event_id = bundle.add_event(
        tenant_code=tenant_code,
        external_id=row["externalId"],
        kind=kind,
        fecha=row.get("fecha"),
        descripcion=raw_data.get("descripcion") or raw_data.get("materia"),
    )

    # Extract RUT from raw data if available
    rut = extract_rut_from_raw(raw_data)
    normalized_rut = normalize_rut(rut) if rut else None

    # Map by kind
    if kind == "audiencia":
        _map_audiencia(bundle, row, raw_data, event_id, tenant_code, normalized_rut)
    elif kind == "viaje":
        _map_viaje(bundle, row, raw_data, event_id, tenant_code, normalized_rut)
    elif kind == "donativo":
        _map_donativo(bundle, row, raw_data, event_id, tenant_code, normalized_rut)

    return bundle


def _map_audiencia(
    bundle: EntityBundle,
    row: Dict[str, Any],
    raw_data: Dict[str, Any],
    event_id: str,
    tenant_code: str,
    rut: Optional[str],
):
    """
    Map audiencia: Person MEETS Person/Org.

    Sujeto activo (person with RUT) meets sujeto pasivo (institution/person).
    """
    # Create sujeto activo (person)
    person_id = bundle.add_person(
        tenant_code=tenant_code,
        nombres=row.get("nombres") or "",
        apellidos=row.get("apellidos") or "",
        cargo=row.get("cargo"),
        rut=rut,
    )

    # Create sujeto pasivo (institution as Organisation)
    institucion = row.get("institucion")
    if institucion:
        # Infer tipo from institucion name
        tipo = _infer_org_tipo(institucion)

        org_id = bundle.add_organisation(
            tenant_code=tenant_code,
            name=institucion,
            tipo=tipo,
        )

        # Person MEETS Organisation
        bundle.add_edge(
            tenant_code=tenant_code,
            event_id=event_id,
            label="MEETS",
            from_person_id=person_id,
            to_org_id=org_id,
            metadata={
                "fecha": row.get("fecha").isoformat() if row.get("fecha") else None,
                "cargo": row.get("cargo"),
            },
        )


def _map_viaje(
    bundle: EntityBundle,
    row: Dict[str, Any],
    raw_data: Dict[str, Any],
    event_id: str,
    tenant_code: str,
    rut: Optional[str],
):
    """
    Map viaje: Person TRAVELS_TO Org.

    Person travels to destination institution/location.
    """
    # Create person (traveler)
    person_id = bundle.add_person(
        tenant_code=tenant_code,
        nombres=row.get("nombres") or "",
        apellidos=row.get("apellidos") or "",
        cargo=row.get("cargo"),
        rut=rut,
    )

    # Create destination organisation
    institucion = row.get("institucion")  # institucion_destino
    if institucion:
        org_id = bundle.add_organisation(
            tenant_code=tenant_code,
            name=institucion,
            tipo="destino",  # Generic type for destination
        )

        # Person TRAVELS_TO Organisation
        bundle.add_edge(
            tenant_code=tenant_code,
            event_id=event_id,
            label="TRAVELS_TO",
            from_person_id=person_id,
            to_org_id=org_id,
            metadata={
                "destino": row.get("destino"),
                "fecha": row.get("fecha").isoformat() if row.get("fecha") else None,
            },
        )


def _map_donativo(
    bundle: EntityBundle,
    row: Dict[str, Any],
    raw_data: Dict[str, Any],
    event_id: str,
    tenant_code: str,
    rut: Optional[str],
):
    """
    Map donativo: Org CONTRIBUTES Person.

    Donor organisation contributes to recipient person (political figure).
    """
    # Create recipient person
    person_id = bundle.add_person(
        tenant_code=tenant_code,
        nombres=row.get("nombres") or "",
        apellidos=row.get("apellidos") or "",
        cargo=row.get("cargo"),
        rut=rut,
    )

    # Create donor organisation
    institucion = row.get("institucion")  # institucion_donante
    if institucion:
        tipo = _infer_org_tipo(institucion)
        org_id = bundle.add_organisation(
            tenant_code=tenant_code,
            name=institucion,
            tipo=tipo,
        )

        # Organisation CONTRIBUTES Person
        bundle.add_edge(
            tenant_code=tenant_code,
            event_id=event_id,
            label="CONTRIBUTES",
            from_org_id=org_id,
            to_person_id=person_id,
            metadata={
                "monto": str(row.get("monto")) if row.get("monto") else None,
                "fecha": row.get("fecha").isoformat() if row.get("fecha") else None,
            },
        )


def _infer_org_tipo(name: str) -> str:
    """
    Infer organisation type from name.

    Uses heuristics to classify Chilean institutions.
    """
    name_lower = name.lower()

    if "ministerio" in name_lower:
        return "ministerio"
    elif "subsecretaría" in name_lower or "subsecretaria" in name_lower:
        return "subsecretaria"
    elif any(word in name_lower for word in ["cámara", "camara", "senado", "congreso"]):
        return "legislativo"
    elif any(word in name_lower for word in ["tribunal", "corte", "justicia"]):
        return "judicial"
    elif "partido" in name_lower:
        return "partido"
    elif any(word in name_lower for word in ["empresa", "s.a.", "sa", "ltda"]):
        return "empresa"
    elif any(word in name_lower for word in ["fundación", "fundacion", "ong"]):
        return "ong"
    else:
        return "otro"
