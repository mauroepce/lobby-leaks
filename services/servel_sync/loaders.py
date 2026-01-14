"""
Loaders for canonical entity lookups from PostgreSQL.

Loads Person and Organisation entities and builds dictionaries
for use with merge_donations().

This module:
- Loads entities once from DB
- Builds normalized lookup dictionaries
- Validates RUTs before including in lookup
- Preserves name collisions (does NOT resolve them)
- Does NOT perform any matching logic
"""

from typing import Dict, List, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Connection

from services._template.helpers.rut import validate_rut


def load_person_lookups(
    conn: Connection,
    tenant_code: str,
) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    """
    Load Person entities into lookup dictionaries.

    Args:
        conn: Active database connection
        tenant_code: Tenant code for filtering (e.g., "CL")

    Returns:
        Tuple of:
        - persons_by_rut: Dict mapping RUT -> Person.id
        - persons_by_name: Dict mapping normalizedName -> List[Person.id]

    Notes:
        - Only valid RUTs are included in persons_by_rut
        - Name collisions are preserved as lists (not resolved)
        - Uses normalizedName from DB (no re-normalization)

    Example:
        >>> with engine.connect() as conn:
        ...     by_rut, by_name = load_person_lookups(conn, "CL")
        >>> by_rut["12345678-9"]
        'uuid-person-1'
        >>> by_name["juan perez"]
        ['uuid-person-1']
    """
    query = text("""
        SELECT id, rut, "normalizedName"
        FROM "Person"
        WHERE "tenantCode" = :tenant_code
    """)

    result = conn.execute(query, {"tenant_code": tenant_code})

    persons_by_rut: Dict[str, str] = {}
    persons_by_name: Dict[str, List[str]] = {}

    for row in result:
        # Extract fields from row
        if hasattr(row, '_mapping'):
            person_id = row._mapping['id']
            rut = row._mapping['rut']
            normalized_name = row._mapping['normalizedName']
        else:
            person_id = row[0]
            rut = row[1]
            normalized_name = row[2]

        # Add to RUT lookup (only if valid)
        if rut and validate_rut(rut):
            persons_by_rut[rut] = person_id

        # Add to name lookup (preserve collisions)
        if normalized_name:
            if normalized_name not in persons_by_name:
                persons_by_name[normalized_name] = []
            persons_by_name[normalized_name].append(person_id)

    return persons_by_rut, persons_by_name


def load_org_lookups(
    conn: Connection,
    tenant_code: str,
) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    """
    Load Organisation entities into lookup dictionaries.

    Args:
        conn: Active database connection
        tenant_code: Tenant code for filtering (e.g., "CL")

    Returns:
        Tuple of:
        - orgs_by_rut: Dict mapping RUT -> Organisation.id
        - orgs_by_name: Dict mapping normalizedName -> List[Organisation.id]

    Notes:
        - Only valid RUTs are included in orgs_by_rut
        - Name collisions are preserved as lists (not resolved)
        - Uses normalizedName from DB (no re-normalization)

    Example:
        >>> with engine.connect() as conn:
        ...     by_rut, by_name = load_org_lookups(conn, "CL")
        >>> by_rut["76543210-K"]
        'uuid-org-1'
        >>> by_name["empresa xyz"]
        ['uuid-org-1']
    """
    query = text("""
        SELECT id, rut, "normalizedName"
        FROM "Organisation"
        WHERE "tenantCode" = :tenant_code
    """)

    result = conn.execute(query, {"tenant_code": tenant_code})

    orgs_by_rut: Dict[str, str] = {}
    orgs_by_name: Dict[str, List[str]] = {}

    for row in result:
        # Extract fields from row
        if hasattr(row, '_mapping'):
            org_id = row._mapping['id']
            rut = row._mapping['rut']
            normalized_name = row._mapping['normalizedName']
        else:
            org_id = row[0]
            rut = row[1]
            normalized_name = row[2]

        # Add to RUT lookup (only if valid)
        if rut and validate_rut(rut):
            orgs_by_rut[rut] = org_id

        # Add to name lookup (preserve collisions)
        if normalized_name:
            if normalized_name not in orgs_by_name:
                orgs_by_name[normalized_name] = []
            orgs_by_name[normalized_name].append(org_id)

    return orgs_by_rut, orgs_by_name
