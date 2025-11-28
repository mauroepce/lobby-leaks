"""
Canonical entity persistence with idempotent UPSERT logic.

Persists Person, Organisation, Event, and Edge entities to PostgreSQL
using natural keys for deduplication.
"""

from typing import Dict, Any, Optional
import json
from sqlalchemy import text
from sqlalchemy.engine import Engine
from datetime import datetime

from services.lobby_collector.canonical_mapper import EntityBundle


def upsert_canonical(engine: Engine, bundle: EntityBundle) -> Dict[str, Any]:
    """
    Upsert canonical entities from bundle to database.

    Uses idempotent UPSERT with natural keys:
    - Person: (tenantCode, rut) OR (tenantCode, normalizedName)
    - Organisation: (tenantCode, rut) OR (tenantCode, normalizedName)
    - Event: (tenantCode, externalId, kind)
    - Edge: (eventId, fromPersonId, fromOrgId, toPersonId, toOrgId, label)

    Args:
        engine: SQLAlchemy engine
        bundle: EntityBundle with entities to persist

    Returns:
        Statistics dict with counts of created/updated entities

    Example:
        >>> bundle = map_staging_row(row, raw_data)
        >>> stats = upsert_canonical(engine, bundle)
        >>> print(stats)
        {'persons_created': 1, 'orgs_created': 1, 'events_created': 1, 'edges_created': 1}
    """
    stats = {
        "persons_created": 0,
        "persons_updated": 0,
        "orgs_created": 0,
        "orgs_updated": 0,
        "events_created": 0,
        "events_updated": 0,
        "edges_created": 0,
        "edges_updated": 0,
    }

    # Track ID mappings for edges (bundle IDs -> DB IDs)
    person_id_map: Dict[str, str] = {}
    org_id_map: Dict[str, str] = {}
    event_id_map: Dict[str, str] = {}

    with engine.begin() as conn:
        # 1. Upsert Persons
        for person in bundle.persons:
            result = _upsert_person(conn, person)
            person_id_map[person["id"]] = result["id"]
            if result["created"]:
                stats["persons_created"] += 1
            else:
                stats["persons_updated"] += 1

        # 2. Upsert Organisations
        for org in bundle.organisations:
            result = _upsert_organisation(conn, org)
            org_id_map[org["id"]] = result["id"]
            if result["created"]:
                stats["orgs_created"] += 1
            else:
                stats["orgs_updated"] += 1

        # 3. Upsert Events
        for event in bundle.events:
            result = _upsert_event(conn, event)
            event_id_map[event["id"]] = result["id"]
            if result["created"]:
                stats["events_created"] += 1
            else:
                stats["events_updated"] += 1

        # 4. Upsert Edges (with mapped IDs)
        for edge in bundle.edges:
            # Map bundle IDs to DB IDs
            mapped_edge = {
                "tenantCode": edge["tenantCode"],
                "eventId": event_id_map[edge["eventId"]],
                "label": edge["label"],
                "fromPersonId": person_id_map.get(edge["fromPersonId"]) if edge["fromPersonId"] else None,
                "fromOrgId": org_id_map.get(edge["fromOrgId"]) if edge["fromOrgId"] else None,
                "toPersonId": person_id_map.get(edge["toPersonId"]) if edge["toPersonId"] else None,
                "toOrgId": org_id_map.get(edge["toOrgId"]) if edge["toOrgId"] else None,
                "metadata": edge["metadata"],
            }

            result = _upsert_edge(conn, mapped_edge)
            if result["created"]:
                stats["edges_created"] += 1
            else:
                stats["edges_updated"] += 1

    return stats


