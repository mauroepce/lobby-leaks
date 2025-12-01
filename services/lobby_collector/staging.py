"""
Staging layer helpers for reading from lobby_events_staging VIEW.

Provides utilities for reading normalized/derived data and normalizing
person names and Chilean RUTs for canonical entity matching.
"""

import re
from typing import Optional, List, Dict, Any
from sqlalchemy import text
from sqlalchemy.engine import Engine


def normalize_person_name(nombres: Optional[str], apellidos: Optional[str]) -> str:
    """
    Normalize person name for matching and deduplication.

    Converts to lowercase, removes extra whitespace, and concatenates.

    Args:
        nombres: First name(s) (e.g., "Juan Carlos")
        apellidos: Last name(s) (e.g., "Pérez García")

    Returns:
        Normalized full name (e.g., "juan carlos perez garcia")

    Examples:
        >>> normalize_person_name("Juan Carlos", "Pérez García")
        'juan carlos perez garcia'
        >>> normalize_person_name("  Mario  ", "  Desbordes  ")
        'mario desbordes'
        >>> normalize_person_name(None, "Pérez")
        'perez'
    """
    parts = []

    if nombres:
        # Lowercase and strip extra whitespace
        normalized = ' '.join(nombres.strip().lower().split())
        if normalized:
            parts.append(normalized)

    if apellidos:
        normalized = ' '.join(apellidos.strip().lower().split())
        if normalized:
            parts.append(normalized)

    return ' '.join(parts) if parts else ''


def validate_rut(rut: str) -> bool:
    """
    Validate Chilean RUT using módulo 11 algorithm.

    Args:
        rut: RUT string (e.g., "12345678-9" or "12.345.678-9")

    Returns:
        True if RUT is valid, False otherwise

    Examples:
        >>> validate_rut("12345678-5")
        True
        >>> validate_rut("12345678-0")
        False
    """
    # Remove dots and hyphens
    clean = rut.replace('.', '').replace('-', '').upper()

    if len(clean) < 2:
        return False

    # Split number and verification digit
    number = clean[:-1]
    verif = clean[-1]

    # Number part must be digits
    if not number.isdigit():
        return False

    # Calculate expected verification digit using módulo 11
    reversed_digits = [int(d) for d in reversed(number)]
    factors = [2, 3, 4, 5, 6, 7]

    total = sum(
        digit * factors[i % len(factors)]
        for i, digit in enumerate(reversed_digits)
    )

    remainder = total % 11
    expected_verif = 11 - remainder

    # Convert to character
    if expected_verif == 11:
        expected_char = '0'
    elif expected_verif == 10:
        expected_char = 'K'
    else:
        expected_char = str(expected_verif)

    return verif == expected_char


def normalize_rut(rut: Optional[str]) -> Optional[str]:
    """
    Normalize Chilean RUT to canonical format without dots or hyphens.

    Validates RUT using módulo 11 algorithm. Returns None if invalid.

    Args:
        rut: RUT string (e.g., "12.345.678-9" or "12345678-9")

    Returns:
        Normalized RUT (e.g., "123456789") or None if invalid

    Examples:
        >>> normalize_rut("12.345.678-5")
        '123456785'
        >>> normalize_rut("12345678-5")
        '123456785'
        >>> normalize_rut("invalid")
        None
    """
    if not rut:
        return None

    # Remove dots, hyphens, and whitespace
    clean = rut.replace('.', '').replace('-', '').replace(' ', '').upper()

    if not clean:
        return None

    # Validate before returning
    if not validate_rut(clean):
        return None

    return clean


def read_staging_rows(
    engine: Engine,
    kind: Optional[str] = None,
    tenant_code: str = "CL",
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Read rows from lobby_events_staging VIEW.

    Args:
        engine: SQLAlchemy engine
        kind: Filter by event kind ('audiencia', 'viaje', 'donativo'). None = all.
        tenant_code: Tenant filter (default: 'CL')
        limit: Maximum rows to return (default: no limit)

    Returns:
        List of row dictionaries with all VIEW columns

    Example:
        >>> engine = create_engine("postgresql://...")
        >>> rows = read_staging_rows(engine, kind="audiencia", limit=100)
        >>> for row in rows:
        ...     print(row["nombresCompletos"], row["institucion"])
    """
    query = """
        SELECT
            id,
            "externalId",
            "tenantCode",
            kind,
            nombres,
            apellidos,
            "nombresCompletos",
            cargo,
            fecha,
            year,
            month,
            institucion,
            destino,
            monto,
            "rawDataHash",
            "rawDataSize",
            "createdAt",
            "updatedAt"
        FROM lobby_events_staging
        WHERE "tenantCode" = :tenant_code
    """

    params = {"tenant_code": tenant_code}

    if kind:
        query += " AND kind = :kind"
        params["kind"] = kind

    query += " ORDER BY fecha DESC NULLS LAST"

    if limit:
        query += f" LIMIT {limit}"

    with engine.connect() as conn:
        result = conn.execute(text(query), params)
        rows = result.fetchall()

    # Convert to list of dicts
    return [dict(row._mapping) for row in rows]


def extract_rut_from_raw(raw_data: Dict[str, Any]) -> Optional[str]:
    """
    Extract and normalize RUT from raw JSON data.

    Searches common RUT field names in the raw data structure.

    Args:
        raw_data: Raw JSONB data from LobbyEventRaw

    Returns:
        Normalized RUT or None if not found/invalid

    Examples:
        >>> extract_rut_from_raw({"rut": "12.345.678-5"})
        '123456785'
        >>> extract_rut_from_raw({"rut_sujeto": "12345678-5"})
        '123456785'
    """
    # Common RUT field names in Chilean lobby data
    rut_fields = [
        "rut",
        "rut_sujeto",
        "rut_pasivo",
        "rut_activo",
        "run",
        "identificacion"
    ]

    for field in rut_fields:
        if field in raw_data:
            value = raw_data[field]
            if isinstance(value, str):
                normalized = normalize_rut(value)
                if normalized:
                    return normalized

    return None
