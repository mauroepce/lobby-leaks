"""
Orchestrator for SERVEL donation sync pipeline.

Coordinates the complete flow:
1. Fetch raw data from source (file or URL)
2. Parse into ParsedDonation objects
3. Load canonical entity lookups from DB
4. Execute deterministic merge
5. Return DonationMergeResult

This module:
- Controls connection lifecycle
- Coordinates modules without business logic
- Does NOT perform matching (delegated to merge)
- Does NOT modify any data
"""

from pathlib import Path
from typing import Union

from sqlalchemy.engine import Engine

from .fetcher import fetch
from .parser import parse_all_donations
from .loaders import load_person_lookups, load_org_lookups
from .merge import merge_donations, DonationMergeResult


def run_servel_donation_sync(
    source: Union[str, Path],
    engine: Engine,
    tenant_code: str,
) -> DonationMergeResult:
    """
    Execute complete SERVEL donation sync pipeline.

    Pipeline steps (fixed order):
    1. Fetch raw records from source
    2. Parse records into ParsedDonation objects
    3. Load Person lookups from DB
    4. Load Organisation lookups from DB
    5. Execute merge against canonical entities
    6. Return merge result

    Args:
        source: File path or URL to SERVEL data (CSV/Excel)
        engine: SQLAlchemy database engine
        tenant_code: Tenant code for filtering entities (e.g., "CL")

    Returns:
        DonationMergeResult with merged donations and metrics

    Raises:
        FetchError: If source cannot be loaded
        ParseError: If records cannot be parsed

    Example:
        >>> from sqlalchemy import create_engine
        >>> from services.servel_sync.orchestrator import run_servel_donation_sync
        >>>
        >>> engine = create_engine("postgresql://...")
        >>> result = run_servel_donation_sync(
        ...     "data/servel/donations_2021.csv",
        ...     engine,
        ...     "CL",
        ... )
        >>> print(f"Total: {result.total_records}")
        >>> print(f"Matched by RUT: {result.donors_matched_by_rut}")
    """
    # Step 1: Fetch raw data
    raw_records = fetch(str(source))

    # Step 2: Parse into typed donations
    parsed_donations, parse_errors = parse_all_donations(raw_records, skip_errors=True)

    # Step 3-4: Load lookups within connection context
    with engine.connect() as conn:
        persons_by_rut, persons_by_name = load_person_lookups(conn, tenant_code)
        orgs_by_rut, orgs_by_name = load_org_lookups(conn, tenant_code)

    # Step 5: Execute merge (pure function)
    result = merge_donations(
        parsed_donations,
        persons_by_rut,
        persons_by_name,
        orgs_by_rut,
        orgs_by_name,
    )

    return result
