"""
Merge logic for InfoLobby SPARQL data.

Normalizes and deduplicates entities (Person, Organisation) against
the canonical database using exact normalized name matching.

Strategy:
- No RUT available in SPARQL data, so matching is by normalized name only
- Exact match on normalized name (no fuzzy matching)
- Roles (activo/pasivo/asistente) are modeled in relationships, not entity identity
- Homonyms are intentionally not resolved (conservative for future triangulation)
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Engine


@dataclass
class MergeResult:
    """Result of merge operation with metrics."""
    persons: List[Dict[str, Any]]
    organisations: List[Dict[str, Any]]
    duplicates_found: int = 0
    merged_count: int = 0
    persons_existing: int = 0
    persons_new: int = 0
    orgs_existing: int = 0
    orgs_new: int = 0


def normalize_for_matching(name: str) -> str:
    """
    Normalize name for exact matching.

    Rules:
    - lowercase
    - remove accents (NFD decomposition + strip combining marks)
    - remove punctuation
    - collapse whitespace
    - trim

    Args:
        name: Raw name string

    Returns:
        Normalized name for matching

    Examples:
        >>> normalize_for_matching("José María López")
        'jose maria lopez'
        >>> normalize_for_matching("  GARCÍA-HUIDOBRO,  Juan  ")
        'garcia huidobro juan'
        >>> normalize_for_matching("Corporación de Fomento (CORFO)")
        'corporacion de fomento corfo'
    """
    if not name or not isinstance(name, str):
        return ""

    # Lowercase
    result = name.lower()

    # Remove accents: NFD decomposition + strip combining marks
    result = unicodedata.normalize("NFD", result)
    result = "".join(c for c in result if not unicodedata.combining(c))

    # Remove punctuation (keep alphanumeric and spaces)
    result = re.sub(r"[^\w\s]", " ", result)

    # Collapse whitespace
    result = re.sub(r"\s+", " ", result)

    # Trim
    result = result.strip()

    return result


def extract_persons_from_record(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract person entities from a parsed InfoLobby record.

    Extracts from:
    - pasivo (datosPasivos) → single person with cargo
    - activos (datosActivos) → list of lobbyist names

    Args:
        record: Parsed record (ParsedAudiencia, ParsedViaje, or ParsedDonativo as dict)

    Returns:
        List of person dicts with name and normalized_name
    """
    persons = []

    # Extract pasivo (official/funcionario)
    pasivo = record.get("pasivo")
    if pasivo:
        if isinstance(pasivo, dict):
            nombre = pasivo.get("nombre", "")
        else:
            # ParsedPasivo dataclass
            nombre = getattr(pasivo, "nombre", "")

        if nombre:
            persons.append({
                "name": nombre,
                "normalized_name": normalize_for_matching(nombre),
                "cargo": pasivo.get("cargo") if isinstance(pasivo, dict) else getattr(pasivo, "cargo", None),
                "role": "pasivo",
            })

    # Extract activos (lobbyists)
    activos = record.get("activos", [])
    for nombre in activos:
        if nombre:
            persons.append({
                "name": nombre,
                "normalized_name": normalize_for_matching(nombre),
                "cargo": None,
                "role": "activo",
            })

    return persons


