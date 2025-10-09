"""
Data ingestion logic with pagination and temporal windows.

Handles iterating through paginated API responses and calculating
time windows for incremental updates.
"""

import logging
from datetime import datetime, timedelta
from typing import AsyncIterator, Any

from .client import fetch_page
from .settings import settings


logger = logging.getLogger(__name__)


def resolve_window(
    now: datetime | None = None,
    days: int | None = None
) -> tuple[datetime, datetime]:
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
    until: datetime | None = None,
    endpoint: str = "/audiencias"
) -> AsyncIterator[dict[str, Any]]:
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
) -> AsyncIterator[dict[str, Any]]:
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
    until: datetime | None = None,
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
