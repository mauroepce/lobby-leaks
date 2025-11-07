"""
Tests for raw event persistence functionality.

Tests upsert operations, derived fields, and idempotent behavior using fixtures.
"""

import json
import os
import pytest
from decimal import Decimal
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from sqlalchemy import create_engine, text

from services.lobby_collector.persistence import upsert_raw_event
from services.lobby_collector.derivers import (
    derive_external_id,
    derive_fecha,
    derive_monto,
    derive_institucion,
    derive_destino,
)


# Fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(filename: str) -> Dict[str, Any]:
    """Load JSON fixture from file."""
    with open(FIXTURES_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def db_url():
    """Get database URL from environment or use test default."""
    return os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/lobbyleaks_test")


@pytest.fixture
def engine(db_url):
    """Create SQLAlchemy engine for tests."""
    return create_engine(db_url)


@pytest.fixture
def clean_db(engine):
    """Clean LobbyEventRaw table before each test."""
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE \"LobbyEventRaw\" CASCADE"))
        conn.commit()
    yield
    # Cleanup after test
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE \"LobbyEventRaw\" CASCADE"))
        conn.commit()


class TestDerivers:
    """Test field derivation helpers."""

    def test_derive_external_id_audiencia(self):
        """Test external ID derivation for audiencia."""
        record = load_fixture("audiencia_sample.json")
        external_id = derive_external_id(record, "audiencia")

        assert external_id.startswith("audiencia:")
        assert "mario" in external_id.lower()
        assert "marcel" in external_id.lower()
        assert "2025-01-15" in external_id

    def test_derive_external_id_viaje(self):
        """Test external ID derivation for viaje."""
        record = load_fixture("viaje_sample.json")
        external_id = derive_external_id(record, "viaje")

        assert external_id.startswith("viaje:")
        assert "carolina" in external_id.lower()
        assert "2025-02-10" in external_id

    def test_derive_external_id_donativo(self):
        """Test external ID derivation for donativo."""
        record = load_fixture("donativo_sample.json")
        external_id = derive_external_id(record, "donativo")

        assert external_id.startswith("donativo:")
        assert "rodrigo" in external_id.lower()
        assert "2025-01-20" in external_id

    def test_derive_external_id_with_explicit_id(self):
        """Test external ID when record has explicit 'id' field."""
        record = {"id": 12345, "nombres": "Test", "apellidos": "User"}
        external_id = derive_external_id(record, "audiencia")

        assert external_id == "audiencia:12345"

    def test_derive_external_id_hash_fallback(self):
        """Test hash fallback when key fields are missing."""
        record = {"some": "data", "without": "key_fields"}
        external_id = derive_external_id(record, "audiencia")

        assert external_id.startswith("audiencia:hash_")
        assert len(external_id) > len("audiencia:hash_")

    def test_derive_fecha_audiencia(self):
        """Test fecha derivation for audiencia."""
        record = load_fixture("audiencia_sample.json")
        fecha = derive_fecha(record, "audiencia")

        assert fecha is not None
        assert fecha.year == 2025
        assert fecha.month == 1
        assert fecha.day == 15
        assert fecha.hour == 10

    def test_derive_fecha_viaje(self):
        """Test fecha derivation for viaje."""
        record = load_fixture("viaje_sample.json")
        fecha = derive_fecha(record, "viaje")

        assert fecha is not None
        assert fecha.year == 2025
        assert fecha.month == 2
        assert fecha.day == 10

    def test_derive_fecha_donativo(self):
        """Test fecha derivation for donativo."""
        record = load_fixture("donativo_sample.json")
        fecha = derive_fecha(record, "donativo")

        assert fecha is not None
        assert fecha.year == 2025
        assert fecha.month == 1
        assert fecha.day == 20

    def test_derive_fecha_missing(self):
        """Test fecha derivation with missing date field."""
        record = {"nombres": "Test"}
        fecha = derive_fecha(record, "audiencia")

        assert fecha is None

    def test_derive_monto_viaje(self):
        """Test monto derivation for viaje (should be None)."""
        record = load_fixture("viaje_sample.json")
        monto = derive_monto(record, "viaje")

        assert monto is None  # Viajes don't have monto in main record

    def test_derive_monto_donativo_missing(self):
        """Test monto derivation for donativo (no monto field in API)."""
        record = load_fixture("donativo_sample.json")
        monto = derive_monto(record, "donativo")

        assert monto is None  # Donativos don't have monetary value in API response

    def test_derive_institucion_audiencia(self):
        """Test institucion derivation for audiencia."""
        record = load_fixture("audiencia_sample.json")
        record["sujeto_pasivo"] = "Ministerio de Hacienda"
        institucion = derive_institucion(record, "audiencia")

        assert institucion == "Ministerio de Hacienda"

    def test_derive_institucion_from_nested(self):
        """Test institucion derivation from nested object."""
        record = load_fixture("viaje_sample.json")
        institucion = derive_institucion(record, "viaje")

        assert institucion == "Ministerio del Interior y Seguridad Pública"

    def test_derive_destino_viaje(self):
        """Test destino derivation for viaje."""
        record = load_fixture("viaje_sample.json")
        destino = derive_destino(record, "viaje")

        assert destino == "París, Francia"

    def test_derive_destino_audiencia(self):
        """Test destino derivation for audiencia (should be None)."""
        record = load_fixture("audiencia_sample.json")
        destino = derive_destino(record, "audiencia")

        assert destino is None


