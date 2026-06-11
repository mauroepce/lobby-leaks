#!/usr/bin/env python3
"""
InfoLobby smoke-test orchestrator.

Validates the full SPARQL → parse → merge → persist pipeline end-to-end against
the configured database with a small sample:

    fetch  -> parse  -> merge persons/orgs    -> persist Person/Organisation
                  \\-> extract_events          -> persist Event
                       extract_participations -> persist Edge

Usage:
    DATABASE_URL=... python scripts/sync_infolobby_smoke.py --limit 10
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import create_engine, text  # noqa: E402

from services.info_lobby_sync.event_persistence import persist_events  # noqa: E402
from services.info_lobby_sync.events import extract_events  # noqa: E402
from services.info_lobby_sync.fetcher import (  # noqa: E402
    SPARQLClient,
    fetch_audiencias,
    fetch_donativos,
    fetch_viajes,
)
from services.info_lobby_sync.merge import merge_records  # noqa: E402
from services.info_lobby_sync.parser import (  # noqa: E402
    parse_all_audiencias,
    parse_all_donativos,
    parse_all_viajes,
)
from services.info_lobby_sync.participation import (  # noqa: E402
    extract_participations,
    load_organisations_dict,
    load_persons_dict,
)
from services.info_lobby_sync.participation_persistence import (  # noqa: E402
    persist_participations,
)
from services.info_lobby_sync.persistence import persist_merge_result  # noqa: E402

logger = logging.getLogger("infolobby.smoke")


def _to_dict(obj: Any) -> dict:
    if is_dataclass(obj):
        return asdict(obj)
    return vars(obj)


def fetch_sample(client: SPARQLClient, limit: int, rate_sleep: float) -> dict:
    """Fetch a small sample of each kind, sleeping `rate_sleep` seconds between calls."""
    out: dict[str, list[dict]] = {}

    logger.info("Fetching audiencias (limit=%d)", limit)
    out["audiencias"] = fetch_audiencias(client=client, limit=limit, offset=0)
    logger.info("  → %d records", len(out["audiencias"]))
    time.sleep(rate_sleep)

    logger.info("Fetching viajes (limit=%d)", limit)
    out["viajes"] = fetch_viajes(client=client, limit=limit, offset=0)
    logger.info("  → %d records", len(out["viajes"]))
    time.sleep(rate_sleep)

    logger.info("Fetching donativos (limit=%d)", limit)
    out["donativos"] = fetch_donativos(client=client, limit=limit, offset=0)
    logger.info("  → %d records", len(out["donativos"]))

    return out


def parse_sample(raw: dict) -> dict:
    """Parse raw SPARQL records into typed dataclasses, keyed by kind.

    Returns both the typed lists (events extractor needs them) and a flat
    list of dicts (merger expects dicts).
    """
    audiencias = parse_all_audiencias(raw["audiencias"])
    viajes = parse_all_viajes(raw["viajes"])
    donativos = parse_all_donativos(raw["donativos"])
    flat_dicts = [_to_dict(r) for r in (*audiencias, *viajes, *donativos)]
    return {
        "audiencias": audiencias,
        "viajes": viajes,
        "donativos": donativos,
        "flat_dicts": flat_dicts,
    }


def verify_db_counts(engine, tenant_code: str) -> dict:
    """Smoke check: count rows per table after persistence."""
    with engine.connect() as conn:
        counts = {
            "Person": conn.execute(
                text('SELECT count(*) FROM "Person" WHERE "tenantCode"=:t'),
                {"t": tenant_code},
            ).scalar_one(),
            "Organisation": conn.execute(
                text('SELECT count(*) FROM "Organisation" WHERE "tenantCode"=:t'),
                {"t": tenant_code},
            ).scalar_one(),
            "Event": conn.execute(
                text('SELECT count(*) FROM "Event" WHERE "tenantCode"=:t'),
                {"t": tenant_code},
            ).scalar_one(),
            "Edge": conn.execute(
                text('SELECT count(*) FROM "Edge" WHERE "tenantCode"=:t'),
                {"t": tenant_code},
            ).scalar_one(),
        }
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10, help="SPARQL records per kind")
    parser.add_argument("--tenant", default="CL")
    parser.add_argument(
        "--rate-sleep",
        type=float,
        default=1.0,
        help="Seconds to sleep between SPARQL calls (WAF rate limiting)",
    )
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    # Prefer DIRECT_URL (Session Pooler / direct): full Postgres features and no
    # PgBouncer quirks. DATABASE_URL points to the transaction pooler which
    # would need extra config (no prepared statements, ?pgbouncer=true stripped).
    database_url = os.environ.get("DIRECT_URL") or os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("Neither DIRECT_URL nor DATABASE_URL is set. Source .env first.")
        return 2

    started_at = datetime.utcnow()
    metrics: dict[str, Any] = {
        "timestamp": started_at.isoformat() + "Z",
        "tenant": args.tenant,
        "limit": args.limit,
        "status": "ok",
        "errors": [],
    }

    try:
        with SPARQLClient() as client:
            raw = fetch_sample(client, limit=args.limit, rate_sleep=args.rate_sleep)

        metrics["fetched"] = {k: len(v) for k, v in raw.items()}

        parsed = parse_sample(raw)
        metrics["parsed_total"] = len(parsed["flat_dicts"])

        # Force psycopg v3 driver (info_lobby_sync/requirements.txt installs
        # psycopg[binary]; the bare "postgresql://" scheme would try psycopg2).
        if database_url.startswith("postgresql://"):
            database_url = "postgresql+psycopg://" + database_url[len("postgresql://"):]
        engine = create_engine(database_url, future=True)

        # ── persons & orgs ────────────────────────────────────────────────
        merge_result = merge_records(parsed["flat_dicts"], engine, tenant_code=args.tenant)
        metrics["merge"] = {
            "persons": len(merge_result.persons),
            "organisations": len(merge_result.organisations),
            "duplicates_found": merge_result.duplicates_found,
        }

        person_persist = persist_merge_result(engine, merge_result)
        metrics["persistence"] = {
            "persons_inserted": person_persist.persons_inserted,
            "persons_updated": person_persist.persons_updated,
            "orgs_inserted": person_persist.orgs_inserted,
            "orgs_updated": person_persist.orgs_updated,
            "total_processed": person_persist.total_processed,
            "errors": person_persist.errors,
        }

        # ── events ────────────────────────────────────────────────────────
        events = extract_events(
            audiencias=parsed["audiencias"],
            viajes=parsed["viajes"],
            donativos=parsed["donativos"],
        )
        event_persist = persist_events(engine, events, tenant_code=args.tenant)
        metrics["events"] = {
            "extracted": len(events),
            "inserted": event_persist.inserted,
            "updated": event_persist.updated,
            "skipped": event_persist.skipped,
            "errors": event_persist.errors,
        }

        # ── participations (edges) ────────────────────────────────────────
        # Events must already be in DB so participation_persistence can
        # resolve them by (externalId, kind). Same for persons/orgs.
        # load_*_dict opens its own connection internally — pass engine.
        persons_lookup = load_persons_dict(engine, tenant_code=args.tenant)
        orgs_lookup = load_organisations_dict(engine, tenant_code=args.tenant)
        participation = extract_participations(events, persons_lookup, orgs_lookup)
        edge_persist = persist_participations(
            participation.edges, engine, tenant_code=args.tenant
        )
        metrics["participations"] = {
            "edges_extracted": participation.total_edges,
            "skipped_unmatched_refs": participation.total_skipped,
            "edges_inserted": edge_persist.inserted_edges,
            "edges_skipped_no_event": edge_persist.skipped_missing_event,
            "edges_skipped_duplicate": edge_persist.skipped_duplicates,
            "edges_by_role": edge_persist.edges_by_role,
            "errors": edge_persist.errors,
        }

        metrics["db_counts_after"] = verify_db_counts(engine, args.tenant)

    except Exception as e:
        logger.exception("Smoke test failed")
        metrics["status"] = "error"
        metrics["errors"].append(f"{type(e).__name__}: {e}")

    metrics["duration_seconds"] = (datetime.utcnow() - started_at).total_seconds()

    print(json.dumps(metrics, indent=2, default=str))
    return 0 if metrics["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