def _upsert_person(conn, person: Dict[str, Any]) -> Dict[str, Any]:
    """
    Upsert a Person entity.

    Natural key: (tenantCode, rut) if RUT exists, else (tenantCode, normalizedName)

    Returns: {"id": str, "created": bool}
    """
    now = datetime.utcnow()

    # Try to find existing person by RUT first
    if person["rut"]:
        query = text("""
            SELECT id FROM "Person"
            WHERE "tenantCode" = :tenant_code AND rut = :rut
        """)
        result = conn.execute(query, {
            "tenant_code": person["tenantCode"],
            "rut": person["rut"],
        })
        existing = result.fetchone()

        if existing:
            # Update existing person
            update_query = text("""
                UPDATE "Person"
                SET
                    "normalizedName" = :normalized_name,
                    nombres = :nombres,
                    apellidos = :apellidos,
                    "nombresCompletos" = :nombres_completos,
                    cargo = :cargo,
                    "updatedAt" = :updated_at
                WHERE id = :id
            """)
            conn.execute(update_query, {
                "id": existing[0],
                "normalized_name": person["normalizedName"],
                "nombres": person["nombres"],
                "apellidos": person["apellidos"],
                "nombres_completos": person["nombresCompletos"],
                "cargo": person["cargo"],
                "updated_at": now,
            })
            return {"id": existing[0], "created": False}

    # Try to find by normalizedName
    query = text("""
        SELECT id FROM "Person"
        WHERE "tenantCode" = :tenant_code AND "normalizedName" = :normalized_name
    """)
    result = conn.execute(query, {
        "tenant_code": person["tenantCode"],
        "normalized_name": person["normalizedName"],
    })
    existing = result.fetchone()

    if existing:
        # Update existing person (add RUT if it didn't exist)
        update_query = text("""
            UPDATE "Person"
            SET
                rut = COALESCE(rut, :rut),
                nombres = :nombres,
                apellidos = :apellidos,
                "nombresCompletos" = :nombres_completos,
                cargo = :cargo,
                "updatedAt" = :updated_at
            WHERE id = :id
        """)
        conn.execute(update_query, {
            "id": existing[0],
            "rut": person["rut"],
            "nombres": person["nombres"],
            "apellidos": person["apellidos"],
            "nombres_completos": person["nombresCompletos"],
            "cargo": person["cargo"],
            "updated_at": now,
        })
        return {"id": existing[0], "created": False}

    # Insert new person
    insert_query = text("""
        INSERT INTO "Person" (
            id, "tenantCode", rut, "normalizedName",
            nombres, apellidos, "nombresCompletos", cargo,
            "createdAt", "updatedAt"
        )
        VALUES (
            gen_random_uuid()::text, :tenant_code, :rut, :normalized_name,
            :nombres, :apellidos, :nombres_completos, :cargo,
            :created_at, :updated_at
        )
        RETURNING id
    """)
    result = conn.execute(insert_query, {
        "tenant_code": person["tenantCode"],
        "rut": person["rut"],
        "normalized_name": person["normalizedName"],
        "nombres": person["nombres"],
        "apellidos": person["apellidos"],
        "nombres_completos": person["nombresCompletos"],
        "cargo": person["cargo"],
        "created_at": now,
        "updated_at": now,
    })
    new_id = result.fetchone()[0]
    return {"id": new_id, "created": True}


def _upsert_organisation(conn, org: Dict[str, Any]) -> Dict[str, Any]:
    """
    Upsert an Organisation entity.

    Natural key: (tenantCode, rut) if RUT exists, else (tenantCode, normalizedName)

    Returns: {"id": str, "created": bool}
    """
    now = datetime.utcnow()

    # Try to find existing org by RUT first
    if org["rut"]:
        query = text("""
            SELECT id FROM "Organisation"
            WHERE "tenantCode" = :tenant_code AND rut = :rut
        """)
        result = conn.execute(query, {
            "tenant_code": org["tenantCode"],
            "rut": org["rut"],
        })
        existing = result.fetchone()

        if existing:
            # Update existing org
            update_query = text("""
                UPDATE "Organisation"
                SET
                    "normalizedName" = :normalized_name,
                    name = :name,
                    tipo = :tipo,
                    "updatedAt" = :updated_at
                WHERE id = :id
            """)
            conn.execute(update_query, {
                "id": existing[0],
                "normalized_name": org["normalizedName"],
                "name": org["name"],
                "tipo": org["tipo"],
                "updated_at": now,
            })
            return {"id": existing[0], "created": False}

    # Try to find by normalizedName
    query = text("""
        SELECT id FROM "Organisation"
        WHERE "tenantCode" = :tenant_code AND "normalizedName" = :normalized_name
    """)
    result = conn.execute(query, {
        "tenant_code": org["tenantCode"],
        "normalized_name": org["normalizedName"],
    })
    existing = result.fetchone()

    if existing:
        # Update existing org
        update_query = text("""
            UPDATE "Organisation"
            SET
                rut = COALESCE(rut, :rut),
                name = :name,
                tipo = :tipo,
                "updatedAt" = :updated_at
            WHERE id = :id
        """)
        conn.execute(update_query, {
            "id": existing[0],
            "rut": org["rut"],
            "name": org["name"],
            "tipo": org["tipo"],
            "updated_at": now,
        })
        return {"id": existing[0], "created": False}

    # Insert new organisation
    insert_query = text("""
        INSERT INTO "Organisation" (
            id, "tenantCode", rut, "normalizedName",
            name, tipo,
            "createdAt", "updatedAt"
        )
        VALUES (
            gen_random_uuid()::text, :tenant_code, :rut, :normalized_name,
            :name, :tipo,
            :created_at, :updated_at
        )
        RETURNING id
    """)
    result = conn.execute(insert_query, {
        "tenant_code": org["tenantCode"],
        "rut": org["rut"],
        "normalized_name": org["normalizedName"],
        "name": org["name"],
        "tipo": org["tipo"],
        "created_at": now,
        "updated_at": now,
    })
    new_id = result.fetchone()[0]
    return {"id": new_id, "created": True}


