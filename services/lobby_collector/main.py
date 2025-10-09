"""
CLI entry point for Lobby Collector service.

Usage:
    python -m services.lobby_collector.main --since 2025-01-01
    python -m services.lobby_collector.main --days 7
    python -m services.lobby_collector.main --test-connection
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime

from . import __version__
from .client import test_connection
from .ingest import fetch_since, fetch_by_days, resolve_window
from .settings import settings


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Lobby Collector - Ingest data from Chile's Ley de Lobby API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch data since specific date
  python -m services.lobby_collector.main --since 2025-01-01

  # Fetch last 7 days (default)
  python -m services.lobby_collector.main --days 7

  # Test API connection
  python -m services.lobby_collector.main --test-connection

  # Dry run (count records without processing)
  python -m services.lobby_collector.main --since 2025-01-01 --dry-run

  # Debug mode
  python -m services.lobby_collector.main --since 2025-01-01 --debug
        """
    )

    parser.add_argument(
        "--since",
        type=str,
        help="Start date in YYYY-MM-DD format"
    )

    parser.add_argument(
        "--until",
        type=str,
        help="End date in YYYY-MM-DD format (default: now)"
    )

    parser.add_argument(
        "--days",
        type=int,
        help=f"Number of days to look back (default: {settings().default_since_days})"
    )

    parser.add_argument(
        "--endpoint",
        type=str,
        default="/audiencias",
        help="API endpoint to query (default: /audiencias)"
    )

    parser.add_argument(
        "--test-connection",
        action="store_true",
        help="Test connection to API and exit"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count records without processing them"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}"
    )

    return parser.parse_args()


async def run_ingestion(args: argparse.Namespace) -> int:
    """
    Run the data ingestion process.

    Args:
        args: Parsed command line arguments

    Returns:
        Exit code (0 for success, 1 for error)
    """
    config = settings()

    # Set log level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)

    # Determine time window
    if args.since:
        try:
            since = datetime.fromisoformat(args.since)
        except ValueError:
            logger.error(f"Invalid date format: {args.since}. Expected YYYY-MM-DD")
            return 1

        if args.until:
            try:
                until = datetime.fromisoformat(args.until)
            except ValueError:
                logger.error(f"Invalid date format: {args.until}. Expected YYYY-MM-DD")
                return 1
        else:
            until = datetime.now()

        logger.info(
            "Using specified date range",
            since=since.isoformat(),
            until=until.isoformat()
        )
    elif args.days:
        since, until = resolve_window(days=args.days)
        logger.info(
            "Using last N days",
            days=args.days,
            since=since.isoformat(),
            until=until.isoformat()
        )
    else:
        # Default: use config.default_since_days
        since, until = resolve_window()
        logger.info(
            "Using default lookback period",
            days=config.default_since_days,
            since=since.isoformat(),
            until=until.isoformat()
        )

    # Dry run mode
    if args.dry_run:
        logger.info("DRY RUN MODE - Counting records only")
        from .ingest import count_records
        total = await count_records(since, until, args.endpoint)
        logger.info(f"Would process {total} records")
        return 0

    # Process records
    try:
        count = 0
        start_time = datetime.now()

        async for record in fetch_since(since, until, args.endpoint):
            count += 1

            # Log progress every 100 records
            if count % 100 == 0:
                logger.info(f"Processed {count} records...")

            # TODO: In next story, save to database
            # For now, just log sample
            if count <= 3 or args.debug:
                logger.debug(f"Record {count}: {record.get('id', 'N/A')}")

        elapsed = (datetime.now() - start_time).total_seconds()

        logger.info(
            "Ingestion completed successfully",
            total_records=count,
            duration_seconds=round(elapsed, 2),
            records_per_second=round(count / elapsed if elapsed > 0 else 0, 2)
        )

        return 0

    except Exception as e:
        logger.error(
            "Ingestion failed",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True
        )
        return 1


async def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Test connection mode
    if args.test_connection:
        logger.info("Testing connection to Lobby API...")
        success = await test_connection()
        if success:
            logger.info("✅ Connection test PASSED")
            return 0
        else:
            logger.error("❌ Connection test FAILED")
            return 1

    # Run ingestion
    return await run_ingestion(args)


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
