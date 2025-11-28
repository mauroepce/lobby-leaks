"""
Tests for lobby_events_staging VIEW.

Verifies that the staging view correctly derives and normalizes fields
from the raw LobbyEventRaw table for different event kinds.
"""

import json
import os
import pytest
from pathlib import Path
from typing import Dict, Any

from sqlalchemy import create_engine, text

from services.lobby_collector.persistence import upsert_raw_event
from services.lobby_collector.derivers import derive_external_id


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


@pytest.mark.asyncio
class TestStagingViewStructure:
    """Test that the staging view exists and has correct structure."""

    async def test_staging_view_exists(self, engine):
        """Verify that lobby_events_staging view exists."""
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT EXISTS (
                        SELECT FROM pg_views
                        WHERE viewname = 'lobby_events_staging'
                    )
                """)
            )
            exists = result.fetchone()[0]

        assert exists, "lobby_events_staging view does not exist"

    async def test_staging_view_has_required_columns(self, engine):
        """Verify view has all required columns."""
        required_columns = [
            "id", "externalId", "tenantCode", "kind",
            "nombres", "apellidos", "nombresCompletos", "cargo",
            "fecha", "year", "month",
            "institucion", "destino", "monto",
            "rawDataHash", "rawDataSize",
            "createdAt", "updatedAt"
        ]

        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'lobby_events_staging'
                """)
            )
            actual_columns = [row[0] for row in result]

        for col in required_columns:
            assert col in actual_columns, f"Missing column: {col}"


@pytest.mark.asyncio
class TestStagingViewAudiencias:
    """Test staging view derivation for audiencias."""

    async def test_audiencia_basic_fields(self, engine, clean_db):
        """Test that basic fields are correctly extracted for audiencia."""
        record = load_fixture("audiencia_sample.json")
        await upsert_raw_event(engine, record, kind="audiencia", tenant_code="CL")

        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT * FROM lobby_events_staging WHERE kind = 'audiencia'")
            )
            row = result.fetchone()

        assert row is not None
        assert row.kind == "audiencia"
        assert row.nombres == "Mario"
        assert row.apellidos == "Marcel Cullell"
        assert row.nombresCompletos == "Mario Marcel Cullell"
        assert row.cargo == "Ministro de Hacienda"

    async def test_audiencia_temporal_fields(self, engine, clean_db):
        """Test temporal field extraction for audiencia."""
        record = load_fixture("audiencia_sample.json")
        await upsert_raw_event(engine, record, kind="audiencia")

        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT fecha, year, month FROM lobby_events_staging WHERE kind = 'audiencia'")
            )
            row = result.fetchone()

        assert row.fecha is not None
        assert row.year == 2025
        assert row.month == 1

    async def test_audiencia_institucion_extraction(self, engine, clean_db):
        """Test that institucion is correctly extracted from sujeto_pasivo."""
        record = load_fixture("audiencia_sample.json")
        record["sujeto_pasivo"] = "Ministerio de Hacienda"
        await upsert_raw_event(engine, record, kind="audiencia")

        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT institucion FROM lobby_events_staging WHERE kind = 'audiencia'")
            )
            row = result.fetchone()

        assert row.institucion == "Ministerio de Hacienda"

    async def test_audiencia_destino_is_null(self, engine, clean_db):
        """Audiencias should have NULL destino (only viajes have destino)."""
        record = load_fixture("audiencia_sample.json")
        await upsert_raw_event(engine, record, kind="audiencia")

        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT destino FROM lobby_events_staging WHERE kind = 'audiencia'")
            )
            row = result.fetchone()

        assert row.destino is None


@pytest.mark.asyncio
class TestStagingViewViajes:
    """Test staging view derivation for viajes."""

    async def test_viaje_basic_fields(self, engine, clean_db):
        """Test basic field extraction for viaje."""
        record = load_fixture("viaje_sample.json")
        await upsert_raw_event(engine, record, kind="viaje")

        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT * FROM lobby_events_staging WHERE kind = 'viaje'")
            )
            row = result.fetchone()

        assert row is not None
        assert row.kind == "viaje"
        assert row.nombres == "Carolina"
        assert row.apellidos == "Tohá Morales"
        assert row.nombresCompletos == "Carolina Tohá Morales"

    async def test_viaje_destino_extraction(self, engine, clean_db):
        """Test destino extraction for viaje."""
        record = load_fixture("viaje_sample.json")
        await upsert_raw_event(engine, record, kind="viaje")

        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT destino FROM lobby_events_staging WHERE kind = 'viaje'")
            )
            row = result.fetchone()

        assert row.destino == "París, Francia"

    async def test_viaje_institucion_from_nested(self, engine, clean_db):
        """Test institucion extraction from nested object for viaje."""
        record = load_fixture("viaje_sample.json")
        await upsert_raw_event(engine, record, kind="viaje")

        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT institucion FROM lobby_events_staging WHERE kind = 'viaje'")
            )
            row = result.fetchone()

        assert row.institucion == "Ministerio del Interior y Seguridad Pública"


@pytest.mark.asyncio
class TestStagingViewDonativos:
    """Test staging view derivation for donativos."""

    async def test_donativo_basic_fields(self, engine, clean_db):
        """Test basic field extraction for donativo."""
        record = load_fixture("donativo_sample.json")
        await upsert_raw_event(engine, record, kind="donativo")

        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT * FROM lobby_events_staging WHERE kind = 'donativo'")
            )
            row = result.fetchone()

        assert row is not None
        assert row.kind == "donativo"
        assert row.nombres == "Rodrigo"
        assert row.apellidos == "Delgado Mocarquer"

    async def test_donativo_temporal_fields(self, engine, clean_db):
        """Test temporal fields for donativo."""
        record = load_fixture("donativo_sample.json")
        await upsert_raw_event(engine, record, kind="donativo")

        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT year, month FROM lobby_events_staging WHERE kind = 'donativo'")
            )
            row = result.fetchone()

        assert row.year == 2025
        assert row.month == 1


