"""
Parser for SERVEL campaign financing datasets.

Converts raw records (from CSV/Excel) into typed ParsedDonation objects with:
- Name normalization (for matching)
- RUT validation and normalization
- Date parsing
- Amount normalization (to int CLP)
- SHA256 checksum for change detection

This module handles column mapping variations from different SERVEL datasets.
"""

import hashlib
import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from services._template.helpers.rut import normalize_rut, validate_rut

logger = logging.getLogger(__name__)


# Column aliases for flexible parsing
# Maps canonical field name to list of possible column names in source data
COLUMN_ALIASES: Dict[str, List[str]] = {
    "donor_name": [
        "NOMBRE_DONANTE", "DONANTE", "NOMBRE_APORTANTE", "APORTANTE",
        "nombre_donante", "donante", "nombre_aportante", "aportante",
    ],
    "donor_rut": [
        "RUT_DONANTE", "RUT_APORTANTE", "RUT DONANTE", "RUT APORTANTE",
        "rut_donante", "rut_aportante",
    ],
    "candidate_name": [
        "NOMBRE_CANDIDATO", "CANDIDATO", "NOMBRE_BENEFICIARIO", "BENEFICIARIO",
        "nombre_candidato", "candidato", "nombre_beneficiario", "beneficiario",
    ],
    "candidate_rut": [
        "RUT_CANDIDATO", "RUT_BENEFICIARIO", "RUT CANDIDATO", "RUT BENEFICIARIO",
        "rut_candidato", "rut_beneficiario",
    ],
    "amount_clp": [
        "MONTO", "MONTO_APORTE", "MONTO APORTE", "VALOR", "MONTO_CLP",
        "monto", "monto_aporte", "valor", "monto_clp",
    ],
    "donation_date": [
        "FECHA", "FECHA_APORTE", "FECHA APORTE", "FECHA_DONACION",
        "fecha", "fecha_aporte", "fecha_donacion",
    ],
    "campaign_year": [
        "AÑO_ELECCION", "ANIO_ELECCION", "AÑO", "ANIO", "PERIODO",
        "año_eleccion", "anio_eleccion", "año", "anio", "periodo",
    ],
    "election_type": [
        "TIPO_ELECCION", "TIPO ELECCION", "ELECCION", "TIPO",
        "tipo_eleccion", "eleccion", "tipo",
    ],
    "candidate_party": [
        "PARTIDO", "PARTIDO_POLITICO", "PARTIDO POLITICO",
        "partido", "partido_politico",
    ],
    "donor_type": [
        "TIPO_DONANTE", "TIPO_APORTANTE", "TIPO DONANTE", "TIPO APORTANTE",
        "tipo_donante", "tipo_aportante",
    ],
    "region": [
        "REGION", "REGIÓN", "CIRCUNSCRIPCION", "CIRCUNSCRIPCIÓN",
        "region", "región", "circunscripcion", "circunscripción",
    ],
}


@dataclass
class ParsedDonation:
    """
    Typed donation record from SERVEL data.

    Contains both raw and normalized versions of key fields
    for matching and display purposes.
    """
    # Core fields (required for valid record)
    donor_name: str
    donor_name_normalized: str
    candidate_name: str
    candidate_name_normalized: str
    amount_clp: int
    campaign_year: int

    # Optional RUT fields
    donor_rut: Optional[str] = None
    donor_rut_valid: bool = False
    candidate_rut: Optional[str] = None
    candidate_rut_valid: bool = False

    # Optional date
    donation_date: Optional[date] = None

    # Optional metadata fields
    election_type: Optional[str] = None
    candidate_party: Optional[str] = None
    donor_type: Optional[str] = None
    region: Optional[str] = None

    # Change detection
    checksum: str = ""


class ParseError(Exception):
    """Error during parsing of a record."""
    pass


class MissingRequiredFieldError(ParseError):
    """Required field is missing or empty."""
    pass


def normalize_name(name: str) -> str:
    """
    Normalize name for matching.

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
    """
    if not name:
        return ""

    # Lowercase
    result = name.lower()

    # Remove accents via NFD decomposition
    result = unicodedata.normalize("NFD", result)
    result = "".join(c for c in result if unicodedata.category(c) != "Mn")

    # Remove punctuation (keep alphanumeric and spaces)
    result = re.sub(r"[^\w\s]", " ", result)

    # Collapse whitespace and trim
    result = " ".join(result.split())

    return result