def _upsert_event(conn, event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Upsert an Event entity.

    Natural key: (tenantCode, externalId, kind)

    Returns: {"id": str, "created": bool}
    """
    now = datetime.utcnow()

    # Try to find existing event
    query = text("""
        SELECT id FROM "Event"
        WHERE "tenantCode" = :tenant_code
          AND "externalId" = :external_id
          AND kind = :kind
    """)
    result = conn.execute(query, {
        "tenant_code": event["tenantCode"],
        "external_id": event["externalId"],
        "kind": event["kind"],
    })
    existing = result.fetchone()

    if existing:
        # Update existing event
        update_query = text("""
            UPDATE "Event"
            SET
                fecha = :fecha,
                descripcion = :descripcion,
                "updatedAt" = :updated_at
            WHERE id = :id
        """)
        conn.execute(update_query, {
            "id": existing[0],
            "fecha": event["fecha"],
            "descripcion": event["descripcion"],
            "updated_at": now,
        })
        return {"id": existing[0], "created": False}

    # Insert new event
    insert_query = text("""
        INSERT INTO "Event" (
            id, "tenantCode", "externalId", kind,
            fecha, descripcion,
            "createdAt", "updatedAt"
        )
        VALUES (
            gen_random_uuid()::text, :tenant_code, :external_id, :kind,
            :fecha, :descripcion,
            :created_at, :updated_at
        )
        RETURNING id
    """)
    result = conn.execute(insert_query, {
        "tenant_code": event["tenantCode"],
        "external_id": event["externalId"],
        "kind": event["kind"],
        "fecha": event["fecha"],
        "descripcion": event["descripcion"],
        "created_at": now,
        "updated_at": now,
    })
    new_id = result.fetchone()[0]
    return {"id": new_id, "created": True}


def _upsert_edge(conn, edge: Dict[str, Any]) -> Dict[str, Any]:
    """
    Upsert an Edge entity.

    Natural key: (eventId, fromPersonId, fromOrgId, toPersonId, toOrgId, label)

    Returns: {"id": str, "created": bool}
    """
    now = datetime.utcnow()

    # Try to find existing edge
    query = text("""
        SELECT id FROM "Edge"
        WHERE "eventId" = :event_id
          AND "fromPersonId" IS NOT DISTINCT FROM :from_person_id
          AND "fromOrgId" IS NOT DISTINCT FROM :from_org_id
          AND "toPersonId" IS NOT DISTINCT FROM :to_person_id
          AND "toOrgId" IS NOT DISTINCT FROM :to_org_id
          AND label = :label
    """)
    result = conn.execute(query, {
        "event_id": edge["eventId"],
        "from_person_id": edge["fromPersonId"],
        "from_org_id": edge["fromOrgId"],
        "to_person_id": edge["toPersonId"],
        "to_org_id": edge["toOrgId"],
        "label": edge["label"],
    })
    existing = result.fetchone()

    if existing:
        # Update existing edge (just metadata and timestamp)
        update_query = text("""
            UPDATE "Edge"
            SET
                metadata = :metadata,
                "updatedAt" = :updated_at
            WHERE id = :id
        """)
        conn.execute(update_query, {
            "id": existing[0],
            "metadata": json.dumps(edge["metadata"]) if edge["metadata"] else None,
            "updated_at": now,
        })
        return {"id": existing[0], "created": False}

    # Insert new edge
    insert_query = text("""
        INSERT INTO "Edge" (
            id, "tenantCode", "eventId", label,
            "fromPersonId", "fromOrgId", "toPersonId", "toOrgId",
            metadata,
            "createdAt", "updatedAt"
        )
        VALUES (
            gen_random_uuid()::text, :tenant_code, :event_id, :label,
            :from_person_id, :from_org_id, :to_person_id, :to_org_id,
            :metadata,
            :created_at, :updated_at
        )
        RETURNING id
    """)
    result = conn.execute(insert_query, {
        "tenant_code": edge["tenantCode"],
        "event_id": edge["eventId"],
        "label": edge["label"],
        "from_person_id": edge["fromPersonId"],
        "from_org_id": edge["fromOrgId"],
        "to_person_id": edge["toPersonId"],
        "to_org_id": edge["toOrgId"],
        "metadata": json.dumps(edge["metadata"]) if edge["metadata"] else None,
        "created_at": now,
        "updated_at": now,
    })
    new_id = result.fetchone()[0]
    return {"id": new_id, "created": True}
