"""
Data ingestion logic with pagination and temporal windows.

Handles iterating through paginated API responses and calculating
time windows for incremental updates.
"""

import logging
from datetime import datetime, timedelta
from typing import AsyncIterator, Any, Optional, Dict, List

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from .client import fetch_page
from .settings import settings
from .persistence import upsert_raw_event
from .staging import read_staging_rows
from .canonical_mapper import map_staging_row
from .canonical_persistence import upsert_canonical


logger = logging.getLogger(__name__)


def resolve_window(
    now: Optional[datetime] = None,
    days: Optional[int] = None
) -> tuple:
    """
    Calculate time window for data ingestion.

    Args:
        now: Current datetime (defaults to datetime.now())
        days: Number of days to look back (defaults to DEFAULT_SINCE_DAYS from settings)

    Returns:
        Tuple of (since, until) datetimes

    Example:
        >>> now = datetime(2025, 10, 8, 12, 0)
        >>> since, until = resolve_window(now, days=7)
        >>> print(since)
        datetime(2025, 10, 1, 12, 0)
        >>> print(until)
        datetime(2025, 10, 8, 12, 0)
    """
    config = settings()
    now = now or datetime.now()
    days = days if days is not None else config.default_since_days

    since = now - timedelta(days=days)
    until = now

    logger.debug(
        f"Resolved time window: since={since.isoformat()}, until={until.isoformat()}, days={days}"
    )

    return (since, until)


async def fetch_since(
    since: datetime,
    until: Optional[datetime] = None,
    endpoint: str = "/audiencias"
) -> AsyncIterator[Dict[str, Any]]:
    """
    Fetch all records from API since a given date, handling pagination automatically.

    Yields individual records from all pages until exhausted.

    Args:
        since: Start date for the query
        until: End date for the query (defaults to now)
        endpoint: API endpoint to query (default: /audiencias)

    Yields:
        Individual record dictionaries from the API

    Example:
        >>> async for record in fetch_since(datetime(2025, 1, 1)):
        ...     print(record["id"], record["sujeto_pasivo"])
        123 "Ministerio de Hacienda"
        124 "Banco Central"
        ...
    """
    config = settings()
    until = until or datetime.now()

    page = 1
    total_records = 0
    total_pages = 0

    logger.info(
        f"Starting ingestion: endpoint={endpoint}, since={since.isoformat()}, until={until.isoformat()}, page_size={config.page_size}"
    )

    while True:
        params = {
            "page": page,
            "page_size": config.page_size,
            "since": since.strftime("%Y-%m-%d"),
            "until": until.strftime("%Y-%m-%d")
        }

        try:
            result = await fetch_page(endpoint, params)
        except Exception as e:
            logger.error(
                f"Failed to fetch page: page={page}, error={str(e)}, error_type={type(e).__name__}"
            )
            raise

        # Extract data from response
        # Note: Actual API response structure may vary, adjust as needed
        data = result.get("data", [])
        has_more = result.get("has_more", False)
        total_available = result.get("total", 0)

        records_in_page = len(data)
        total_records += records_in_page
        total_pages += 1

        logger.debug(
            f"Page fetched: page={page}, records={records_in_page}, total_so_far={total_records}, has_more={has_more}"
        )

        # Yield each record
        for record in data:
            yield record

        # Check if there are more pages
        if not has_more or records_in_page == 0:
            logger.info(
                f"Ingestion complete: total_records={total_records}, total_pages={total_pages}, endpoint={endpoint}"
            )
            break

        page += 1


async def fetch_by_days(
    days: int,
    endpoint: str = "/audiencias"
) -> AsyncIterator[Dict[str, Any]]:
    """
    Convenience function to fetch records from the last N days.

    Args:
        days: Number of days to look back
        endpoint: API endpoint to query

    Yields:
        Individual record dictionaries

    Example:
        >>> # Fetch last 7 days
        >>> async for record in fetch_by_days(7):
        ...     print(record["id"])
    """
    since, until = resolve_window(days=days)
    async for record in fetch_since(since, until, endpoint):
        yield record