def extract_organisations_from_record(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract organisation entities from a parsed InfoLobby record.

    Extracts from:
    - representados (datosRepresentados) → organisation represented
    - donantes (datosDonantes) → donor organisation
    - financistas (datosFinancistas) → financing organisation

    Args:
        record: Parsed record as dict

    Returns:
        List of organisation dicts with name and normalized_name
    """
    orgs = []

    # representados
    representados = record.get("representados")
    if representados:
        orgs.append({
            "name": representados,
            "normalized_name": normalize_for_matching(representados),
            "tipo": "representado",
        })

    # donantes
    donantes = record.get("donantes")
    if donantes:
        orgs.append({
            "name": donantes,
            "normalized_name": normalize_for_matching(donantes),
            "tipo": "donante",
        })

    # financistas
    financistas = record.get("financistas")
    if financistas and financistas.lower() != "s/i":
        orgs.append({
            "name": financistas,
            "normalized_name": normalize_for_matching(financistas),
            "tipo": "financista",
        })

    return orgs


def lookup_person_by_name(
    conn,
    normalized_name: str,
    tenant_code: str = "CL"
) -> Optional[str]:
    """
    Look up existing Person by normalized name.

    Args:
        conn: Database connection
        normalized_name: Normalized name to search
        tenant_code: Tenant code (default "CL")

    Returns:
        Person ID if found, None otherwise
    """
    query = text("""
        SELECT id FROM "Person"
        WHERE "tenantCode" = :tenant_code
          AND "normalizedName" = :normalized_name
        LIMIT 1
    """)
    result = conn.execute(query, {
        "tenant_code": tenant_code,
        "normalized_name": normalized_name,
    })
    row = result.fetchone()
    return row[0] if row else None


def lookup_organisation_by_name(
    conn,
    normalized_name: str,
    tenant_code: str = "CL"
) -> Optional[str]:
    """
    Look up existing Organisation by normalized name.

    Args:
        conn: Database connection
        normalized_name: Normalized name to search
        tenant_code: Tenant code (default "CL")

    Returns:
        Organisation ID if found, None otherwise
    """
    query = text("""
        SELECT id FROM "Organisation"
        WHERE "tenantCode" = :tenant_code
          AND "normalizedName" = :normalized_name
        LIMIT 1
    """)
    result = conn.execute(query, {
        "tenant_code": tenant_code,
        "normalized_name": normalized_name,
    })
    row = result.fetchone()
    return row[0] if row else None


def merge_records(
    records: List[Dict[str, Any]],
    engine: Engine,
    tenant_code: str = "CL"
) -> MergeResult:
    """
    Merge parsed InfoLobby records against canonical database.

    For each record:
    1. Extract person and organisation entities
    2. Normalize names
    3. Look up existing entities in database
    4. Deduplicate within batch
    5. Return merged list with existing IDs or marked for creation

    Args:
        records: List of parsed records (as dicts)
        engine: SQLAlchemy engine for database lookups
        tenant_code: Tenant code (default "CL")

    Returns:
        MergeResult with merged entities and metrics
    """
    # Track unique entities by normalized name
    seen_persons: Dict[str, Dict[str, Any]] = {}
    seen_orgs: Dict[str, Dict[str, Any]] = {}

    duplicates_found = 0
    persons_existing = 0
    persons_new = 0
    orgs_existing = 0
    orgs_new = 0

    with engine.connect() as conn:
        for record in records:
            # Convert dataclass to dict if needed
            if hasattr(record, "__dataclass_fields__"):
                record_dict = _dataclass_to_dict(record)
            else:
                record_dict = record

            # Extract and merge persons
            for person in extract_persons_from_record(record_dict):
                norm_name = person["normalized_name"]
                if not norm_name:
                    continue

                if norm_name in seen_persons:
                    # Duplicate within batch - merge fields
                    duplicates_found += 1
                    _merge_person_fields(seen_persons[norm_name], person)
                else:
                    # Check database
                    existing_id = lookup_person_by_name(conn, norm_name, tenant_code)
                    person["existing_id"] = existing_id
                    person["tenant_code"] = tenant_code

                    if existing_id:
                        persons_existing += 1
                    else:
                        persons_new += 1

                    seen_persons[norm_name] = person

            # Extract and merge organisations
            for org in extract_organisations_from_record(record_dict):
                norm_name = org["normalized_name"]
                if not norm_name:
                    continue

                if norm_name in seen_orgs:
                    # Duplicate within batch
                    duplicates_found += 1
                    _merge_org_fields(seen_orgs[norm_name], org)
                else:
                    # Check database
                    existing_id = lookup_organisation_by_name(conn, norm_name, tenant_code)
                    org["existing_id"] = existing_id
                    org["tenant_code"] = tenant_code

                    if existing_id:
                        orgs_existing += 1
                    else:
                        orgs_new += 1

                    seen_orgs[norm_name] = org

    return MergeResult(
        persons=list(seen_persons.values()),
        organisations=list(seen_orgs.values()),
        duplicates_found=duplicates_found,
        merged_count=len(seen_persons) + len(seen_orgs),
        persons_existing=persons_existing,
        persons_new=persons_new,
        orgs_existing=orgs_existing,
        orgs_new=orgs_new,
    )


def merge_records_in_memory(
    records: List[Dict[str, Any]],
    existing_persons: Optional[Dict[str, str]] = None,
    existing_orgs: Optional[Dict[str, str]] = None,
    tenant_code: str = "CL"
) -> MergeResult:
    """
    Merge parsed records without database access (for testing).

    Args:
        records: List of parsed records (as dicts)
        existing_persons: Dict of normalized_name -> id for existing persons
        existing_orgs: Dict of normalized_name -> id for existing orgs
        tenant_code: Tenant code

    Returns:
        MergeResult with merged entities and metrics
    """
    existing_persons = existing_persons or {}
    existing_orgs = existing_orgs or {}

    seen_persons: Dict[str, Dict[str, Any]] = {}
    seen_orgs: Dict[str, Dict[str, Any]] = {}

    duplicates_found = 0
    persons_existing = 0
    persons_new = 0
    orgs_existing = 0
    orgs_new = 0

    for record in records:
        if hasattr(record, "__dataclass_fields__"):
            record_dict = _dataclass_to_dict(record)
        else:
            record_dict = record

        # Extract and merge persons
        for person in extract_persons_from_record(record_dict):
            norm_name = person["normalized_name"]
            if not norm_name:
                continue

            if norm_name in seen_persons:
                duplicates_found += 1
                _merge_person_fields(seen_persons[norm_name], person)
            else:
                existing_id = existing_persons.get(norm_name)
                person["existing_id"] = existing_id
                person["tenant_code"] = tenant_code

                if existing_id:
                    persons_existing += 1
                else:
                    persons_new += 1

                seen_persons[norm_name] = person

        # Extract and merge organisations
        for org in extract_organisations_from_record(record_dict):
            norm_name = org["normalized_name"]
            if not norm_name:
                continue

            if norm_name in seen_orgs:
                duplicates_found += 1
                _merge_org_fields(seen_orgs[norm_name], org)
            else:
                existing_id = existing_orgs.get(norm_name)
                org["existing_id"] = existing_id
                org["tenant_code"] = tenant_code

                if existing_id:
                    orgs_existing += 1
                else:
                    orgs_new += 1

                seen_orgs[norm_name] = org

    return MergeResult(
        persons=list(seen_persons.values()),
        organisations=list(seen_orgs.values()),
        duplicates_found=duplicates_found,
        merged_count=len(seen_persons) + len(seen_orgs),
        persons_existing=persons_existing,
        persons_new=persons_new,
        orgs_existing=orgs_existing,
        orgs_new=orgs_new,
    )


def _merge_person_fields(existing: Dict[str, Any], new: Dict[str, Any]) -> None:
    """Merge non-null fields from new into existing person."""
    if new.get("cargo") and not existing.get("cargo"):
        existing["cargo"] = new["cargo"]


def _merge_org_fields(existing: Dict[str, Any], new: Dict[str, Any]) -> None:
    """Merge non-null fields from new into existing org."""
    if new.get("tipo") and not existing.get("tipo"):
        existing["tipo"] = new["tipo"]


def _dataclass_to_dict(obj: Any) -> Dict[str, Any]:
    """Convert dataclass to dict, handling nested dataclasses."""
    if hasattr(obj, "__dataclass_fields__"):
        result = {}
        for field_name in obj.__dataclass_fields__:
            value = getattr(obj, field_name)
            if hasattr(value, "__dataclass_fields__"):
                result[field_name] = _dataclass_to_dict(value)
            elif isinstance(value, list):
                result[field_name] = [
                    _dataclass_to_dict(v) if hasattr(v, "__dataclass_fields__") else v
                    for v in value
                ]
            else:
                result[field_name] = value
        return result
    return obj