def _find_column(
    record: Dict[str, Any],
    field_name: str,
    required: bool = False,
) -> Optional[str]:
    """
    Find the value for a field using column aliases.

    Args:
        record: Raw record dictionary
        field_name: Canonical field name
        required: If True, raise error when not found

    Returns:
        Field value or None if not found

    Raises:
        MissingRequiredFieldError: If required and not found
    """
    aliases = COLUMN_ALIASES.get(field_name, [field_name])

    for alias in aliases:
        if alias in record:
            value = record[alias]
            # Return None for empty/whitespace strings
            if value is None:
                return None
            if isinstance(value, str) and not value.strip():
                return None
            return str(value).strip() if value is not None else None

    if required:
        raise MissingRequiredFieldError(
            f"Required field '{field_name}' not found. "
            f"Tried columns: {aliases}"
        )

    return None


def _parse_date(value: Optional[str]) -> Optional[date]:
    """
    Parse date string into date object.

    Supports multiple formats commonly found in SERVEL data.
    """
    if not value:
        return None

    # Clean the value
    value = str(value).strip()

    # Common date formats
    formats = [
        "%Y-%m-%d",          # 2021-03-15
        "%d-%m-%Y",          # 15-03-2021
        "%d/%m/%Y",          # 15/03/2021
        "%Y/%m/%d",          # 2021/03/15
        "%d.%m.%Y",          # 15.03.2021
        "%Y-%m-%dT%H:%M:%S", # ISO with time
        "%d-%m-%y",          # 15-03-21
        "%d/%m/%y",          # 15/03/21
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    # Try parsing just a year
    if re.match(r"^\d{4}$", value):
        return date(int(value), 1, 1)

    logger.debug(f"Could not parse date: {value}")
    return None


def _parse_amount(value: Optional[str]) -> Optional[int]:
    """
    Parse amount string into integer CLP.

    Handles:
    - Thousand separators (. or ,)
    - Currency symbols ($)
    - Decimal values (rounded)
    """
    if not value:
        return None

    # Convert to string and clean
    value = str(value).strip()

    # Remove currency symbols and spaces
    value = re.sub(r"[$\s]", "", value)

    # Handle Chilean format: 1.234.567 (dots as thousand sep)
    # vs international: 1,234,567 (commas as thousand sep)

    # If we have both dots and commas, assume dots are thousand sep
    if "." in value and "," in value:
        # Chilean: 1.234,56 → 1234.56
        value = value.replace(".", "").replace(",", ".")
    elif "." in value:
        # Could be decimal or thousand sep
        # If more than one dot, they're thousand separators
        if value.count(".") > 1:
            value = value.replace(".", "")
        # If dot is followed by exactly 3 digits at end, it's a thousand sep
        elif re.match(r".*\.\d{3}$", value):
            value = value.replace(".", "")
        # Otherwise assume it's decimal
    elif "," in value:
        # Similar logic for commas
        if value.count(",") > 1:
            value = value.replace(",", "")
        elif re.match(r".*,\d{3}$", value):
            value = value.replace(",", "")
        else:
            value = value.replace(",", ".")

    try:
        # Parse as float and round to int
        return int(round(float(value)))
    except ValueError:
        logger.debug(f"Could not parse amount: {value}")
        return None


def _parse_year(value: Optional[str]) -> Optional[int]:
    """Parse campaign year from string."""
    if not value:
        return None

    value = str(value).strip()

    # Extract 4-digit year
    match = re.search(r"(19|20)\d{2}", value)
    if match:
        return int(match.group())

    # Try direct conversion
    try:
        year = int(float(value))
        if 1990 <= year <= 2100:
            return year
    except ValueError:
        pass

    logger.debug(f"Could not parse year: {value}")
    return None


def _compute_checksum(donation: ParsedDonation) -> str:
    """
    Compute SHA256 checksum for change detection.

    Based on core identifying fields only.
    """
    data = {
        "donor_name": donation.donor_name_normalized,
        "donor_rut": donation.donor_rut,
        "candidate_name": donation.candidate_name_normalized,
        "candidate_rut": donation.candidate_rut,
        "amount_clp": donation.amount_clp,
        "donation_date": donation.donation_date.isoformat() if donation.donation_date else None,
        "campaign_year": donation.campaign_year,
    }

    serialized = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def parse_donation(record: Dict[str, Any]) -> ParsedDonation:
    """
    Parse a single raw record into a ParsedDonation.

    Args:
        record: Dictionary from CSV/Excel row

    Returns:
        ParsedDonation with normalized fields

    Raises:
        MissingRequiredFieldError: If required fields are missing
        ParseError: If record cannot be parsed

    Example:
        >>> record = {
        ...     "NOMBRE_DONANTE": "JUAN PÉREZ",
        ...     "NOMBRE_CANDIDATO": "MARÍA GARCÍA",
        ...     "MONTO": "1.000.000",
        ...     "AÑO_ELECCION": "2021"
        ... }
        >>> donation = parse_donation(record)
        >>> print(donation.donor_name_normalized)
        'juan perez'
    """
    # Required fields
    donor_name = _find_column(record, "donor_name", required=True)
    candidate_name = _find_column(record, "candidate_name", required=True)
    amount_str = _find_column(record, "amount_clp", required=True)
    year_str = _find_column(record, "campaign_year", required=True)

    # Parse required values
    amount = _parse_amount(amount_str)
    if amount is None:
        raise ParseError(f"Invalid amount: {amount_str}")

    year = _parse_year(year_str)
    if year is None:
        raise ParseError(f"Invalid campaign year: {year_str}")

    # Optional fields
    donor_rut_raw = _find_column(record, "donor_rut")
    candidate_rut_raw = _find_column(record, "candidate_rut")
    date_str = _find_column(record, "donation_date")
    election_type = _find_column(record, "election_type")
    candidate_party = _find_column(record, "candidate_party")
    donor_type = _find_column(record, "donor_type")
    region = _find_column(record, "region")

    # Normalize RUTs
    donor_rut = normalize_rut(donor_rut_raw) if donor_rut_raw else None
    donor_rut_valid = validate_rut(donor_rut_raw) if donor_rut_raw else False

    candidate_rut = normalize_rut(candidate_rut_raw) if candidate_rut_raw else None
    candidate_rut_valid = validate_rut(candidate_rut_raw) if candidate_rut_raw else False

    # Create donation object
    donation = ParsedDonation(
        donor_name=donor_name,
        donor_name_normalized=normalize_name(donor_name),
        candidate_name=candidate_name,
        candidate_name_normalized=normalize_name(candidate_name),
        amount_clp=amount,
        campaign_year=year,
        donor_rut=donor_rut,
        donor_rut_valid=donor_rut_valid,
        candidate_rut=candidate_rut,
        candidate_rut_valid=candidate_rut_valid,
        donation_date=_parse_date(date_str),
        election_type=election_type,
        candidate_party=candidate_party,
        donor_type=donor_type,
        region=region,
    )

    # Compute checksum
    donation.checksum = _compute_checksum(donation)

    return donation


def parse_all_donations(
    records: List[Dict[str, Any]],
    skip_errors: bool = True,
) -> Tuple[List[ParsedDonation], List[Dict[str, Any]]]:
    """
    Parse multiple records into ParsedDonation objects.

    Args:
        records: List of raw record dictionaries
        skip_errors: If True, log errors and continue; if False, raise

    Returns:
        Tuple of (successful_donations, error_records)

    Example:
        >>> records = fetch_from_file("donations.csv")
        >>> donations, errors = parse_all_donations(records)
        >>> print(f"Parsed {len(donations)}, errors: {len(errors)}")
    """
    donations: List[ParsedDonation] = []
    errors: List[Dict[str, Any]] = []

    for i, record in enumerate(records):
        try:
            donation = parse_donation(record)
            donations.append(donation)
        except (ParseError, MissingRequiredFieldError) as e:
            error_info = {
                "row_index": i,
                "error": str(e),
                "record": record,
            }
            errors.append(error_info)

            if skip_errors:
                logger.warning(f"Row {i}: {e}")
            else:
                raise

    logger.info(
        f"Parsed {len(donations)} donations, {len(errors)} errors"
    )

    return donations, errors