async def count_records(
    since: datetime,
    until: Optional[datetime] = None,
    endpoint: str = "/audiencias"
) -> int:
    """
    Count total records in a time window without yielding them.

    Useful for progress reporting or dry-run mode.

    Args:
        since: Start date
        until: End date (defaults to now)
        endpoint: API endpoint

    Returns:
        Total number of records

    Example:
        >>> total = await count_records(datetime(2025, 1, 1))
        >>> print(f"Would process {total} records")
    """
    count = 0
    async for _ in fetch_since(since, until, endpoint):
        count += 1
    return count


def get_engine() -> Engine:
    """
    Get or create database engine.

    Returns:
        SQLAlchemy Engine instance

    Raises:
        ValueError: If DATABASE_URL is not configured
    """
    config = settings()

    if not config.database_url:
        raise ValueError(
            "DATABASE_URL is not configured. Set it in .env or environment variables."
        )

    return create_engine(
        config.database_url,
        pool_pre_ping=True,
        pool_recycle=3600,
    )


async def ingest_audiencias(
    records: List[Dict[str, Any]],
    tenant_code: str = "CL",
    engine: Optional[Engine] = None
) -> int:
    """
    Ingest audiencias records into database.

    Args:
        records: List of audiencia records (from API or fixtures)
        tenant_code: Tenant identifier (default: 'CL')
        engine: SQLAlchemy engine (creates new if None)

    Returns:
        Number of records successfully processed

    Example:
        >>> records = [load_fixture("audiencia_sample.json")]
        >>> count = await ingest_audiencias(records)
        >>> print(f"Processed {count} audiencias")
    """
    if engine is None:
        engine = get_engine()

    processed = 0

    for record in records:
        try:
            await upsert_raw_event(engine, record, kind="audiencia", tenant_code=tenant_code)
            processed += 1
        except Exception as e:
            logger.error(
                f"Failed to ingest audiencia: error={str(e)}, record_preview={str(record)[:100]}"
            )
            # Continue processing other records (graceful degradation)
            continue

    logger.info(f"Ingested {processed}/{len(records)} audiencias")
    return processed


async def ingest_viajes(
    records: List[Dict[str, Any]],
    tenant_code: str = "CL",
    engine: Optional[Engine] = None
) -> int:
    """
    Ingest viajes records into database.

    Args:
        records: List of viaje records (from API or fixtures)
        tenant_code: Tenant identifier (default: 'CL')
        engine: SQLAlchemy engine (creates new if None)

    Returns:
        Number of records successfully processed

    Example:
        >>> records = [load_fixture("viaje_sample.json")]
        >>> count = await ingest_viajes(records)
        >>> print(f"Processed {count} viajes")
    """
    if engine is None:
        engine = get_engine()

    processed = 0

    for record in records:
        try:
            await upsert_raw_event(engine, record, kind="viaje", tenant_code=tenant_code)
            processed += 1
        except Exception as e:
            logger.error(
                f"Failed to ingest viaje: error={str(e)}, record_preview={str(record)[:100]}"
            )
            continue

    logger.info(f"Ingested {processed}/{len(records)} viajes")
    return processed


async def ingest_donativos(
    records: List[Dict[str, Any]],
    tenant_code: str = "CL",
    engine: Optional[Engine] = None
) -> int:
    """
    Ingest donativos records into database.

    Args:
        records: List of donativo records (from API or fixtures)
        tenant_code: Tenant identifier (default: 'CL')
        engine: SQLAlchemy engine (creates new if None)

    Returns:
        Number of records successfully processed

    Example:
        >>> records = [load_fixture("donativo_sample.json")]
        >>> count = await ingest_donativos(records)
        >>> print(f"Processed {count} donativos")
    """
    if engine is None:
        engine = get_engine()

    processed = 0

    for record in records:
        try:
            await upsert_raw_event(engine, record, kind="donativo", tenant_code=tenant_code)
            processed += 1
        except Exception as e:
            logger.error(
                f"Failed to ingest donativo: error={str(e)}, record_preview={str(record)[:100]}"
            )
            continue

    logger.info(f"Ingested {processed}/{len(records)} donativos")
    return processed