@pytest.mark.asyncio
class TestStagingViewMetadata:
    """Test metadata fields (hash, size)."""

    async def test_raw_data_hash_generated(self, engine, clean_db):
        """Test that rawDataHash is generated for each record."""
        record = load_fixture("audiencia_sample.json")
        await upsert_raw_event(engine, record, kind="audiencia")

        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT \"rawDataHash\" FROM lobby_events_staging")
            )
            row = result.fetchone()

        assert row.rawDataHash is not None
        assert len(row.rawDataHash) == 64  # SHA256 produces 64 hex chars

    async def test_raw_data_hash_unique_per_record(self, engine, clean_db):
        """Test that different records have different hashes."""
        audiencia = load_fixture("audiencia_sample.json")
        viaje = load_fixture("viaje_sample.json")

        await upsert_raw_event(engine, audiencia, kind="audiencia")
        await upsert_raw_event(engine, viaje, kind="viaje")

        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT \"rawDataHash\" FROM lobby_events_staging")
            )
            hashes = [row[0] for row in result]

        assert len(hashes) == 2
        assert hashes[0] != hashes[1]

    async def test_raw_data_size_calculated(self, engine, clean_db):
        """Test that rawDataSize is calculated."""
        record = load_fixture("audiencia_sample.json")
        await upsert_raw_event(engine, record, kind="audiencia")

        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT \"rawDataSize\" FROM lobby_events_staging")
            )
            row = result.fetchone()

        assert row.rawDataSize is not None
        assert row.rawDataSize > 0


@pytest.mark.asyncio
class TestStagingViewConsistency:
    """Test consistency between raw table and staging view."""

    async def test_staging_count_matches_raw(self, engine, clean_db):
        """Verify that staging view has same record count as raw table."""
        audiencia = load_fixture("audiencia_sample.json")
        viaje = load_fixture("viaje_sample.json")
        donativo = load_fixture("donativo_sample.json")

        await upsert_raw_event(engine, audiencia, kind="audiencia")
        await upsert_raw_event(engine, viaje, kind="viaje")
        await upsert_raw_event(engine, donativo, kind="donativo")

        with engine.connect() as conn:
            raw_count = conn.execute(
                text("SELECT COUNT(*) FROM \"LobbyEventRaw\"")
            ).fetchone()[0]

            staging_count = conn.execute(
                text("SELECT COUNT(*) FROM lobby_events_staging")
            ).fetchone()[0]

        assert raw_count == staging_count == 3

    async def test_staging_external_ids_match_raw(self, engine, clean_db):
        """Verify that all externalIds in staging exist in raw."""
        records = [
            (load_fixture("audiencia_sample.json"), "audiencia"),
            (load_fixture("viaje_sample.json"), "viaje"),
            (load_fixture("donativo_sample.json"), "donativo"),
        ]

        for record, kind in records:
            await upsert_raw_event(engine, record, kind=kind)

        with engine.connect() as conn:
            raw_ids = conn.execute(
                text("SELECT \"externalId\" FROM \"LobbyEventRaw\"")
            )
            raw_set = {row[0] for row in raw_ids}

            staging_ids = conn.execute(
                text("SELECT \"externalId\" FROM lobby_events_staging")
            )
            staging_set = {row[0] for row in staging_ids}

        assert raw_set == staging_set

    async def test_staging_handles_multiple_kinds(self, engine, clean_db):
        """Test that view correctly handles all three kinds."""
        audiencia = load_fixture("audiencia_sample.json")
        viaje = load_fixture("viaje_sample.json")
        donativo = load_fixture("donativo_sample.json")

        await upsert_raw_event(engine, audiencia, kind="audiencia")
        await upsert_raw_event(engine, viaje, kind="viaje")
        await upsert_raw_event(engine, donativo, kind="donativo")

        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT kind, COUNT(*) as cnt FROM lobby_events_staging GROUP BY kind")
            )
            counts = {row.kind: row.cnt for row in result}

        assert counts["audiencia"] == 1
        assert counts["viaje"] == 1
        assert counts["donativo"] == 1


@pytest.mark.asyncio
class TestStagingViewQueries:
    """Test common query patterns on staging view."""

    async def test_query_by_year(self, engine, clean_db):
        """Test querying by year."""
        audiencia = load_fixture("audiencia_sample.json")
        await upsert_raw_event(engine, audiencia, kind="audiencia")

        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT COUNT(*) FROM lobby_events_staging WHERE year = 2025")
            )
            count = result.fetchone()[0]

        assert count == 1

    async def test_query_by_kind_and_month(self, engine, clean_db):
        """Test querying by kind and month."""
        audiencia = load_fixture("audiencia_sample.json")
        donativo = load_fixture("donativo_sample.json")

        await upsert_raw_event(engine, audiencia, kind="audiencia")
        await upsert_raw_event(engine, donativo, kind="donativo")

        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT COUNT(*)
                    FROM lobby_events_staging
                    WHERE kind = 'audiencia' AND month = 1
                """)
            )
            count = result.fetchone()[0]

        assert count == 1

    async def test_query_by_institucion(self, engine, clean_db):
        """Test querying by institucion."""
        viaje = load_fixture("viaje_sample.json")
        await upsert_raw_event(engine, viaje, kind="viaje")

        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT COUNT(*)
                    FROM lobby_events_staging
                    WHERE institucion LIKE '%Interior%'
                """)
            )
            count = result.fetchone()[0]

        assert count == 1
