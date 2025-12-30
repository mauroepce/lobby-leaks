"""
Persistence layer for InfoLobby SPARQL data.

Handles UPSERT of parsed+merged entities into PostgreSQL canonical tables
using the existing canonical_persistence module from lobby_collector.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import text
from sqlalchemy.engine import Engine

from services._template.db.connector import get_engine
from services.info_lobby_sync.merge import MergeResult


@dataclass
class PersistenceResult:
    """Result of persistence operation with counts."""
    persons_inserted: int = 0
    persons_updated: int = 0
    persons_unchanged: int = 0
    orgs_inserted: int = 0
    orgs_updated: int = 0
    orgs_unchanged: int = 0
    total_processed: int = 0
    errors: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    @property
    def duration_seconds(self) -> float:
        """Calculate duration in seconds."""
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "persons_inserted": self.persons_inserted,
            "persons_updated": self.persons_updated,
            "persons_unchanged": self.persons_unchanged,
            "orgs_inserted": self.orgs_inserted,
            "orgs_updated": self.orgs_updated,
            "orgs_unchanged": self.orgs_unchanged,
            "total_processed": self.total_processed,
            "errors": self.errors,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_seconds": self.duration_seconds,
        }


def persist_merge_result(
    engine: Engine,
    merge_result: MergeResult,
    source: str = "infolobby_sparql"
) -> PersistenceResult:
    """
    Persist merged entities to canonical database tables.

    Uses UPSERT (INSERT ... ON CONFLICT) for idempotent operations.
    - Persons with existing_id → UPDATE if changed
    - Persons without existing_id → INSERT
    - Same for Organisations

    Args:
        engine: SQLAlchemy database engine
        merge_result: Result from merge_records() containing entities
        source: Source identifier for tracking data origin

    Returns:
        PersistenceResult with operation counts
    """
    result = PersistenceResult(started_at=datetime.utcnow())

    try:
        with engine.begin() as conn:
            # Persist persons
            for person in merge_result.persons:
                try:
                    outcome = _upsert_person(conn, person, source)
                    if outcome == "inserted":
                        result.persons_inserted += 1
                    elif outcome == "updated":
                        result.persons_updated += 1
                    else:
                        result.persons_unchanged += 1
                except Exception as e:
                    result.errors.append(f"Person {person.get('name', 'unknown')}: {str(e)}")

            # Persist organisations
            for org in merge_result.organisations:
                try:
                    outcome = _upsert_organisation(conn, org, source)
                    if outcome == "inserted":
                        result.orgs_inserted += 1
                    elif outcome == "updated":
                        result.orgs_updated += 1
                    else:
                        result.orgs_unchanged += 1
                except Exception as e:
                    result.errors.append(f"Organisation {org.get('name', 'unknown')}: {str(e)}")

    except Exception as e:
        result.errors.append(f"Database error: {str(e)}")

    result.total_processed = (
        result.persons_inserted + result.persons_updated + result.persons_unchanged +
        result.orgs_inserted + result.orgs_updated + result.orgs_unchanged
    )
    result.finished_at = datetime.utcnow()

    return result


def _upsert_person(
    conn,
    person: Dict[str, Any],
    source: str
) -> str:
    """
    Upsert a person entity.

    Returns: "inserted", "updated", or "unchanged"
    """
    now = datetime.utcnow()
    tenant_code = person.get("tenant_code", "CL")
    normalized_name = person["normalized_name"]
    existing_id = person.get("existing_id")

    if existing_id:
        # Check if update is needed
        check_query = text("""
            SELECT cargo FROM "Person"
            WHERE id = :id
        """)
        result = conn.execute(check_query, {"id": existing_id})
        row = result.fetchone()

        if row:
            current_cargo = row[0]
            new_cargo = person.get("cargo")

            # Only update if we have new cargo and current is null
            if new_cargo and not current_cargo:
                update_query = text("""
                    UPDATE "Person"
                    SET cargo = :cargo,
                        "updatedAt" = :updated_at,
                        source = :source
                    WHERE id = :id
                """)
                conn.execute(update_query, {
                    "id": existing_id,
                    "cargo": new_cargo,
                    "updated_at": now,
                    "source": source,
                })
                return "updated"

        return "unchanged"

    # Insert new person
    new_id = str(uuid.uuid4())
    insert_query = text("""
        INSERT INTO "Person" (
            id, "tenantCode", "normalizedName",
            nombres, apellidos, "nombresCompletos", cargo,
            source, "createdAt", "updatedAt"
        )
        VALUES (
            :id, :tenant_code, :normalized_name,
            :nombres, :apellidos, :nombres_completos, :cargo,
            :source, :created_at, :updated_at
        )
        ON CONFLICT ("tenantCode", "normalizedName") DO UPDATE
        SET cargo = COALESCE("Person".cargo, EXCLUDED.cargo),
            source = EXCLUDED.source,
            "updatedAt" = EXCLUDED."updatedAt"
        RETURNING (xmax = 0) AS inserted
    """)

    result = conn.execute(insert_query, {
        "id": new_id,
        "tenant_code": tenant_code,
        "normalized_name": normalized_name,
        "nombres": _extract_nombres(person["name"]),
        "apellidos": _extract_apellidos(person["name"]),
        "nombres_completos": person["name"],
        "cargo": person.get("cargo"),
        "source": source,
        "created_at": now,
        "updated_at": now,
    })

    row = result.fetchone()
    return "inserted" if row and row[0] else "updated"


def _upsert_organisation(
    conn,
    org: Dict[str, Any],
    source: str
) -> str:
    """
    Upsert an organisation entity.

    Returns: "inserted", "updated", or "unchanged"
    """
    now = datetime.utcnow()
    tenant_code = org.get("tenant_code", "CL")
    normalized_name = org["normalized_name"]
    existing_id = org.get("existing_id")

    if existing_id:
        # Check if update is needed
        check_query = text("""
            SELECT tipo FROM "Organisation"
            WHERE id = :id
        """)
        result = conn.execute(check_query, {"id": existing_id})
        row = result.fetchone()

        if row:
            current_tipo = row[0]
            new_tipo = org.get("tipo")

            # Only update if we have new tipo and current is null
            if new_tipo and not current_tipo:
                update_query = text("""
                    UPDATE "Organisation"
                    SET tipo = :tipo,
                        "updatedAt" = :updated_at,
                        source = :source
                    WHERE id = :id
                """)
                conn.execute(update_query, {
                    "id": existing_id,
                    "tipo": new_tipo,
                    "updated_at": now,
                    "source": source,
                })
                return "updated"

        return "unchanged"

    # Insert new organisation
    new_id = str(uuid.uuid4())
    insert_query = text("""
        INSERT INTO "Organisation" (
            id, "tenantCode", "normalizedName",
            name, tipo,
            source, "createdAt", "updatedAt"
        )
        VALUES (
            :id, :tenant_code, :normalized_name,
            :name, :tipo,
            :source, :created_at, :updated_at
        )
        ON CONFLICT ("tenantCode", "normalizedName") DO UPDATE
        SET tipo = COALESCE("Organisation".tipo, EXCLUDED.tipo),
            source = EXCLUDED.source,
            "updatedAt" = EXCLUDED."updatedAt"
        RETURNING (xmax = 0) AS inserted
    """)

    result = conn.execute(insert_query, {
        "id": new_id,
        "tenant_code": tenant_code,
        "normalized_name": normalized_name,
        "name": org["name"],
        "tipo": org.get("tipo"),
        "source": source,
        "created_at": now,
        "updated_at": now,
    })

    row = result.fetchone()
    return "inserted" if row and row[0] else "updated"


def _extract_nombres(full_name: str) -> Optional[str]:
    """Extract first name(s) from full name (best effort)."""
    if not full_name:
        return None
    parts = full_name.strip().split()
    if len(parts) >= 2:
        # Assume first part is nombre
        return parts[0]
    return full_name


def _extract_apellidos(full_name: str) -> Optional[str]:
    """Extract last name(s) from full name (best effort)."""
    if not full_name:
        return None
    parts = full_name.strip().split()
    if len(parts) >= 2:
        # Assume rest are apellidos
        return " ".join(parts[1:])
    return None