def map_staging_to_canonical(
    engine: Optional[Engine] = None,
    kind: Optional[str] = None,
    tenant_code: str = "CL",
    limit: Optional[int] = None,
) -> Dict[str, int]:
    """
    Map staging VIEW rows to canonical graph entities.

    Reads from lobby_events_staging VIEW, extracts canonical entities
    (Person, Organisation, Event, Edge), and persists them idempotently.

    Args:
        engine: SQLAlchemy engine (creates new if None)
        kind: Filter by event kind ('audiencia', 'viaje', 'donativo'). None = all
        tenant_code: Tenant filter (default: 'CL')
        limit: Maximum rows to process (default: no limit)

    Returns:
        Statistics dict with entity counts:
        {
            'rows_processed': int,
            'persons_created': int,
            'persons_updated': int,
            'orgs_created': int,
            'orgs_updated': int,
            'events_created': int,
            'events_updated': int,
            'edges_created': int,
            'edges_updated': int,
        }

    Example:
        >>> stats = map_staging_to_canonical(kind="audiencia", limit=100)
        >>> print(f"Processed {stats['rows_processed']} rows")
        >>> print(f"Created {stats['persons_created']} persons, {stats['edges_created']} edges")
    """
    if engine is None:
        engine = get_engine()

    # Read staging rows
    logger.info(f"Reading staging rows: kind={kind}, tenant_code={tenant_code}, limit={limit}")
    staging_rows = read_staging_rows(
        engine=engine,
        kind=kind,
        tenant_code=tenant_code,
        limit=limit,
    )

    if not staging_rows:
        logger.info("No staging rows found to process")
        return {
            'rows_processed': 0,
            'persons_created': 0,
            'persons_updated': 0,
            'orgs_created': 0,
            'orgs_updated': 0,
            'events_created': 0,
            'events_updated': 0,
            'edges_created': 0,
            'edges_updated': 0,
        }

    # Aggregate stats
    total_stats = {
        'rows_processed': 0,
        'persons_created': 0,
        'persons_updated': 0,
        'orgs_created': 0,
        'orgs_updated': 0,
        'events_created': 0,
        'events_updated': 0,
        'edges_created': 0,
        'edges_updated': 0,
    }

    # Process each staging row
    for row in staging_rows:
        try:
            # Need to fetch rawData from LobbyEventRaw
            from sqlalchemy import text
            with engine.connect() as conn:
                result = conn.execute(
                    text('SELECT "rawData" FROM "LobbyEventRaw" WHERE "externalId" = :external_id'),
                    {"external_id": row["externalId"]}
                )
                raw_row = result.fetchone()
                if not raw_row:
                    logger.warning(f"No raw data found for externalId={row['externalId']}")
                    continue

                raw_data = raw_row[0]

            # Map to canonical entities
            bundle = map_staging_row(row, raw_data)

            # Upsert to database
            stats = upsert_canonical(engine, bundle)

            # Aggregate stats
            total_stats['rows_processed'] += 1
            total_stats['persons_created'] += stats['persons_created']
            total_stats['persons_updated'] += stats['persons_updated']
            total_stats['orgs_created'] += stats['orgs_created']
            total_stats['orgs_updated'] += stats['orgs_updated']
            total_stats['events_created'] += stats['events_created']
            total_stats['events_updated'] += stats['events_updated']
            total_stats['edges_created'] += stats['edges_created']
            total_stats['edges_updated'] += stats['edges_updated']

        except Exception as e:
            logger.error(
                f"Failed to map staging row: error={str(e)}, "
                f"external_id={row.get('externalId')}, kind={row.get('kind')}"
            )
            # Continue processing other rows (graceful degradation)
            continue

    logger.info(
        f"Canonical mapping complete: processed={total_stats['rows_processed']}, "
        f"persons={total_stats['persons_created']}+{total_stats['persons_updated']}, "
        f"orgs={total_stats['orgs_created']}+{total_stats['orgs_updated']}, "
        f"events={total_stats['events_created']}+{total_stats['events_updated']}, "
        f"edges={total_stats['edges_created']}+{total_stats['edges_updated']}"
    )

    return total_stats
