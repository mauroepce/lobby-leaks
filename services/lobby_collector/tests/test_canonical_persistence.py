"""
Tests for canonical entity persistence (idempotent UPSERT).
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine, text
from services.lobby_collector.canonical_persistence import upsert_canonical
from services.lobby_collector.canonical_mapper import EntityBundle


@pytest.fixture
def engine():
    """Create test database engine."""
    import os
    database_url = os.getenv("DATABASE_URL")
    return create_engine(database_url)


@pytest.fixture
def clean_canonical_db(engine):
    """Clean canonical tables before each test."""
    with engine.begin() as conn:
        # Delete in correct order (respect foreign keys)
        conn.execute(text('DELETE FROM "Edge"'))
        conn.execute(text('DELETE FROM "Event"'))
        conn.execute(text('DELETE FROM "Person"'))
        conn.execute(text('DELETE FROM "Organisation"'))
    yield
    # Cleanup after test
    with engine.begin() as conn:
        conn.execute(text('DELETE FROM "Edge"'))
        conn.execute(text('DELETE FROM "Event"'))
        conn.execute(text('DELETE FROM "Person"'))
        conn.execute(text('DELETE FROM "Organisation"'))


class TestUpsertPerson:
    """Test Person UPSERT logic."""

    def test_insert_new_person(self, engine, clean_canonical_db):
        """Test inserting a new person."""
        bundle = EntityBundle()
        bundle.add_person(
            tenant_code="CL",
            nombres="Juan",
            apellidos="Pérez",
            cargo="Senador",
            rut="123456785",
        )
        bundle.add_event("CL", "E-001", "audiencia")

        stats = upsert_canonical(engine, bundle)

        assert stats["persons_created"] == 1
        assert stats["persons_updated"] == 0

        # Verify in database
        with engine.connect() as conn:
            result = conn.execute(text('SELECT COUNT(*) FROM "Person"'))
            assert result.fetchone()[0] == 1

            result = conn.execute(text("""
                SELECT nombres, apellidos, cargo, rut
                FROM "Person"
                WHERE "tenantCode" = 'CL'
            """))
            row = result.fetchone()
            assert row[0] == "Juan"
            assert row[1] == "Pérez"
            assert row[2] == "Senador"
            assert row[3] == "123456785"

    def test_upsert_existing_person_by_rut(self, engine, clean_canonical_db):
        """Test updating existing person matched by RUT."""
        bundle = EntityBundle()
        bundle.add_person("CL", "Juan", "Pérez", "Senador", "123456785")
        bundle.add_event("CL", "E-001", "audiencia")

        # First insert
        stats1 = upsert_canonical(engine, bundle)
        assert stats1["persons_created"] == 1

        # Second insert with same RUT but different cargo
        bundle2 = EntityBundle()
        bundle2.add_person("CL", "Juan Carlos", "Pérez García", "Diputado", "123456785")
        bundle2.add_event("CL", "E-002", "audiencia")

        stats2 = upsert_canonical(engine, bundle2)
        assert stats2["persons_created"] == 0
        assert stats2["persons_updated"] == 1

        # Verify only one person exists
        with engine.connect() as conn:
            result = conn.execute(text('SELECT COUNT(*) FROM "Person"'))
            assert result.fetchone()[0] == 1

            # Verify updated fields
            result = conn.execute(text("""
                SELECT nombres, apellidos, cargo
                FROM "Person"
                WHERE rut = '123456785'
            """))
            row = result.fetchone()
            assert row[0] == "Juan Carlos"
            assert row[1] == "Pérez García"
            assert row[2] == "Diputado"

    def test_upsert_existing_person_by_normalized_name(self, engine, clean_canonical_db):
        """Test updating existing person matched by normalizedName."""
        bundle = EntityBundle()
        bundle.add_person("CL", "María", "González", "Diputada", None)
        bundle.add_event("CL", "E-001", "audiencia")

        # First insert without RUT
        stats1 = upsert_canonical(engine, bundle)
        assert stats1["persons_created"] == 1

        # Second insert with same name but now with RUT
        bundle2 = EntityBundle()
        bundle2.add_person("CL", "María", "González", "Senadora", "987654321")
        bundle2.add_event("CL", "E-002", "audiencia")

        stats2 = upsert_canonical(engine, bundle2)
        assert stats2["persons_created"] == 0
        assert stats2["persons_updated"] == 1

        # Verify only one person exists with RUT added
        with engine.connect() as conn:
            result = conn.execute(text('SELECT COUNT(*) FROM "Person"'))
            assert result.fetchone()[0] == 1

            result = conn.execute(text("""
                SELECT cargo, rut
                FROM "Person"
                WHERE "normalizedName" = 'maría gonzález'
            """))
            row = result.fetchone()
            assert row[0] == "Senadora"
            assert row[1] == "987654321"


class TestUpsertOrganisation:
    """Test Organisation UPSERT logic."""

    def test_insert_new_organisation(self, engine, clean_canonical_db):
        """Test inserting a new organisation."""
        bundle = EntityBundle()
        bundle.add_organisation("CL", "Ministerio de Hacienda", "ministerio")
        bundle.add_event("CL", "E-001", "audiencia")

        stats = upsert_canonical(engine, bundle)

        assert stats["orgs_created"] == 1
        assert stats["orgs_updated"] == 0

        with engine.connect() as conn:
            result = conn.execute(text('SELECT COUNT(*) FROM "Organisation"'))
            assert result.fetchone()[0] == 1

    def test_upsert_existing_organisation_by_name(self, engine, clean_canonical_db):
        """Test updating existing organisation matched by normalizedName."""
        bundle = EntityBundle()
        bundle.add_organisation("CL", "Ministerio de Hacienda", "ministerio")
        bundle.add_event("CL", "E-001", "audiencia")

        stats1 = upsert_canonical(engine, bundle)
        assert stats1["orgs_created"] == 1

        # Second insert with same name but different tipo
        bundle2 = EntityBundle()
        bundle2.add_organisation("CL", "Ministerio de Hacienda", "otro")
        bundle2.add_event("CL", "E-002", "audiencia")

        stats2 = upsert_canonical(engine, bundle2)
        assert stats2["orgs_created"] == 0
        assert stats2["orgs_updated"] == 1

        # Verify only one org exists
        with engine.connect() as conn:
            result = conn.execute(text('SELECT COUNT(*) FROM "Organisation"'))
            assert result.fetchone()[0] == 1


class TestUpsertEvent:
    """Test Event UPSERT logic."""

    def test_insert_new_event(self, engine, clean_canonical_db):
        """Test inserting a new event."""
        bundle = EntityBundle()
        bundle.add_event(
            tenant_code="CL",
            external_id="AUD-2023-001",
            kind="audiencia",
            fecha=datetime(2023, 5, 15),
            descripcion="Reunión presupuesto",
        )

        stats = upsert_canonical(engine, bundle)

        assert stats["events_created"] == 1
        assert stats["events_updated"] == 0

        with engine.connect() as conn:
            result = conn.execute(text('SELECT COUNT(*) FROM "Event"'))
            assert result.fetchone()[0] == 1

    def test_upsert_existing_event(self, engine, clean_canonical_db):
        """Test updating existing event matched by (tenantCode, externalId, kind)."""
        bundle = EntityBundle()
        bundle.add_event("CL", "AUD-2023-001", "audiencia", None, "Original")

        stats1 = upsert_canonical(engine, bundle)
        assert stats1["events_created"] == 1

        # Second insert with same natural key but different descripcion
        bundle2 = EntityBundle()
        bundle2.add_event("CL", "AUD-2023-001", "audiencia", None, "Updated")

        stats2 = upsert_canonical(engine, bundle2)
        assert stats2["events_created"] == 0
        assert stats2["events_updated"] == 1

        # Verify only one event exists
        with engine.connect() as conn:
            result = conn.execute(text('SELECT COUNT(*) FROM "Event"'))
            assert result.fetchone()[0] == 1

            result = conn.execute(text("""
                SELECT descripcion
                FROM "Event"
                WHERE "externalId" = 'AUD-2023-001'
            """))
            row = result.fetchone()
            assert row[0] == "Updated"


class TestUpsertEdge:
    """Test Edge UPSERT logic."""

    def test_insert_new_edge(self, engine, clean_canonical_db):
        """Test inserting a new edge."""
        bundle = EntityBundle()
        person_id = bundle.add_person("CL", "Juan", "Pérez")
        org_id = bundle.add_organisation("CL", "Ministerio")
        event_id = bundle.add_event("CL", "E-001", "audiencia")
        bundle.add_edge(
            tenant_code="CL",
            event_id=event_id,
            label="MEETS",
            from_person_id=person_id,
            to_org_id=org_id,
        )

        stats = upsert_canonical(engine, bundle)

        assert stats["edges_created"] == 1
        assert stats["edges_updated"] == 0

        with engine.connect() as conn:
            result = conn.execute(text('SELECT COUNT(*) FROM "Edge"'))
            assert result.fetchone()[0] == 1

    def test_upsert_existing_edge(self, engine, clean_canonical_db):
        """Test updating existing edge (idempotency)."""
        bundle = EntityBundle()
        person_id = bundle.add_person("CL", "Juan", "Pérez")
        org_id = bundle.add_organisation("CL", "Ministerio")
        event_id = bundle.add_event("CL", "E-001", "audiencia")
        bundle.add_edge(
            tenant_code="CL",
            event_id=event_id,
            label="MEETS",
            from_person_id=person_id,
            to_org_id=org_id,
            metadata={"cargo": "Senador"},
        )

        stats1 = upsert_canonical(engine, bundle)
        assert stats1["edges_created"] == 1

        # Second insert with same edge
        bundle2 = EntityBundle()
        person_id2 = bundle2.add_person("CL", "Juan", "Pérez")
        org_id2 = bundle2.add_organisation("CL", "Ministerio")
        event_id2 = bundle2.add_event("CL", "E-001", "audiencia")
        bundle2.add_edge(
            tenant_code="CL",
            event_id=event_id2,
            label="MEETS",
            from_person_id=person_id2,
            to_org_id=org_id2,
            metadata={"cargo": "Diputado"},
        )

        stats2 = upsert_canonical(engine, bundle2)
        assert stats2["edges_created"] == 0
        assert stats2["edges_updated"] == 1

        # Verify only one edge exists
        with engine.connect() as conn:
            result = conn.execute(text('SELECT COUNT(*) FROM "Edge"'))
            assert result.fetchone()[0] == 1


class TestEndToEnd:
    """Test complete end-to-end flows."""

    def test_complete_audiencia_flow(self, engine, clean_canonical_db):
        """Test complete flow: audiencia with Person MEETS Org."""
        bundle = EntityBundle()
        person_id = bundle.add_person("CL", "Juan", "Pérez", "Senador", "123456785")
        org_id = bundle.add_organisation("CL", "Ministerio de Hacienda", "ministerio")
        event_id = bundle.add_event("CL", "AUD-2023-001", "audiencia", datetime(2023, 5, 15))
        bundle.add_edge(
            tenant_code="CL",
            event_id=event_id,
            label="MEETS",
            from_person_id=person_id,
            to_org_id=org_id,
        )

        stats = upsert_canonical(engine, bundle)

        assert stats["persons_created"] == 1
        assert stats["orgs_created"] == 1
        assert stats["events_created"] == 1
        assert stats["edges_created"] == 1

        # Verify complete graph in database
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    p.nombres,
                    o.name,
                    e.kind,
                    edge.label
                FROM "Edge" edge
                JOIN "Person" p ON edge."fromPersonId" = p.id
                JOIN "Organisation" o ON edge."toOrgId" = o.id
                JOIN "Event" e ON edge."eventId" = e.id
            """))
            row = result.fetchone()
            assert row[0] == "Juan"
            assert row[1] == "Ministerio de Hacienda"
            assert row[2] == "audiencia"
            assert row[3] == "MEETS"

    def test_idempotency_full_flow(self, engine, clean_canonical_db):
        """Test that running same bundle twice doesn't create duplicates."""
        bundle = EntityBundle()
        person_id = bundle.add_person("CL", "María", "González", rut="987654321")
        org_id = bundle.add_organisation("CL", "Empresa S.A.")
        event_id = bundle.add_event("CL", "DON-2023-001", "donativo")
        bundle.add_edge(
            tenant_code="CL",
            event_id=event_id,
            label="CONTRIBUTES",
            from_org_id=org_id,
            to_person_id=person_id,
        )

        # First run
        stats1 = upsert_canonical(engine, bundle)
        assert stats1["persons_created"] == 1
        assert stats1["orgs_created"] == 1
        assert stats1["events_created"] == 1
        assert stats1["edges_created"] == 1

        # Second run (idempotency test)
        stats2 = upsert_canonical(engine, bundle)
        assert stats2["persons_created"] == 0
        assert stats2["persons_updated"] == 1
        assert stats2["orgs_created"] == 0
        assert stats2["orgs_updated"] == 1
        assert stats2["events_created"] == 0
        assert stats2["events_updated"] == 1
        assert stats2["edges_created"] == 0
        assert stats2["edges_updated"] == 1

        # Verify counts haven't changed
        with engine.connect() as conn:
            result = conn.execute(text('SELECT COUNT(*) FROM "Person"'))
            assert result.fetchone()[0] == 1

            result = conn.execute(text('SELECT COUNT(*) FROM "Organisation"'))
            assert result.fetchone()[0] == 1

            result = conn.execute(text('SELECT COUNT(*) FROM "Event"'))
            assert result.fetchone()[0] == 1

            result = conn.execute(text('SELECT COUNT(*) FROM "Edge"'))
            assert result.fetchone()[0] == 1
