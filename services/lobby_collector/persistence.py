"""
Raw event persistence for lobby data.

Persists audiencias, viajes, and donativos to a unified LobbyEventRaw table
with idempotent upsert operations.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from sqlalchemy import MetaData, Table, Column, String, DateTime, DECIMAL, text
from sqlalchemy.dialects.postgresql import JSONB, UUID, insert
from sqlalchemy.engine import Engine

from services.lobby_collector.derivers import (
    derive_external_id,
    derive_fecha,
    derive_monto,
    derive_institucion,
    derive_destino,
)

logger = logging.getLogger(__name__)

# Define table metadata
metadata = MetaData()

lobby_event_raw_table = Table(
    "LobbyEventRaw",
    metadata,
    Column("id", String, primary_key=True),
    Column("externalId", String, unique=True, nullable=False),
    Column("tenantCode", String, nullable=False),
    Column("kind", String, nullable=False),
    Column("rawData", JSONB, nullable=False),
    Column("fecha", DateTime(timezone=True)),
    Column("monto", DECIMAL),
    Column("institucion", String),
    Column("destino", String),
    Column("createdAt", DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")),
    Column("updatedAt", DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")),
)


async def upsert_raw_event(
    engine: Engine,
    record: Dict[str, Any],
    kind: str,
    tenant_code: str = "CL",
) -> None:
    """
    Upsert a raw lobby event into the database.

    This function implements idempotent insertion using PostgreSQL's
    INSERT ... ON CONFLICT syntax. If a record with the same externalId
    already exists, it will be updated with the new data.

    Args:
        engine: SQLAlchemy engine instance
        record: Raw JSON record from API or fixture
        kind: Event type ('audiencia', 'viaje', 'donativo')
        tenant_code: Tenant identifier (default: 'CL' for Chile)

    Raises:
        ValueError: If external ID cannot be derived
        Exception: Database errors are logged but not re-raised (graceful degradation)

    Example:
        >>> engine = create_engine("postgresql://...")
        >>> record = {"id": 123, "fecha_inicio": "2025-01-01", ...}
        >>> await upsert_raw_event(engine, record, kind="audiencia")
    """
    try:
        # Derive external ID (required)
        external_id = derive_external_id(record, kind)

        # Derive optional fields (best-effort)
        fecha = derive_fecha(record, kind)
        monto = derive_monto(record, kind)
        institucion = derive_institucion(record, kind)
        destino = derive_destino(record, kind)

        # Prepare payload
        now = datetime.now(timezone.utc)
        payload = {
            "id": str(uuid4()),
            "externalId": external_id,
            "tenantCode": tenant_code,
            "kind": kind,
            "rawData": json.dumps(record),  # Store as JSON string
            "fecha": fecha,
            "monto": monto,
            "institucion": institucion,
            "destino": destino,
            "createdAt": now,
            "updatedAt": now,
        }

        # Create upsert statement
        stmt = insert(lobby_event_raw_table).values(**payload)

        # On conflict, update rawData and derived fields (plus updatedAt)
        stmt = stmt.on_conflict_do_update(
            index_elements=["externalId"],
            set_={
                "rawData": stmt.excluded.rawData,
                "fecha": stmt.excluded.fecha,
                "monto": stmt.excluded.monto,
                "institucion": stmt.excluded.institucion,
                "destino": stmt.excluded.destino,
                "updatedAt": text("CURRENT_TIMESTAMP"),
            },
        )

        # Execute upsert
        with engine.connect() as conn:
            conn.execute(stmt)
            conn.commit()

        logger.info(
            f"Upserted {kind} event: external_id={external_id}, "
            f"fecha={fecha}, tenant={tenant_code}"
        )

    except ValueError as e:
        # Cannot derive external ID - log and skip
        logger.warning(f"Skipping {kind} record: {e}")
        return

    except Exception as e:
        # Database or other errors - log but don't crash
        logger.error(
            f"Failed to upsert {kind} event: error={str(e)}, "
            f"error_type={type(e).__name__}"
        )
        # Don't re-raise - graceful degradation
        return
