"""
Integration tests for v_donations_graph view semantics.

These tests verify the data semantics and transformations in
the v_donations_graph view.

Requires DATABASE_URL environment variable.
"""

import json
import pytest
import uuid
from datetime import datetime, timezone
from sqlalchemy import text


# ============================================================================
# View Semantics Tests
# ============================================================================


@pytest.mark.integration
class TestDonationsViewSemantics:
    """Tests for v_donations_graph view semantics."""

    @pytest.fixture
    def test_tenant_code(self):
        """Test tenant code for isolation."""
        return f"TEST_{uuid.uuid4().hex[:8]}"

    @pytest.fixture
    def cleanup(self, engine, test_tenant_code):
        """Cleanup test data after test."""
        yield
        # Cleanup test data
        with engine.begin() as conn:
            conn.execute(text(
                'DELETE FROM "Edge" WHERE "tenantCode" = :tenant_code'
            ), {"tenant_code": test_tenant_code})
            conn.execute(text(
                'DELETE FROM "Event" WHERE "tenantCode" = :tenant_code'
            ), {"tenant_code": test_tenant_code})
            conn.execute(text(
                'DELETE FROM "Person" WHERE "tenantCode" = :tenant_code'
            ), {"tenant_code": test_tenant_code})

    def test_donation_event_appears_in_view(self, engine, test_tenant_code, cleanup):
        """Donation event with candidate edge appears in view."""
        event_id = str(uuid.uuid4())
        candidate_id = str(uuid.uuid4())
        edge_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        unique_suffix = uuid.uuid4().hex[:8]

        with engine.begin() as conn:
            # Create candidate person (unique name per test run)
            conn.execute(text("""
                INSERT INTO "Person" (id, "tenantCode", "normalizedName", nombres, apellidos, "nombresCompletos", "createdAt", "updatedAt")
                VALUES (:id, :tenant_code, :normalized_name, :nombres, :apellidos, :nombres_completos, :now, :now)
            """), {
                "id": candidate_id,
                "tenant_code": test_tenant_code,
                "normalized_name": f"test candidate {unique_suffix}",
                "nombres": "Test",
                "apellidos": "Candidate",
                "nombres_completos": "Test Candidate",
                "now": now,
            })

            # Create donation event
            metadata = json.dumps({
                "source": "servel",
                "amount": 1000000,
                "campaign_year": 2021,
                "candidate_name": "Test Candidate",
            })
            conn.execute(text("""
                INSERT INTO "Event" (id, "tenantCode", "externalId", kind, date, metadata, "createdAt", "updatedAt")
                VALUES (:id, :tenant_code, :external_id, 'donation', :date, CAST(:metadata AS JSONB), :now, :now)
            """), {
                "id": event_id,
                "tenant_code": test_tenant_code,
                "external_id": f"SERVEL:test-{uuid.uuid4().hex[:8]}",
                "date": now.date(),
                "metadata": metadata,
                "now": now,
            })

            # Create candidate edge (DONATARIO)
            conn.execute(text("""
                INSERT INTO "Edge" (id, "tenantCode", "eventId", "toPersonId", label, metadata, "createdAt", "updatedAt")
                VALUES (:id, :tenant_code, :event_id, :to_person_id, 'DONATARIO', '{"source":"servel"}'::jsonb, :now, :now)
            """), {
                "id": edge_id,
                "tenant_code": test_tenant_code,
                "event_id": event_id,
                "to_person_id": candidate_id,
                "now": now,
            })

        # Verify event appears in view
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT event_id, amount, campaign_year, candidate_id
                FROM v_donations_graph
                WHERE tenant_code = :tenant_code
            """), {"tenant_code": test_tenant_code})
            rows = list(result)

        assert len(rows) == 1
        row = rows[0]
        assert row[0] == event_id
        assert row[1] == 1000000
        assert row[2] == 2021
        assert row[3] == candidate_id

    def test_non_donation_event_excluded(self, engine, test_tenant_code, cleanup):
        """Non-donation events (kind != 'donation') are excluded from view."""
        event_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        with engine.begin() as conn:
            # Create audience event (not donation)
            conn.execute(text("""
                INSERT INTO "Event" (id, "tenantCode", "externalId", kind, date, "createdAt", "updatedAt")
                VALUES (:id, :tenant_code, :external_id, 'audience', :date, :now, :now)
            """), {
                "id": event_id,
                "tenant_code": test_tenant_code,
                "external_id": f"TEST:{uuid.uuid4().hex[:8]}",
                "date": now.date(),
                "now": now,
            })

        # Verify event does NOT appear in donations view
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT event_id FROM v_donations_graph
                WHERE tenant_code = :tenant_code
            """), {"tenant_code": test_tenant_code})
            rows = list(result)

        assert len(rows) == 0

    def test_donor_type_person(self, engine, test_tenant_code, cleanup):
        """Donor type is 'person' when donor is a Person."""
        event_id = str(uuid.uuid4())
        donor_id = str(uuid.uuid4())
        candidate_id = str(uuid.uuid4())
        donor_edge_id = str(uuid.uuid4())
        candidate_edge_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        unique_suffix = uuid.uuid4().hex[:8]

        with engine.begin() as conn:
            # Create donor person (unique name per test run)
            conn.execute(text("""
                INSERT INTO "Person" (id, "tenantCode", "normalizedName", nombres, apellidos, "nombresCompletos", "createdAt", "updatedAt")
                VALUES (:id, :tenant_code, :normalized_name, 'Test', 'Donor', 'Test Donor', :now, :now)
            """), {
                "id": donor_id,
                "tenant_code": test_tenant_code,
                "normalized_name": f"test donor {unique_suffix}",
                "now": now,
            })

            # Create candidate person (unique name per test run)
            conn.execute(text("""
                INSERT INTO "Person" (id, "tenantCode", "normalizedName", nombres, apellidos, "nombresCompletos", "createdAt", "updatedAt")
                VALUES (:id, :tenant_code, :normalized_name, 'Test', 'Candidate', 'Test Candidate', :now, :now)
            """), {
                "id": candidate_id,
                "tenant_code": test_tenant_code,
                "normalized_name": f"test candidate {unique_suffix}",
                "now": now,
            })

            # Create donation event
            metadata = json.dumps({"amount": 500000})
            conn.execute(text("""
                INSERT INTO "Event" (id, "tenantCode", "externalId", kind, metadata, "createdAt", "updatedAt")
                VALUES (:id, :tenant_code, :external_id, 'donation', CAST(:metadata AS JSONB), :now, :now)
            """), {
                "id": event_id,
                "tenant_code": test_tenant_code,
                "external_id": f"SERVEL:test-{uuid.uuid4().hex[:8]}",
                "metadata": metadata,
                "now": now,
            })

            # Create donor edge (DONANTE)
            conn.execute(text("""
                INSERT INTO "Edge" (id, "tenantCode", "eventId", "toPersonId", label, "createdAt", "updatedAt")
                VALUES (:id, :tenant_code, :event_id, :to_person_id, 'DONANTE', :now, :now)
            """), {
                "id": donor_edge_id,
                "tenant_code": test_tenant_code,
                "event_id": event_id,
                "to_person_id": donor_id,
                "now": now,
            })

            # Create candidate edge (DONATARIO)
            conn.execute(text("""
                INSERT INTO "Edge" (id, "tenantCode", "eventId", "toPersonId", label, "createdAt", "updatedAt")
                VALUES (:id, :tenant_code, :event_id, :to_person_id, 'DONATARIO', :now, :now)
            """), {
                "id": candidate_edge_id,
                "tenant_code": test_tenant_code,
                "event_id": event_id,
                "to_person_id": candidate_id,
                "now": now,
            })

        # Verify donor_type is 'person'
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT donor_id, donor_type FROM v_donations_graph
                WHERE tenant_code = :tenant_code
            """), {"tenant_code": test_tenant_code})
            rows = list(result)

        assert len(rows) == 1
        assert rows[0][0] == donor_id
        assert rows[0][1] == "person"

    def test_amount_extraction_from_metadata(self, engine, test_tenant_code, cleanup):
        """Amount is correctly extracted from metadata JSONB."""
        event_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        expected_amount = 12345678

        with engine.begin() as conn:
            # Create donation event with specific amount
            metadata = json.dumps({"amount": expected_amount})
            conn.execute(text("""
                INSERT INTO "Event" (id, "tenantCode", "externalId", kind, metadata, "createdAt", "updatedAt")
                VALUES (:id, :tenant_code, :external_id, 'donation', CAST(:metadata AS JSONB), :now, :now)
            """), {
                "id": event_id,
                "tenant_code": test_tenant_code,
                "external_id": f"SERVEL:test-{uuid.uuid4().hex[:8]}",
                "metadata": metadata,
                "now": now,
            })

        # Verify amount is extracted correctly
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT amount FROM v_donations_graph
                WHERE event_id = :event_id
            """), {"event_id": event_id})
            rows = list(result)

        assert len(rows) == 1
        assert rows[0][0] == expected_amount

    def test_null_amount_handled(self, engine, test_tenant_code, cleanup):
        """Missing amount in metadata results in NULL."""
        event_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        with engine.begin() as conn:
            # Create donation event without amount
            metadata = json.dumps({"source": "servel"})
            conn.execute(text("""
                INSERT INTO "Event" (id, "tenantCode", "externalId", kind, metadata, "createdAt", "updatedAt")
                VALUES (:id, :tenant_code, :external_id, 'donation', CAST(:metadata AS JSONB), :now, :now)
            """), {
                "id": event_id,
                "tenant_code": test_tenant_code,
                "external_id": f"SERVEL:test-{uuid.uuid4().hex[:8]}",
                "metadata": metadata,
                "now": now,
            })

        # Verify amount is NULL
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT amount FROM v_donations_graph
                WHERE event_id = :event_id
            """), {"event_id": event_id})
            rows = list(result)

        assert len(rows) == 1
        assert rows[0][0] is None


@pytest.mark.integration
class TestTopDonorsViewSemantics:
    """Tests for v_top_donors_by_candidate view semantics."""

    @pytest.fixture
    def test_tenant_code(self):
        """Test tenant code for isolation."""
        return f"TEST_{uuid.uuid4().hex[:8]}"

    @pytest.fixture
    def cleanup(self, engine, test_tenant_code):
        """Cleanup test data after test."""
        yield
        # Cleanup test data
        with engine.begin() as conn:
            conn.execute(text(
                'DELETE FROM "Edge" WHERE "tenantCode" = :tenant_code'
            ), {"tenant_code": test_tenant_code})
            conn.execute(text(
                'DELETE FROM "Event" WHERE "tenantCode" = :tenant_code'
            ), {"tenant_code": test_tenant_code})
            conn.execute(text(
                'DELETE FROM "Person" WHERE "tenantCode" = :tenant_code'
            ), {"tenant_code": test_tenant_code})

    def test_aggregation_sums_amounts(self, engine, test_tenant_code, cleanup):
        """View aggregates total_amount correctly."""
        donor_id = str(uuid.uuid4())
        candidate_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        unique_suffix = uuid.uuid4().hex[:8]

        with engine.begin() as conn:
            # Create donor and candidate (unique names per test run)
            for person_id, name in [(donor_id, f"donor {unique_suffix}"), (candidate_id, f"candidate {unique_suffix}")]:
                conn.execute(text("""
                    INSERT INTO "Person" (id, "tenantCode", "normalizedName", nombres, apellidos, "nombresCompletos", "createdAt", "updatedAt")
                    VALUES (:id, :tenant_code, :name, 'Test', 'Person', 'Test Person', :now, :now)
                """), {
                    "id": person_id,
                    "tenant_code": test_tenant_code,
                    "name": name,
                    "now": now,
                })

            # Create multiple donations from same donor to same candidate
            amounts = [100000, 200000, 300000]
            for i, amount in enumerate(amounts):
                event_id = str(uuid.uuid4())
                metadata = json.dumps({
                    "amount": amount,
                    "donor_name": "Test Donor",
                    "candidate_name": "Test Candidate",
                })
                conn.execute(text("""
                    INSERT INTO "Event" (id, "tenantCode", "externalId", kind, metadata, "createdAt", "updatedAt")
                    VALUES (:id, :tenant_code, :external_id, 'donation', CAST(:metadata AS JSONB), :now, :now)
                """), {
                    "id": event_id,
                    "tenant_code": test_tenant_code,
                    "external_id": f"SERVEL:agg-{i}",
                    "metadata": metadata,
                    "now": now,
                })

                # Donor edge
                conn.execute(text("""
                    INSERT INTO "Edge" (id, "tenantCode", "eventId", "toPersonId", label, "createdAt", "updatedAt")
                    VALUES (:id, :tenant_code, :event_id, :to_person_id, 'DONANTE', :now, :now)
                """), {
                    "id": str(uuid.uuid4()),
                    "tenant_code": test_tenant_code,
                    "event_id": event_id,
                    "to_person_id": donor_id,
                    "now": now,
                })

                # Candidate edge
                conn.execute(text("""
                    INSERT INTO "Edge" (id, "tenantCode", "eventId", "toPersonId", label, "createdAt", "updatedAt")
                    VALUES (:id, :tenant_code, :event_id, :to_person_id, 'DONATARIO', :now, :now)
                """), {
                    "id": str(uuid.uuid4()),
                    "tenant_code": test_tenant_code,
                    "event_id": event_id,
                    "to_person_id": candidate_id,
                    "now": now,
                })

        # Verify aggregation
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT total_amount, donation_count
                FROM v_top_donors_by_candidate
                WHERE tenant_code = :tenant_code
                  AND donor_id = :donor_id
                  AND candidate_id = :candidate_id
            """), {
                "tenant_code": test_tenant_code,
                "donor_id": donor_id,
                "candidate_id": candidate_id,
            })
            rows = list(result)

        assert len(rows) == 1
        assert rows[0][0] == sum(amounts)  # total_amount
        assert rows[0][1] == len(amounts)  # donation_count
