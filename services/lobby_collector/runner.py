#!/usr/bin/env python3
"""
Lobby Collector Pipeline Runner.

Orchestrates the complete ingestion pipeline:
1. Fetch from API (if ENABLE_LOBBY_API=true)
2. Map staging to canonical graph

Outputs JSON metrics for monitoring and always exits 0 (safe for cron).
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from typing import Dict, Any

from .settings import settings
from .ingest import (
    get_engine,
    fetch_since,
    resolve_window,
    ingest_audiencias,
    ingest_viajes,
    ingest_donativos,
    map_staging_to_canonical,
)

logger = logging.getLogger(__name__)


def output_metrics(metrics: Dict[str, Any], output_file: str = "ingest-metrics.json") -> None:
    """Write metrics to JSON file and stdout."""
    metrics_json = json.dumps(metrics, indent=2, default=str)

    # Write to file
    with open(output_file, "w") as f:
        f.write(metrics_json)

    # Also output to stdout for CI logs
    print(metrics_json)


async def run_fetch(days: int, tenant_code: str = "CL") -> Dict[str, int]:
    """
    Fetch data from Lobby API for all endpoints.

    Returns stats dict with rows inserted/updated per endpoint.
    """
    engine = get_engine()
    since, until = resolve_window(days=days)

    stats = {
        "audiencias_inserted": 0,
        "audiencias_updated": 0,
        "viajes_inserted": 0,
        "viajes_updated": 0,
        "donativos_inserted": 0,
        "donativos_updated": 0,
    }

    # Fetch audiencias
    logger.info(f"Fetching audiencias: since={since}, until={until}")
    audiencias = []
    async for record in fetch_since(since, until, endpoint="/audiencias"):
        audiencias.append(record)

    if audiencias:
        count = await ingest_audiencias(audiencias, tenant_code=tenant_code, engine=engine)
        stats["audiencias_inserted"] = count
        logger.info(f"Ingested {count} audiencias")

    # Fetch viajes
    logger.info(f"Fetching viajes: since={since}, until={until}")
    viajes = []
    async for record in fetch_since(since, until, endpoint="/viajes"):
        viajes.append(record)

    if viajes:
        count = await ingest_viajes(viajes, tenant_code=tenant_code, engine=engine)
        stats["viajes_inserted"] = count
        logger.info(f"Ingested {count} viajes")

    # Fetch donativos
    logger.info(f"Fetching donativos: since={since}, until={until}")
    donativos = []
    async for record in fetch_since(since, until, endpoint="/donativos"):
        donativos.append(record)

    if donativos:
        count = await ingest_donativos(donativos, tenant_code=tenant_code, engine=engine)
        stats["donativos_inserted"] = count
        logger.info(f"Ingested {count} donativos")

    return stats


def run_map(tenant_code: str = "CL") -> Dict[str, int]:
    """
    Map staging VIEW to canonical graph.

    Returns stats from map_staging_to_canonical.
    """
    logger.info("Mapping staging to canonical...")
    stats = map_staging_to_canonical(tenant_code=tenant_code)
    logger.info(f"Canonical mapping complete: {stats}")
    return stats


async def run_pipeline(days: int, tenant_code: str = "CL") -> Dict[str, Any]:
    """
    Run the complete ingestion pipeline.

    Always returns metrics dict and exits 0 (safe for cron).
    """
    config = settings()
    start_time = datetime.utcnow()

    metrics: Dict[str, Any] = {
        "timestamp": start_time.isoformat() + "Z",
        "service": config.service_name,
        "tenant_code": tenant_code,
        "days": days,
        "status": "ok",
        "fetch": {
            "enabled": config.enable_lobby_api,
            "audiencias_inserted": 0,
            "viajes_inserted": 0,
            "donativos_inserted": 0,
        },
        "map": {
            "rows_processed": 0,
            "persons_created": 0,
            "persons_updated": 0,
            "orgs_created": 0,
            "orgs_updated": 0,
            "events_created": 0,
            "events_updated": 0,
            "edges_created": 0,
            "edges_updated": 0,
        },
        "errors": [],
    }

    # Step 1: Fetch (if enabled)
    if config.enable_lobby_api:
        try:
            fetch_stats = await run_fetch(days, tenant_code)
            metrics["fetch"].update(fetch_stats)
            logger.info(f"Fetch completed: {fetch_stats}")
        except Exception as e:
            error_msg = f"Fetch failed: {type(e).__name__}: {str(e)}"
            logger.warning(error_msg)
            metrics["errors"].append(error_msg)
            metrics["status"] = "degraded"
    else:
        logger.info("Lobby API disabled, skipping fetch")
        metrics["fetch"]["skipped"] = True

    # Step 2: Map staging to canonical (always runs)
    try:
        map_stats = run_map(tenant_code)
        metrics["map"].update(map_stats)
        logger.info(f"Map completed: {map_stats}")
    except Exception as e:
        error_msg = f"Map failed: {type(e).__name__}: {str(e)}"
        logger.error(error_msg)
        metrics["errors"].append(error_msg)
        metrics["status"] = "error"

    # Calculate duration
    end_time = datetime.utcnow()
    metrics["duration_seconds"] = (end_time - start_time).total_seconds()

    # Set final status
    if not metrics["errors"]:
        if not config.enable_lobby_api:
            metrics["status"] = "skipped"
        else:
            metrics["status"] = "ok"

    return metrics


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run Lobby Collector ingestion pipeline"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to look back (default: 7)"
    )
    parser.add_argument(
        "--tenant",
        type=str,
        default="CL",
        help="Tenant code (default: CL)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="ingest-metrics.json",
        help="Output file for metrics JSON (default: ingest-metrics.json)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Run pipeline
    metrics = asyncio.run(run_pipeline(args.days, args.tenant))

    # Output metrics
    output_metrics(metrics, args.output)

    # Always exit 0 (safe for cron)
    # Status is indicated in metrics, not exit code
    sys.exit(0)


if __name__ == "__main__":
    main()
