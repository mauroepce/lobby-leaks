"""
Persistence layer for InfoLobby events.

Bridges the gap between event extraction (events.py → BaseEvent subclasses) and
edge persistence (participation_persistence.py, which expects events to already
exist in the Event table).

Natural key for idempotent upsert: (tenantCode, externalId, kind).
Event subtype is stored in `kind` ("audience" | "travel" | "donation").
Type-specific fields are packed into the `metadata` JSONB column.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from services.info_lobby_sync.events import (
    AudienceEvent,
    BaseEvent,
    DonationEvent,
    TravelEvent,
)


@dataclass
class EventPersistResult:
    """Counts + lookup table after persistence."""

    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    errors: List[str] = field(default_factory=list)
    # external_id → db event id (built so callers can chain participations
    # without a separate DB roundtrip; participation_persistence will reload
    # if this isn't passed through).
    event_ids: Dict[str, str] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    @property
    def total_processed(self) -> int:
        return self.inserted + self.updated

    def to_dict(self) -> Dict[str, Any]:
        return {
            "inserted": self.inserted,
            "updated": self.updated,
            "skipped": self.skipped,
            "total_processed": self.total_processed,
            "errors": self.errors,
        }


def _kind_for(event: BaseEvent) -> str:
    """Map an event subclass to its Event.kind value."""
    if isinstance(event, AudienceEvent):
        return "audience"
    if isinstance(event, TravelEvent):
        return "travel"
    if isinstance(event, DonationEvent):
        return "donation"
    # event_type is set by the dataclass default; trust it for unknown subtypes.
    return event.event_type


def _build_metadata(event: BaseEvent) -> Dict[str, Any]:
    """Pack subtype-specific fields + provenance into a JSON-serialisable dict.

    Only the fields meaningful for an Event row land here. Entity refs
    (pasivo_ref, activos_refs, …) belong to ParticipationEdge and are NOT
    stored on Event — those are resolved against canonical Person/Organisation
    rows at participation extraction time.
    """
    metadata: Dict[str, Any] = {"source": event.source}

    if isinstance(event, AudienceEvent):
        metadata.update(
            {
                "lugar": event.lugar,
                "forma": event.forma,
                "materias": event.materias or None,
                "descripcion": event.descripcion,
                "observaciones": event.observaciones,
            }
        )
    elif isinstance(event, TravelEvent):
        metadata.update(
            {
                "destino": event.destino,
                "motivo": event.motivo,
                "costo_total": event.costo_total,
            }
        )
    elif isinstance(event, DonationEvent):
        metadata.update(
            {
                "tipo_donativo": event.tipo_donativo,
                "descripcion": event.descripcion,
                "ocasion": event.ocasion,
            }
        )

    # Drop None values so the JSON stays compact and queries are simpler.
    return {k: v for k, v in metadata.items() if v is not None}


def persist_events(
    engine: Engine,
    events: List[BaseEvent],
    tenant_code: str = "CL",
) -> EventPersistResult:
    """
    Batched UPSERT into the Event table.

    Idempotent on the natural key (tenantCode, externalId, kind). On
    conflict the row's date + metadata are refreshed (source data may
    add fields the first ingest didn't have).

    Single bulk INSERT statement plus one pre-flight SELECT to classify
    rows as inserted vs updated for the metrics. The earlier per-event
    INSERT was about 16% of total sync time at the pooler RTT we have.

    Args:
        engine: SQLAlchemy engine
        events: Output of `extract_events(...)` — heterogeneous list of
            AudienceEvent | TravelEvent | DonationEvent.
        tenant_code: tenantCode invariant; the graph is tenant-scoped.

    Returns:
        EventPersistResult — counts + a `{external_id: db_id}` lookup
        callers can pass to participation persistence to avoid a reload.
    """
    result = EventPersistResult(started_at=datetime.utcnow())

    if not events:
        result.finished_at = datetime.utcnow()
        return result

    # Build the parameter rows up front; skip events with no external_id.
    now = datetime.utcnow()
    rows: List[Dict[str, Any]] = []
    for event in events:
        if not event.external_id:
            result.skipped += 1
            continue
        rows.append({
            "id": str(uuid.uuid4()),
            "tenant_code": tenant_code,
            "external_id": event.external_id,
            "kind": _kind_for(event),
            "date": event.date_start,
            "metadata": json.dumps(_build_metadata(event)),
            "now": now,
        })

    if not rows:
        result.finished_at = datetime.utcnow()
        return result

    # Pre-flight: which (externalId, kind) pairs already exist? One
    # round-trip for the whole batch, used to populate accurate
    # inserted/updated counts after the bulk upsert.
    existing_keys: set[tuple] = set()
    try:
        with engine.connect() as conn:
            lookup_sql = text("""
                SELECT "externalId", kind FROM "Event"
                WHERE "tenantCode" = :tenant_code
                  AND "externalId" = ANY(:ext_ids)
            """)
            ext_ids = list({r["external_id"] for r in rows})
            cursor = conn.execute(
                lookup_sql, {"tenant_code": tenant_code, "ext_ids": ext_ids}
            )
            existing_keys = {(row[0], row[1]) for row in cursor}
    except Exception as e:
        # Lookup failure isn't fatal — we'll still upsert; the metrics
        # just lose the inserted/updated breakdown for this run.
        result.errors.append(f"event pre-flight lookup: {type(e).__name__}: {e}")

    upsert_sql = text("""
        INSERT INTO "Event" (
            id, "tenantCode", "externalId", kind,
            "date", metadata,
            "createdAt", "updatedAt"
        )
        VALUES (
            :id, :tenant_code, :external_id, :kind,
            :date, CAST(:metadata AS jsonb),
            :now, :now
        )
        ON CONFLICT ("tenantCode", "externalId", kind) DO UPDATE
        SET "date" = EXCLUDED."date",
            metadata = EXCLUDED.metadata,
            "updatedAt" = EXCLUDED."updatedAt"
    """)

    try:
        with engine.begin() as conn:
            conn.execute(upsert_sql, rows)
    except Exception as e:
        result.errors.append(f"event bulk upsert ({len(rows)}): {type(e).__name__}: {e}")
        result.finished_at = datetime.utcnow()
        return result

    for row in rows:
        key = (row["external_id"], row["kind"])
        if key in existing_keys:
            result.updated += 1
        else:
            result.inserted += 1

    # Map external_id → db_id for downstream participation persistence.
    # The DB id is either the freshly generated uuid (if inserted) or
    # whatever Postgres has (if updated); read both back with one SELECT.
    try:
        with engine.connect() as conn:
            ext_ids = list({r["external_id"] for r in rows})
            id_sql = text("""
                SELECT "externalId", id FROM "Event"
                WHERE "tenantCode" = :tenant_code
                  AND "externalId" = ANY(:ext_ids)
            """)
            cursor = conn.execute(
                id_sql, {"tenant_code": tenant_code, "ext_ids": ext_ids}
            )
            result.event_ids = {row[0]: row[1] for row in cursor}
    except Exception as e:
        result.errors.append(f"event id readback: {type(e).__name__}: {e}")

    result.finished_at = datetime.utcnow()
    return result
