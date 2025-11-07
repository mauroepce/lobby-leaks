"""
Field derivation helpers for lobby raw events.

Extracts minimal derived fields (externalId, fecha, monto, etc.) from raw JSON
records with best-effort fallbacks and robust error handling.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional, Dict


def derive_external_id(record: Dict[str, Any], kind: str) -> str:
    """
    Derive a unique external ID for the record.

    Since the Ley de Lobby API doesn't provide ID fields, we generate a
    deterministic ID based on kind + key fields (nombres, apellidos, fecha).

    Args:
        record: Raw JSON record from API
        kind: Event type ('audiencia', 'viaje', 'donativo')

    Returns:
        External ID string (e.g., "audiencia:mario_marcel_2025-01-15")

    Raises:
        ValueError: If required fields are missing
    """
    import hashlib

    # Try explicit ID fields first (if API provides them in future)
    record_id = record.get("id") or record.get("ID") or record.get("folio")

    if record_id is not None:
        return f"{kind}:{record_id}"

    # Fallback: generate deterministic ID from key fields
    nombres = record.get("nombres", "").strip().lower()
    apellidos = record.get("apellidos", "").strip().lower()

    # Get date field based on kind
    if kind == "audiencia":
        fecha_str = record.get("fecha_inicio", "")
    elif kind == "viaje":
        fecha_str = record.get("fecha_inicio", "")
    elif kind == "donativo":
        fecha_str = record.get("fecha", "")
    else:
        fecha_str = ""

    # Extract date part (yyyy-mm-dd) from datetime string
    fecha = fecha_str.split(" ")[0] if fecha_str else ""

    if not (nombres and apellidos and fecha):
        # Last resort: hash the entire record
        record_json = str(sorted(record.items()))
        record_hash = hashlib.sha256(record_json.encode()).hexdigest()[:12]
        return f"{kind}:hash_{record_hash}"

    # Create human-readable ID
    external_id = f"{kind}:{nombres}_{apellidos}_{fecha}".replace(" ", "_")
    return external_id


def derive_fecha(record: Dict[str, Any], kind: str) -> Optional[datetime]:
    """
    Derive fecha (date) from record with best-effort fallbacks.

    Args:
        record: Raw JSON record from API
        kind: Event type ('audiencia', 'viaje', 'donativo')

    Returns:
        Datetime object or None if not found/parseable
    """
    # Field name mapping by kind
    fecha_fields = {
        "audiencia": ["fecha_inicio", "fecha", "created_at"],
        "viaje": ["fecha_inicio", "fecha_salida", "fecha", "created_at"],
        "donativo": ["fecha", "fecha_donacion", "created_at"],
    }

    fields_to_try = fecha_fields.get(kind, ["fecha", "created_at"])

    for field in fields_to_try:
        fecha_str = record.get(field)
        if fecha_str:
            try:
                # Try ISO8601 format first
                return datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                try:
                    # Try common date format
                    return datetime.strptime(fecha_str, "%Y-%m-%d")
                except (ValueError, AttributeError):
                    continue

    return None


def derive_monto(record: Dict[str, Any], kind: str) -> Optional[Decimal]:
    """
    Derive monto (amount) from record.

    Args:
        record: Raw JSON record from API
        kind: Event type (mainly relevant for 'donativo')

    Returns:
        Decimal amount or None if not found/parseable
    """
    # Monto is mainly relevant for donativos
    if kind != "donativo":
        return None

    monto_fields = ["monto", "monto_donacion", "valor", "amount"]

    for field in monto_fields:
        monto_value = record.get(field)
        if monto_value is not None:
            try:
                return Decimal(str(monto_value))
            except (InvalidOperation, ValueError):
                continue

    return None


def derive_institucion(record: Dict[str, Any], kind: str) -> Optional[str]:
    """
    Derive institucion (institution) from record.

    Args:
        record: Raw JSON record from API
        kind: Event type

    Returns:
        Institution name or None if not found
    """
    institucion_fields = {
        "audiencia": ["institucion", "sujeto_pasivo", "nombre_institucion"],
        "viaje": ["institucion_destino", "institucion", "organizador"],
        "donativo": ["institucion_donante", "donante", "institucion"],
    }

    fields_to_try = institucion_fields.get(kind, ["institucion"])

    for field in fields_to_try:
        value = record.get(field)
        if value:
            # Handle nested object (e.g., {nombre: "...", codigo: "..."})
            if isinstance(value, dict) and "nombre" in value:
                nombre = value["nombre"]
                if isinstance(nombre, str):
                    return nombre.strip()
            # Handle direct string value
            elif isinstance(value, str):
                return value.strip()

    return None


def derive_destino(record: Dict[str, Any], kind: str) -> Optional[str]:
    """
    Derive destino (destination) from record.

    Args:
        record: Raw JSON record from API
        kind: Event type (mainly relevant for 'viaje')

    Returns:
        Destination string or None if not found
    """
    # Destino is mainly relevant for viajes
    if kind != "viaje":
        return None

    destino_fields = ["destino", "ciudad_destino", "pais_destino", "lugar_destino"]

    for field in destino_fields:
        value = record.get(field)
        if value and isinstance(value, str):
            return value.strip()

    return None
