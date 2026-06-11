#!/usr/bin/env python3
"""
InfoLobby sync — production orchestrator.

Drives the full canonical pipeline against InfoLobby SPARQL:

    fetch (paginated) -> parse -> merge persons/orgs -> persist
                                                     \\-> persist events
                                                          extract+persist participations

Outputs JSON metrics on stdout (and optionally to a file) and ALWAYS exits 0,
so it is safe to run from cron / a workflow that already alerts on metrics.

Usage:
    # Full sync with defaults (batch=1000, 1 req/s, no cap)
    DATABASE_URL=... python -m services.info_lobby_sync.run_sync

    # Capped first run, faster pacing, write metrics to file
    DATABASE_URL=... python -m services.info_lobby_sync.run_sync \\
        --max-records 500 --rate-sleep 0.5 --output sync-metrics.json

    # Validate the SPARQL → parse path without touching the DB
    DATABASE_URL=... python -m services.info_lobby_sync.run_sync --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import create_engine, text

from services.info_lobby_sync.event_persistence import persist_events
from services.info_lobby_sync.events import extract_events
from services.info_lobby_sync.fetcher import (
    SPARQLClient,
    fetch_audiencias,
    fetch_donativos,
    fetch_viajes,
)
from services.info_lobby_sync.merge import merge_records
from services.info_lobby_sync.parser import (
    parse_all_audiencias,
    parse_all_donativos,
    parse_all_viajes,
)
from services.info_lobby_sync.participation import (
    extract_participations,
    load_organisations_dict,
    load_persons_dict,
)
from services.info_lobby_sync.participation_persistence import persist_participations
from services.info_lobby_sync.persistence import persist_merge_result

logger = logging.getLogger("infolobby.sync")

KIND_FETCHERS = {
    "audiencias": fetch_audiencias,
    "viajes": fetch_viajes,
    "donativos": fetch_donativos,
}

KIND_PARSERS = {
    "audiencias": parse_all_audiencias,
    "viajes": parse_all_viajes,
    "donativos": parse_all_donativos,
}

# InfoLobby runs Virtuoso, which caps `ORDER BY ... LIMIT N OFFSET M` queries
# at M+N <= 100_000 with SR353 ("Sorted TOP clause specifies more then ... rows
# to sort. Only 100000 are allowed."). Going past this requires keyset
# pagination (cursor by fechaEvento DESC) — tracked as Phase 2. For now the
# fetcher clamps each batch so the (offset+limit) stays within bounds and
# stops cleanly when there's no room left.
VIRTUOSO_ORDERED_MAX = 100_000


def _to_dict(obj: Any) -> dict:
    if is_dataclass(obj):
        return asdict(obj)
    return vars(obj)


@contextmanager
def _stage(name: str, timings: Dict[str, float]):
    """Time a pipeline stage and accumulate into the timings dict."""
    start = time.perf_counter()
    try:
        yield
    finally:
        timings[name] = round(time.perf_counter() - start, 3)
        logger.info("stage %s — %.3fs", name, timings[name])


def fetch_kind_paginated(
    client: SPARQLClient,
    kind: str,
    batch_size: int,
    max_records: int | None,
    rate_sleep: float,
    start_offset: int = 0,
) -> List[Dict[str, Any]]:
    """Loop SPARQL pages until exhausted or `max_records` cap is hit.

    `start_offset` lets the caller resume part-way through the corpus
    (chunked syncs use this to avoid OOM on the 1M+ record sets). The
    `max_records` cap still applies AFTER `start_offset` — fetch returns
    at most `max_records` records, starting from position `start_offset`.

    Rate-limited between batches to be polite to the InfoLobby WAF.
    Each batch fetched is logged so a long-running sync produces visible
    progress in CI logs.
    """
    fetch_fn = KIND_FETCHERS[kind]
    all_records: List[Dict[str, Any]] = []
    offset = start_offset

    while True:
        if max_records is not None:
            remaining = max_records - len(all_records)
            if remaining <= 0:
                break
            limit = min(batch_size, remaining)
        else:
            limit = batch_size

        # Clamp so offset+limit stays within Virtuoso's 100k ORDER-BY cap.
        # When offset >= VIRTUOSO_ORDERED_MAX we can't ask for any more
        # rows without hitting SR353 — stop cleanly and let the caller
        # know (the wrapper script reads this as "kind exhausted").
        if offset >= VIRTUOSO_ORDERED_MAX:
            logger.info(
                "fetch %s — hit Virtuoso ORDER BY cap at offset=%d; "
                "stopping (Phase 2 keyset pagination needed for the rest)",
                kind, offset,
            )
            break
        room = VIRTUOSO_ORDERED_MAX - offset
        if limit > room:
            limit = room

        logger.info("fetch %s offset=%d limit=%d (have %d)", kind, offset, limit, len(all_records))
        batch = fetch_fn(client=client, limit=limit, offset=offset)
        if not batch:
            break

        all_records.extend(batch)
        if len(batch) < limit:
            break  # last page

        offset += limit
        if rate_sleep > 0:
            time.sleep(rate_sleep)

    logger.info("fetch %s done — %d records", kind, len(all_records))
    return all_records


def coerce_database_url(url: str) -> str:
    """Force psycopg v3 driver. SQLAlchemy's bare `postgresql://` default
    is psycopg2 (not installed); psycopg[binary] (v3) is what's in the
    info_lobby_sync requirements."""
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def verify_db_counts(engine, tenant_code: str) -> Dict[str, int]:
    with engine.connect() as conn:
        return {
            t: conn.execute(
                text(f'SELECT count(*) FROM "{t}" WHERE "tenantCode"=:t'),
                {"t": tenant_code},
            ).scalar_one()
            for t in ("Person", "Organisation", "Event", "Edge")
        }


def run_pipeline(args: argparse.Namespace) -> Dict[str, Any]:
    """One full pass: fetch all kinds, then run the canonical pipeline."""
    started_at = datetime.utcnow()
    timings: Dict[str, float] = {}
    metrics: Dict[str, Any] = {
        "timestamp": started_at.isoformat() + "Z",
        "tenant": args.tenant,
        "config": {
            "batch_size": args.batch_size,
            "max_records": args.max_records,
            "offset": args.offset,
            "rate_sleep": args.rate_sleep,
            "dry_run": args.dry_run,
        },
        "status": "ok",
        "errors": [],
        "fetched": {},
        "parsed": {},
        "timings": timings,
    }

    # ── fetch ────────────────────────────────────────────────────────
    raw: Dict[str, List[Dict[str, Any]]] = {}
    try:
        with _stage("fetch_all", timings), SPARQLClient() as client:
            for kind in ("audiencias", "viajes", "donativos"):
                raw[kind] = fetch_kind_paginated(
                    client,
                    kind,
                    batch_size=args.batch_size,
                    max_records=args.max_records,
                    rate_sleep=args.rate_sleep,
                    start_offset=args.offset,
                )
                metrics["fetched"][kind] = len(raw[kind])
                if args.rate_sleep > 0:
                    time.sleep(args.rate_sleep)  # between kinds too
    except Exception as e:
        # A partial fetch still has value — we keep what we got and let the
        # rest of the pipeline run on it; just downgrade status.
        logger.exception("fetch stage failed partway through")
        metrics["errors"].append(f"fetch: {type(e).__name__}: {e}")
        metrics["status"] = "degraded"

    # ── parse ────────────────────────────────────────────────────────
    try:
        with _stage("parse", timings):
            audiencias = parse_all_audiencias(raw.get("audiencias", []))
            viajes = parse_all_viajes(raw.get("viajes", []))
            donativos = parse_all_donativos(raw.get("donativos", []))
            flat_dicts = [_to_dict(r) for r in (*audiencias, *viajes, *donativos)]
        metrics["parsed"] = {
            "audiencias": len(audiencias),
            "viajes": len(viajes),
            "donativos": len(donativos),
            "total": len(flat_dicts),
        }
    except Exception as e:
        logger.exception("parse stage failed")
        metrics["errors"].append(f"parse: {type(e).__name__}: {e}")
        metrics["status"] = "error"
        metrics["duration_seconds"] = (datetime.utcnow() - started_at).total_seconds()
        return metrics

    if args.dry_run:
        logger.info("--dry-run set; skipping all DB writes")
        metrics["dry_run_skipped_persist"] = True
        metrics["duration_seconds"] = (datetime.utcnow() - started_at).total_seconds()
        return metrics

    # ── DB engine ─────────────────────────────────────────────────────
    database_url = os.environ.get("DIRECT_URL") or os.environ.get("DATABASE_URL")
    if not database_url:
        metrics["errors"].append("DIRECT_URL / DATABASE_URL not set")
        metrics["status"] = "error"
        metrics["duration_seconds"] = (datetime.utcnow() - started_at).total_seconds()
        return metrics
    engine = create_engine(coerce_database_url(database_url), future=True)

    # ── persons & orgs ────────────────────────────────────────────────
    try:
        with _stage("merge_records", timings):
            merge_result = merge_records(flat_dicts, engine, tenant_code=args.tenant)
        metrics["merge"] = {
            "persons": len(merge_result.persons),
            "organisations": len(merge_result.organisations),
            "duplicates_found": merge_result.duplicates_found,
            "persons_existing": merge_result.persons_existing,
            "persons_new": merge_result.persons_new,
            "orgs_existing": merge_result.orgs_existing,
            "orgs_new": merge_result.orgs_new,
        }
        with _stage("persist_persons_orgs", timings):
            person_persist = persist_merge_result(engine, merge_result)
        metrics["persistence"] = {
            "persons_inserted": person_persist.persons_inserted,
            "persons_updated": person_persist.persons_updated,
            "persons_unchanged": person_persist.persons_unchanged,
            "orgs_inserted": person_persist.orgs_inserted,
            "orgs_updated": person_persist.orgs_updated,
            "orgs_unchanged": person_persist.orgs_unchanged,
            "errors": person_persist.errors,
        }
        if person_persist.errors:
            metrics["status"] = "degraded"
            metrics["errors"].extend(f"persistence: {e}" for e in person_persist.errors[:5])
    except Exception as e:
        logger.exception("persons/orgs stage failed")
        metrics["errors"].append(f"persistence: {type(e).__name__}: {e}")
        metrics["status"] = "error"
        metrics["duration_seconds"] = (datetime.utcnow() - started_at).total_seconds()
        return metrics

    # ── events ────────────────────────────────────────────────────────
    try:
        with _stage("extract_events", timings):
            events = extract_events(audiencias=audiencias, viajes=viajes, donativos=donativos)
        with _stage("persist_events", timings):
            event_persist = persist_events(engine, events, tenant_code=args.tenant)
        metrics["events"] = {
            "extracted": len(events),
            "inserted": event_persist.inserted,
            "updated": event_persist.updated,
            "skipped": event_persist.skipped,
            "errors": event_persist.errors,
        }
        if event_persist.errors:
            metrics["status"] = "degraded"
            metrics["errors"].extend(f"events: {e}" for e in event_persist.errors[:5])
    except Exception as e:
        logger.exception("events stage failed")
        metrics["errors"].append(f"events: {type(e).__name__}: {e}")
        metrics["status"] = "error"
        metrics["duration_seconds"] = (datetime.utcnow() - started_at).total_seconds()
        return metrics

    # ── participations (edges) ────────────────────────────────────────
    try:
        with _stage("load_lookups", timings):
            persons_lookup = load_persons_dict(engine, tenant_code=args.tenant)
            orgs_lookup = load_organisations_dict(engine, tenant_code=args.tenant)
        with _stage("extract_participations", timings):
            participation = extract_participations(events, persons_lookup, orgs_lookup)
        with _stage("persist_edges", timings):
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
        if edge_persist.errors:
            metrics["status"] = "degraded"
            metrics["errors"].extend(f"edges: {e}" for e in edge_persist.errors[:5])
    except Exception as e:
        logger.exception("participations stage failed")
        metrics["errors"].append(f"participations: {type(e).__name__}: {e}")
        metrics["status"] = "error" if metrics["status"] == "ok" else metrics["status"]

    # ── final db snapshot ─────────────────────────────────────────────
    try:
        metrics["db_counts_after"] = verify_db_counts(engine, args.tenant)
    except Exception as e:
        metrics["errors"].append(f"verify_db_counts: {type(e).__name__}: {e}")

    metrics["duration_seconds"] = (datetime.utcnow() - started_at).total_seconds()
    return metrics


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tenant", default="CL", help="tenantCode invariant (default: CL)")
    p.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="SPARQL pagination size per request (default: 1000)",
    )
    p.add_argument(
        "--max-records",
        type=int,
        default=None,
        help="Cap PER KIND. None = full sync (default: unlimited)",
    )
    p.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Starting SPARQL offset PER KIND, for chunked / resumable syncs "
             "(default: 0). Combine with --max-records to bound a chunk.",
    )
    p.add_argument(
        "--rate-sleep",
        type=float,
        default=1.0,
        help="Seconds between SPARQL calls (WAF politeness, default: 1.0)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch + parse only; skip every DB write",
    )
    p.add_argument(
        "--output",
        default=None,
        help="Optional path to write JSON metrics (also always printed to stdout)",
    )
    p.add_argument("--debug", action="store_true")
    return p.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    metrics = run_pipeline(args)
    payload = json.dumps(metrics, indent=2, default=str)
    print(payload)
    if args.output:
        with open(args.output, "w") as f:
            f.write(payload)

    # Exit 0 by convention — non-zero exit codes break cron-style retries;
    # the JSON status field is the authoritative signal.
    return 0


if __name__ == "__main__":
    sys.exit(main())
