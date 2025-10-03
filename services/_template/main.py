"""
Main CLI module for the LobbyLeaks service template.

Provides command-line interface for data ingestion and processing.
Example: python -m services._template.main --since 2025-01-01
"""

import argparse
import asyncio
import sys
from datetime import datetime, date

# Support both package and standalone modes
try:
    from . import __version__
    from .client import HTTPClient
    from .log_config import get_logger, log_api_call, log_processing_batch
    from .settings import settings
except ImportError:
    # Standalone mode (e.g., running directly or from Docker)
    __version__ = "0.1.0"
    from client import HTTPClient
    from log_config import get_logger, log_api_call, log_processing_batch
    from settings import settings


logger = get_logger(__name__)


def parse_date(date_string: str) -> date:
    """
    Parse date string in YYYY-MM-DD format.

    Args:
        date_string: Date in YYYY-MM-DD format

    Returns:
        Parsed date object

    Raises:
        ValueError: If date format is invalid
    """
    try:
        return datetime.strptime(date_string, "%Y-%m-%d").date()
    except ValueError as e:
        raise ValueError(f"Invalid date format '{date_string}'. Expected YYYY-MM-DD") from e


async def fetch_data_since(since_date: date) -> dict:
    """
    Fetch data from API since the specified date.

    This is a template function that demonstrates how to:
    - Use the HTTP client with retries
    - Log API calls with structured logging
    - Handle errors gracefully

    Args:
        since_date: Date to fetch data from

    Returns:
        Dictionary containing fetched data

    Raises:
        Exception: If data fetching fails after retries
    """
    config = settings()

    logger.info(
        "Starting data fetch",
        since_date=since_date.isoformat(),
        api_base_url=config.api_base_url
    )

    start_time = datetime.now()

    try:
        # Example API endpoint - replace with actual endpoint
        url = f"{config.api_base_url}/data"
        params = {
            "since": since_date.isoformat(),
            "limit": 1000,  # Example parameter
        }

        headers = config.get_api_headers()

        with HTTPClient(
            max_retries=config.api_max_retries,
            timeout=config.api_timeout
        ) as client:
            data = client.get_json(url, headers=headers, params=params)

            duration_ms = (datetime.now() - start_time).total_seconds() * 1000

            log_api_call(
                logger,
                method="GET",
                url=url,
                status_code=200,
                duration_ms=duration_ms,
                records_count=len(data.get("records", []))
            )

            logger.info(
                "Data fetch completed successfully",
                records_fetched=len(data.get("records", [])),
                duration_ms=round(duration_ms, 2)
            )

            return data

    except Exception as e:
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000

        logger.error(
            "Data fetch failed",
            since_date=since_date.isoformat(),
            duration_ms=round(duration_ms, 2),
            error=str(e),
            error_type=type(e).__name__
        )
        raise


def process_records(records: list) -> tuple[int, int]:
    """
    Process fetched records.

    This is a template function that demonstrates record processing
    with structured logging and error handling.

    Args:
        records: List of records to process

    Returns:
        Tuple of (processed_count, failed_count)
    """
    processed = 0
    failed = 0

    logger.info("Starting record processing", total_records=len(records))

    for i, record in enumerate(records):
        try:
            # Example processing - replace with actual logic
            record_id = record.get("id", f"record_{i}")

            # Simulate processing
            if validate_record(record):
                # Process the record (placeholder)
                logger.debug("Record processed successfully", record_id=record_id)
                processed += 1
            else:
                logger.warning("Record validation failed", record_id=record_id)
                failed += 1

        except Exception as e:
            logger.error(
                "Record processing failed",
                record_id=record.get("id", f"record_{i}"),
                error=str(e),
                error_type=type(e).__name__
            )
            failed += 1

    return processed, failed


def validate_record(record: dict) -> bool:
    """
    Validate a single record.

    Args:
        record: Record to validate

    Returns:
        True if record is valid, False otherwise
    """
    # Example validation - replace with actual validation logic
    required_fields = ["id", "timestamp"]

    for field in required_fields:
        if field not in record:
            return False

    return True


async def ingest_since(since_date: str) -> bool:
    """
    Main ingestion function that fetches and processes data since a given date.

    Args:
        since_date: Date string in YYYY-MM-DD format

    Returns:
        True if ingestion was successful, False otherwise
    """
    try:
        # Parse and validate date
        parsed_date = parse_date(since_date)

        logger.info(
            "Starting data ingestion",
            since_date=parsed_date.isoformat(),
            service_version=__version__
        )

        start_time = datetime.now()

        # Fetch data from API
        data = await fetch_data_since(parsed_date)
        records = data.get("records", [])

        if not records:
            logger.info("No records found for the specified date range")
            return True

        # Process records
        processed, failed = process_records(records)

        duration_ms = (datetime.now() - start_time).total_seconds() * 1000

        # Log batch processing results
        batch_id = f"ingest_{parsed_date.isoformat()}_{int(start_time.timestamp())}"
        log_processing_batch(
            logger,
            batch_id=batch_id,
            items_processed=processed,
            items_failed=failed,
            duration_ms=duration_ms
        )

        success = failed == 0

        if success:
            logger.info(
                "Data ingestion completed successfully",
                total_records=len(records),
                processed=processed,
                duration_ms=round(duration_ms, 2)
            )
        else:
            logger.warning(
                "Data ingestion completed with errors",
                total_records=len(records),
                processed=processed,
                failed=failed,
                duration_ms=round(duration_ms, 2)
            )

        return success

    except Exception as e:
        logger.error(
            "Data ingestion failed",
            since_date=since_date,
            error=str(e),
            error_type=type(e).__name__
        )
        return False


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="LobbyLeaks Service Template",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m services._template.main --since 2025-01-01
  python -m services._template.main --since 2025-01-15 --log-level DEBUG
  python -m services._template.main --version
        """
    )

    parser.add_argument(
        "--since",
        type=str,
        required=True,
        help="Fetch data since this date (YYYY-MM-DD format)"
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Override log level from configuration"
    )

    parser.add_argument(
        "--log-format",
        choices=["json", "text"],
        help="Override log format from configuration"
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"LobbyLeaks Service Template {__version__}"
    )

    return parser


async def main() -> int:
    """
    Main entry point for the CLI application.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = create_parser()
    args = parser.parse_args()

    # Configure logging with CLI overrides
    if args.log_level or args.log_format:
        try:
            from .log_config import configure_logging
        except ImportError:
            from log_config import configure_logging
        configure_logging(args.log_level, args.log_format)

    # Log startup information
    config = settings()
    logger.info(
        "Service starting",
        service_name=config.service_name,
        version=__version__,
        environment=config.environment,
        log_level=config.log_level
    )

    try:
        # Run the main ingestion process
        success = await ingest_since(args.since)

        if success:
            logger.info("Service completed successfully")
            return 0
        else:
            logger.error("Service completed with errors")
            return 1

    except KeyboardInterrupt:
        logger.warning("Service interrupted by user")
        return 1
    except Exception as e:
        logger.error(
            "Service failed with unexpected error",
            error=str(e),
            error_type=type(e).__name__
        )
        return 1


def cli_main():
    """Synchronous entry point for setuptools console scripts."""
    return asyncio.run(main())


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))