@pytest.mark.asyncio
class TestPersistence:
    """Test raw event persistence operations."""

    async def test_insert_new_audiencia(self, engine, clean_db):
        """Test inserting a new audiencia record."""
        record = load_fixture("audiencia_sample.json")

        await upsert_raw_event(engine, record, kind="audiencia", tenant_code="CL")

        # Verify insertion
        with engine.connect() as conn:
            result = conn.execute(
                text('SELECT * FROM "LobbyEventRaw" WHERE kind = :kind'),
                {"kind": "audiencia"}
            )
            row = result.fetchone()

        assert row is not None
        assert row.kind == "audiencia"
        assert row.tenantCode == "CL"
        assert "mario" in row.externalId.lower()

    async def test_insert_new_viaje(self, engine, clean_db):
        """Test inserting a new viaje record."""
        record = load_fixture("viaje_sample.json")

        await upsert_raw_event(engine, record, kind="viaje", tenant_code="CL")

        # Verify insertion
        with engine.connect() as conn:
            result = conn.execute(
                text('SELECT * FROM "LobbyEventRaw" WHERE kind = :kind'),
                {"kind": "viaje"}
            )
            row = result.fetchone()

        assert row is not None
        assert row.kind == "viaje"
        assert row.destino == "París, Francia"

    async def test_insert_new_donativo(self, engine, clean_db):
        """Test inserting a new donativo record."""
        record = load_fixture("donativo_sample.json")

        await upsert_raw_event(engine, record, kind="donativo", tenant_code="CL")

        # Verify insertion
        with engine.connect() as conn:
            result = conn.execute(
                text('SELECT * FROM "LobbyEventRaw" WHERE kind = :kind'),
                {"kind": "donativo"}
            )
            row = result.fetchone()

        assert row is not None
        assert row.kind == "donativo"
        assert row.tenantCode == "CL"

    async def test_upsert_idempotent(self, engine, clean_db):
        """Test that upserting same record twice updates instead of duplicating."""
        record = load_fixture("audiencia_sample.json")

        # First insert
        await upsert_raw_event(engine, record, kind="audiencia")

        # Second insert (should update)
        record_modified = record.copy()
        record_modified["referencia"] = "UPDATED: New reference text"
        await upsert_raw_event(engine, record_modified, kind="audiencia")

        # Verify only one record exists
        with engine.connect() as conn:
            result = conn.execute(
                text('SELECT COUNT(*) as cnt FROM "LobbyEventRaw"')
            )
            count = result.fetchone().cnt

        assert count == 1

        # Verify rawData was updated
        with engine.connect() as conn:
            result = conn.execute(
                text('SELECT "rawData" FROM "LobbyEventRaw" WHERE kind = :kind'),
                {"kind": "audiencia"}
            )
            row = result.fetchone()
            raw_data = json.loads(row.rawData)

        assert raw_data["referencia"] == "UPDATED: New reference text"

    async def test_upsert_updates_updatedAt(self, engine, clean_db):
        """Test that upsert updates the updatedAt timestamp."""
        import time

        record = load_fixture("audiencia_sample.json")

        # First insert
        await upsert_raw_event(engine, record, kind="audiencia")

        # Get initial updatedAt
        with engine.connect() as conn:
            result = conn.execute(
                text('SELECT "updatedAt" FROM "LobbyEventRaw"')
            )
            first_updated_at = result.fetchone().updatedAt

        # Wait a bit
        time.sleep(1)

        # Second insert (update)
        await upsert_raw_event(engine, record, kind="audiencia")

        # Get new updatedAt
        with engine.connect() as conn:
            result = conn.execute(
                text('SELECT "updatedAt" FROM "LobbyEventRaw"')
            )
            second_updated_at = result.fetchone().updatedAt

        assert second_updated_at > first_updated_at

    async def test_derived_fields_stored(self, engine, clean_db):
        """Test that derived fields are correctly stored."""
        record = load_fixture("audiencia_sample.json")

        await upsert_raw_event(engine, record, kind="audiencia")

        with engine.connect() as conn:
            result = conn.execute(
                text('SELECT * FROM "LobbyEventRaw"')
            )
            row = result.fetchone()

        assert row.fecha is not None
        assert row.fecha.year == 2025
        assert row.fecha.month == 1

    async def test_multiple_kinds(self, engine, clean_db):
        """Test inserting different kinds of events."""
        audiencia = load_fixture("audiencia_sample.json")
        viaje = load_fixture("viaje_sample.json")
        donativo = load_fixture("donativo_sample.json")

        await upsert_raw_event(engine, audiencia, kind="audiencia")
        await upsert_raw_event(engine, viaje, kind="viaje")
        await upsert_raw_event(engine, donativo, kind="donativo")

        # Verify all three exist
        with engine.connect() as conn:
            result = conn.execute(
                text('SELECT kind, COUNT(*) as cnt FROM "LobbyEventRaw" GROUP BY kind')
            )
            counts = {row.kind: row.cnt for row in result}

        assert counts["audiencia"] == 1
        assert counts["viaje"] == 1
        assert counts["donativo"] == 1

    async def test_tenant_isolation(self, engine, clean_db):
        """Test that records respect tenant_code."""
        record = load_fixture("audiencia_sample.json")

        await upsert_raw_event(engine, record, kind="audiencia", tenant_code="CL")

        with engine.connect() as conn:
            result = conn.execute(
                text('SELECT "tenantCode" FROM "LobbyEventRaw"')
            )
            row = result.fetchone()

        assert row.tenantCode == "CL"
