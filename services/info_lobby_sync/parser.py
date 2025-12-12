"""
Parser for InfoLobby SPARQL results.

Converts raw SPARQL bindings into typed Python dictionaries with:
- Date/datetime parsing
- RUT validation and normalization
- Name parsing from denormalized strings
- Field extraction from compound values
"""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional

# RUT pattern: 12.345.678-9 or 12345678-9
RUT_PATTERN = re.compile(r"(\d{1,2}\.?\d{3}\.?\d{3})-?([\dkK])")

# Name/cargo pattern in datosPasivos: "Nombre: Cargo: Institución"
PASIVO_PATTERN = re.compile(r"^([^:]+):\s*([^:]+):\s*(.+)$")

# Date patterns
DATE_PATTERNS = [
    ("%Y-%m-%dT%H:%M:%S.%f", True),  # 2025-04-03T11:16:16.82
    ("%Y-%m-%dT%H:%M:%S", True),     # 2025-04-03T11:16:16
    ("%Y-%m-%d", False),              # 2025-04-03
]


@dataclass
class ParsedPasivo:
    """Parsed data from datosPasivos field."""
    nombre: str
    cargo: str
    institucion: str


@dataclass
class ParsedAudiencia:
    """Typed audiencia record."""
    uri: str
    codigo_uri: str
    identificador_temporal: Optional[int]
    fecha_evento: Optional[datetime]
    fecha_actualizacion: Optional[datetime]
    pasivo: Optional[ParsedPasivo]
    activos: List[str]
    representados: Optional[str]
    materias: Optional[str]
    descripcion: Optional[str]
    observaciones: Optional[str]
    tipo: Optional[str]
    checksum: str


@dataclass
class ParsedViaje:
    """Typed viaje record."""
    uri: str
    codigo_uri: str
    identificador_temporal: Optional[int]
    fecha_evento: Optional[date]
    fecha_actualizacion: Optional[datetime]
    descripcion: Optional[str]
    razones: Optional[str]
    objetos: Optional[str]
    financistas: Optional[str]
    costo: Optional[int]
    checksum: str


@dataclass
class ParsedDonativo:
    """Typed donativo record."""
    uri: str
    codigo_uri: str
    identificador_temporal: Optional[int]
    fecha_evento: Optional[date]
    fecha_actualizacion: Optional[datetime]
    descripcion: Optional[str]
    ocasion: Optional[str]
    donantes: Optional[str]
    checksum: str


def parse_date(value: Optional[str]) -> Optional[date]:
    """Parse date string into date object."""
    if not value:
        return None

    for pattern, is_datetime in DATE_PATTERNS:
        try:
            parsed = datetime.strptime(value.strip(), pattern)
            return parsed.date()
        except ValueError:
            continue

    return None


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse datetime string into datetime object."""
    if not value:
        return None

    for pattern, _ in DATE_PATTERNS:
        try:
            return datetime.strptime(value.strip(), pattern)
        except ValueError:
            continue

    return None


def parse_int(value: Optional[str]) -> Optional[int]:
    """Parse integer from string."""
    if not value:
        return None

    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def normalize_rut(rut: str) -> Optional[str]:
    """
    Normalize Chilean RUT to standard format.

    Args:
        rut: RUT in any format (12.345.678-9, 123456789, etc.)

    Returns:
        Normalized RUT (12345678-9) or None if invalid
    """
    match = RUT_PATTERN.search(rut)
    if not match:
        return None

    number = match.group(1).replace(".", "")
    verifier = match.group(2).upper()

    return f"{number}-{verifier}"


def parse_pasivo(datos_pasivos: Optional[str]) -> Optional[ParsedPasivo]:
    """
    Parse datosPasivos field into structured data.

    Format: "Nombre Apellido: Cargo: Institución"
    Example: "Carolina Tohá Morales: Ministro: SUBSECRETARÍA DEL INTERIOR"
    """
    if not datos_pasivos:
        return None

    match = PASIVO_PATTERN.match(datos_pasivos.strip())
    if not match:
        return ParsedPasivo(
            nombre=datos_pasivos.strip(),
            cargo="",
            institucion=""
        )

    return ParsedPasivo(
        nombre=match.group(1).strip(),
        cargo=match.group(2).strip(),
        institucion=match.group(3).strip()
    )


def parse_activos(datos_activos: Optional[str]) -> List[str]:
    """
    Parse datosActivos field into list of names.

    Format: "Nombre1 - Nombre2 - Nombre3"
    """
    if not datos_activos:
        return []

    names = [name.strip() for name in datos_activos.split(" - ")]
    return [name for name in names if name]


def compute_checksum(record: Dict[str, Any]) -> str:
    """Compute SHA256 checksum of a record for incremental sync detection."""
    serialized = json.dumps(record, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def parse_audiencia(record: Dict[str, Any]) -> ParsedAudiencia:
    """Parse raw audiencia record into typed dataclass."""
    return ParsedAudiencia(
        uri=record.get("uri", ""),
        codigo_uri=record.get("codigoURI", ""),
        identificador_temporal=parse_int(record.get("identificadorTemporal")),
        fecha_evento=parse_datetime(record.get("fechaEvento")),
        fecha_actualizacion=parse_datetime(record.get("fechaActualizacion")),
        pasivo=parse_pasivo(record.get("datosPasivos")),
        activos=parse_activos(record.get("datosActivos")),
        representados=record.get("datosRepresentados"),
        materias=record.get("datosMaterias"),
        descripcion=record.get("descripcion"),
        observaciones=record.get("observaciones"),
        tipo=record.get("esDeTipo"),
        checksum=compute_checksum(record),
    )


def parse_viaje(record: Dict[str, Any]) -> ParsedViaje:
    """Parse raw viaje record into typed dataclass."""
    return ParsedViaje(
        uri=record.get("uri", ""),
        codigo_uri=record.get("codigoURI", ""),
        identificador_temporal=parse_int(record.get("identificadorTemporal")),
        fecha_evento=parse_date(record.get("fechaEvento")),
        fecha_actualizacion=parse_datetime(record.get("fechaActualizacion")),
        descripcion=record.get("descripcion"),
        razones=record.get("datosRazones"),
        objetos=record.get("datosObjetos"),
        financistas=record.get("datosFinancistas"),
        costo=parse_int(record.get("costo")),
        checksum=compute_checksum(record),
    )


def parse_donativo(record: Dict[str, Any]) -> ParsedDonativo:
    """Parse raw donativo record into typed dataclass."""
    return ParsedDonativo(
        uri=record.get("uri", ""),
        codigo_uri=record.get("codigoURI", ""),
        identificador_temporal=parse_int(record.get("identificadorTemporal")),
        fecha_evento=parse_date(record.get("fechaEvento")),
        fecha_actualizacion=parse_datetime(record.get("fechaActualizacion")),
        descripcion=record.get("descripcion"),
        ocasion=record.get("ocasion"),
        donantes=record.get("datosDonantes"),
        checksum=compute_checksum(record),
    )


def parse_all_audiencias(records: List[Dict[str, Any]]) -> List[ParsedAudiencia]:
    """Parse list of raw audiencia records."""
    return [parse_audiencia(r) for r in records]


def parse_all_viajes(records: List[Dict[str, Any]]) -> List[ParsedViaje]:
    """Parse list of raw viaje records."""
    return [parse_viaje(r) for r in records]


def parse_all_donativos(records: List[Dict[str, Any]]) -> List[ParsedDonativo]:
    """Parse list of raw donativo records."""
    return [parse_donativo(r) for r in records]
