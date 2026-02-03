"""
Integration tests for analysis view existence.

These tests verify that the graph analysis views exist and have
the expected structure.

Requires DATABASE_URL environment variable.
"""

import pytest
from sqlalchemy import text


# ============================================================================
# Analysis View Existence Tests
# ============================================================================


@pytest.mark.integration
class TestVDonationsGraphExists:
    """Tests for v_donations_graph view existence."""

    def test_v_donations_graph_exists(self, engine):
        """View v_donations_graph exists."""
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT COUNT(*) FROM information_schema.views
                WHERE table_name = 'v_donations_graph'
            """))
            count = result.scalar()
            assert count == 1, "v_donations_graph view does not exist"

    def test_v_donations_graph_has_required_columns(self, engine):
        """v_donations_graph has required columns."""
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'v_donations_graph'
            """))
            columns = {row[0] for row in result}

        expected = {
            "event_id",
            "tenant_code",
            "amount",
            "donor_id",
            "donor_type",
            "candidate_id",
        }
        assert expected.issubset(columns), (
            f"Missing columns: {expected - columns}"
        )

    def test_v_donations_graph_is_queryable(self, engine):
        """v_donations_graph can be queried."""
        with engine.connect() as conn:
            # Just verify the query runs without error
            result = conn.execute(text("""
                SELECT event_id, tenant_code, amount, donor_id, candidate_id
                FROM v_donations_graph
                LIMIT 1
            """))
            # Fetch to ensure query completes
            list(result)

    def test_v_donations_graph_has_metadata_columns(self, engine):
        """v_donations_graph has metadata columns."""
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'v_donations_graph'
            """))
            columns = {row[0] for row in result}

        metadata_columns = {
            "campaign_year",
            "donor_name",
            "candidate_name",
            "donor_matched_by",
            "candidate_matched_by",
        }
        assert metadata_columns.issubset(columns), (
            f"Missing metadata columns: {metadata_columns - columns}"
        )


@pytest.mark.integration
class TestVTopDonorsByCandidateExists:
    """Tests for v_top_donors_by_candidate view existence."""

    def test_v_top_donors_by_candidate_exists(self, engine):
        """View v_top_donors_by_candidate exists."""
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT COUNT(*) FROM information_schema.views
                WHERE table_name = 'v_top_donors_by_candidate'
            """))
            count = result.scalar()
            assert count == 1, "v_top_donors_by_candidate view does not exist"

    def test_v_top_donors_by_candidate_has_required_columns(self, engine):
        """v_top_donors_by_candidate has required columns."""
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'v_top_donors_by_candidate'
            """))
            columns = {row[0] for row in result}

        expected = {
            "tenant_code",
            "candidate_id",
            "donor_id",
            "total_amount",
            "donation_count",
        }
        assert expected.issubset(columns), (
            f"Missing columns: {expected - columns}"
        )

    def test_v_top_donors_by_candidate_is_queryable(self, engine):
        """v_top_donors_by_candidate can be queried."""
        with engine.connect() as conn:
            # Just verify the query runs without error
            result = conn.execute(text("""
                SELECT tenant_code, candidate_id, donor_id, total_amount, donation_count
                FROM v_top_donors_by_candidate
                LIMIT 1
            """))
            # Fetch to ensure query completes
            list(result)

    def test_v_top_donors_by_candidate_has_name_columns(self, engine):
        """v_top_donors_by_candidate has name columns for display."""
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'v_top_donors_by_candidate'
            """))
            columns = {row[0] for row in result}

        name_columns = {"candidate_name", "donor_name", "donor_type"}
        assert name_columns.issubset(columns), (
            f"Missing name columns: {name_columns - columns}"
        )
