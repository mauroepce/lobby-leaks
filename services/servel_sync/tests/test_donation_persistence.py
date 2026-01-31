"""
Tests for SERVEL donation persistence.

Tests persisting MergedDonation objects as Events and Edges.
Uses mocked database connections.
"""

import pytest
from unittest.mock import MagicMock, patch, call
from datetime import date, datetime
import json

from ..parser import ParsedDonation
from ..merge import MergedDonation, DonationMergeResult
from ..donation_persistence import (
    persist_donation_events,
    DonationPersistResult,
    _build_external_id,
    _build_event_metadata,
    _persist_event,
    _persist_donor_edge,
    _persist_candidate_edge,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_donation() -> ParsedDonation:
    """Create a sample ParsedDonation."""
    return ParsedDonation(
        donor_name="JUAN PEREZ",
        donor_name_normalized="juan perez",
        candidate_name="MARIA LOPEZ",
        candidate_name_normalized="maria lopez",
        amount_clp=1000000,
        campaign_year=2021,
        donor_rut="12345678-5",
        donor_rut_valid=True,
        candidate_rut="98765432-5",
        candidate_rut_valid=True,
        donation_date=date(2021, 3, 15),
        donor_type="persona_natural",
        checksum="abc123def456",
    )


@pytest.fixture
def merged_person_donor(sample_donation) -> MergedDonation:
    """MergedDonation with person donor and candidate matched."""
    return MergedDonation(
        donation=sample_donation,
        donor_person_id="uuid-donor-1",
        donor_org_id=None,
        candidate_person_id="uuid-candidate-1",
        donor_matched_by="RUT",
        candidate_matched_by="RUT",
    )


@pytest.fixture
def merged_org_donor(sample_donation) -> MergedDonation:
    """MergedDonation with org donor and candidate matched."""
    donation = ParsedDonation(
        donor_name="EMPRESA XYZ",
        donor_name_normalized="empresa xyz",
        candidate_name="CARLOS RUIZ",
        candidate_name_normalized="carlos ruiz",
        amount_clp=5000000,
        campaign_year=2021,
        donor_type="persona_juridica",
        checksum="org123checksum",
    )
    return MergedDonation(
        donation=donation,
        donor_person_id=None,
        donor_org_id="uuid-org-1",
        candidate_person_id="uuid-candidate-2",
        donor_matched_by="RUT",
        candidate_matched_by="NAME",
    )


@pytest.fixture
def merged_no_candidate(sample_donation) -> MergedDonation:
    """MergedDonation with no candidate match."""
    return MergedDonation(
        donation=sample_donation,
        donor_person_id="uuid-donor-1",
        donor_org_id=None,
        candidate_person_id=None,
        donor_matched_by="RUT",
        candidate_matched_by="NONE",
    )


@pytest.fixture
def merged_no_donor(sample_donation) -> MergedDonation:
    """MergedDonation with no donor match but candidate matched."""
    return MergedDonation(
        donation=sample_donation,
        donor_person_id=None,
        donor_org_id=None,
        candidate_person_id="uuid-candidate-1",
        donor_matched_by="NONE",
        candidate_matched_by="RUT",
    )


@pytest.fixture
def mock_engine():
    """Create a mock SQLAlchemy engine."""
    engine = MagicMock()
    mock_conn = MagicMock()

    # Mock transaction context manager
    engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
    engine.begin.return_value.__exit__ = MagicMock(return_value=False)

    return engine, mock_conn


# ============================================================================
# Test _build_external_id
# ============================================================================

class TestBuildExternalId:
    """Tests for external ID generation."""

    def test_builds_servel_prefix(self):
        """External ID has SERVEL: prefix."""
        result = _build_external_id("abc123")
        assert result == "SERVEL:abc123"

    def test_includes_full_checksum(self):
        """External ID includes full checksum."""
        checksum = "a1b2c3d4e5f6"
        result = _build_external_id(checksum)
        assert result == f"SERVEL:{checksum}"


# ============================================================================
# Test _build_event_metadata
# ============================================================================

class TestBuildEventMetadata:
    """Tests for event metadata generation."""

    def test_includes_source(self, merged_person_donor):
        """Metadata includes source=servel."""
        metadata = _build_event_metadata(merged_person_donor)
        assert metadata["source"] == "servel"

    def test_includes_amount(self, merged_person_donor):
        """Metadata includes amount."""
        metadata = _build_event_metadata(merged_person_donor)
        assert metadata["amount"] == 1000000

    def test_includes_campaign_year(self, merged_person_donor):
        """Metadata includes campaign_year."""
        metadata = _build_event_metadata(merged_person_donor)
        assert metadata["campaign_year"] == 2021

    def test_includes_donation_date(self, merged_person_donor):
        """Metadata includes donation_date when present."""
        metadata = _build_event_metadata(merged_person_donor)
        assert metadata["donation_date"] == "2021-03-15"

    def test_includes_matching_info(self, merged_person_donor):
        """Metadata includes matching info."""
        metadata = _build_event_metadata(merged_person_donor)
        assert metadata["donor_matched_by"] == "RUT"
        assert metadata["candidate_matched_by"] == "RUT"


# ============================================================================
# Test _persist_event
# ============================================================================

class TestPersistEvent:
    """Tests for event persistence."""

    def test_skips_when_no_candidate(self, mock_engine, merged_no_candidate):
        """Skips event creation when candidate not matched."""
        _, mock_conn = mock_engine

        event_id, outcome = _persist_event(
            mock_conn, merged_no_candidate, "CL"
        )

        assert event_id is None
        assert outcome == "skipped_no_candidate"
        mock_conn.execute.assert_not_called()

    def test_skips_when_no_checksum(self, mock_engine, merged_person_donor):
        """Skips event creation when checksum is empty."""
        _, mock_conn = mock_engine

        # Remove checksum
        merged_person_donor.donation.checksum = ""

        event_id, outcome = _persist_event(
            mock_conn, merged_person_donor, "CL"
        )

        assert event_id is None
        assert outcome == "skipped_invalid"

    def test_creates_event_with_correct_external_id(self, mock_engine, merged_person_donor):
        """Creates event with SERVEL:{checksum} external ID."""
        _, mock_conn = mock_engine

        # Mock successful insert
        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("new-event-uuid",)
        mock_conn.execute.return_value = mock_result

        event_id, outcome = _persist_event(
            mock_conn, merged_person_donor, "CL"
        )

        assert outcome == "created"
        # Verify external_id in query params
        call_args = mock_conn.execute.call_args
        params = call_args[0][1]
        assert params["external_id"] == "SERVEL:abc123def456"
        assert params["kind"] == "donation"

    def test_returns_existing_when_conflict(self, mock_engine, merged_person_donor):
        """Returns existing event ID on conflict."""
        _, mock_conn = mock_engine

        # Mock conflict (no row returned from insert)
        mock_insert_result = MagicMock()
        mock_insert_result.fetchone.return_value = None

        # Mock existing event lookup
        mock_select_result = MagicMock()
        mock_select_result.fetchone.return_value = ("existing-event-uuid",)

        mock_conn.execute.side_effect = [mock_insert_result, mock_select_result]

        event_id, outcome = _persist_event(
            mock_conn, merged_person_donor, "CL"
        )

        assert event_id == "existing-event-uuid"
        assert outcome == "existing"


# ============================================================================
# Test _persist_donor_edge
# ============================================================================

class TestPersistDonorEdge:
    """Tests for donor edge persistence."""

    def test_creates_person_donor_edge(self, mock_engine, merged_person_donor):
        """Creates edge to person donor."""
        _, mock_conn = mock_engine

        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("new-edge-uuid",)
        mock_conn.execute.return_value = mock_result

        outcome = _persist_donor_edge(
            mock_conn, "event-uuid", merged_person_donor, "CL"
        )

        assert outcome == "created"
        call_args = mock_conn.execute.call_args
        params = call_args[0][1]
        assert params["to_person_id"] == "uuid-donor-1"
        assert params["to_org_id"] is None
        assert params["label"] == "DONANTE"

    def test_creates_org_donor_edge(self, mock_engine, merged_org_donor):
        """Creates edge to org donor."""
        _, mock_conn = mock_engine

        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("new-edge-uuid",)
        mock_conn.execute.return_value = mock_result

        outcome = _persist_donor_edge(
            mock_conn, "event-uuid", merged_org_donor, "CL"
        )

        assert outcome == "created"
        call_args = mock_conn.execute.call_args
        params = call_args[0][1]
        assert params["to_person_id"] is None
        assert params["to_org_id"] == "uuid-org-1"

    def test_skips_when_no_donor(self, mock_engine, merged_no_donor):
        """Skips edge when no donor matched."""
        _, mock_conn = mock_engine

        outcome = _persist_donor_edge(
            mock_conn, "event-uuid", merged_no_donor, "CL"
        )

        assert outcome == "skipped"
        mock_conn.execute.assert_not_called()

    def test_returns_duplicate_on_conflict(self, mock_engine, merged_person_donor):
        """Returns duplicate when edge already exists."""
        _, mock_conn = mock_engine

        mock_result = MagicMock()
        mock_result.fetchone.return_value = None  # No row = conflict
        mock_conn.execute.return_value = mock_result

        outcome = _persist_donor_edge(
            mock_conn, "event-uuid", merged_person_donor, "CL"
        )

        assert outcome == "duplicate"


# ============================================================================
# Test _persist_candidate_edge
# ============================================================================

class TestPersistCandidateEdge:
    """Tests for candidate edge persistence."""

    def test_creates_candidate_edge(self, mock_engine, merged_person_donor):
        """Creates edge to candidate person."""
        _, mock_conn = mock_engine

        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("new-edge-uuid",)
        mock_conn.execute.return_value = mock_result

        outcome = _persist_candidate_edge(
            mock_conn, "event-uuid", merged_person_donor, "CL"
        )

        assert outcome == "created"
        call_args = mock_conn.execute.call_args
        params = call_args[0][1]
        assert params["to_person_id"] == "uuid-candidate-1"
        assert params["label"] == "DONATARIO"

    def test_skips_when_no_candidate(self, mock_engine, merged_no_candidate):
        """Skips edge when no candidate matched."""
        _, mock_conn = mock_engine

        outcome = _persist_candidate_edge(
            mock_conn, "event-uuid", merged_no_candidate, "CL"
        )

        assert outcome == "skipped"
        mock_conn.execute.assert_not_called()


# ============================================================================
# Test persist_donation_events - Integration
# ============================================================================

class TestPersistDonationEvents:
    """Integration tests for persist_donation_events."""

    def test_empty_result_returns_empty(self, mock_engine):
        """Empty merge result returns empty persist result."""
        engine, _ = mock_engine

        merge_result = DonationMergeResult()

        result = persist_donation_events(merge_result, engine, "CL")

        assert result.events_created == 0
        assert result.donor_edges_created == 0
        assert result.candidate_edges_created == 0
        assert result.total_processed == 0

    def test_skips_no_candidate_donations(self, mock_engine, merged_no_candidate):
        """Skips donations without candidate match."""
        engine, mock_conn = mock_engine

        merge_result = DonationMergeResult(
            total_records=1,
            merged=[merged_no_candidate],
        )

        result = persist_donation_events(merge_result, engine, "CL")

        assert result.events_created == 0
        assert result.skipped_no_candidate == 1

    def test_creates_event_and_both_edges(self, mock_engine, merged_person_donor):
        """Creates event and both donor/candidate edges."""
        engine, mock_conn = mock_engine

        # Setup mocks for: insert event, insert donor edge, insert candidate edge
        mock_event_result = MagicMock()
        mock_event_result.fetchone.return_value = ("event-uuid",)

        mock_donor_edge_result = MagicMock()
        mock_donor_edge_result.fetchone.return_value = ("donor-edge-uuid",)

        mock_candidate_edge_result = MagicMock()
        mock_candidate_edge_result.fetchone.return_value = ("candidate-edge-uuid",)

        mock_conn.execute.side_effect = [
            mock_event_result,
            mock_donor_edge_result,
            mock_candidate_edge_result,
        ]

        merge_result = DonationMergeResult(
            total_records=1,
            merged=[merged_person_donor],
        )

        result = persist_donation_events(merge_result, engine, "CL")

        assert result.events_created == 1
        assert result.donor_edges_created == 1
        assert result.candidate_edges_created == 1

    def test_creates_event_without_donor_edge(self, mock_engine, merged_no_donor):
        """Creates event with only candidate edge when no donor match."""
        engine, mock_conn = mock_engine

        # Setup mocks for: insert event, insert candidate edge (donor skipped)
        mock_event_result = MagicMock()
        mock_event_result.fetchone.return_value = ("event-uuid",)

        mock_candidate_edge_result = MagicMock()
        mock_candidate_edge_result.fetchone.return_value = ("candidate-edge-uuid",)

        mock_conn.execute.side_effect = [
            mock_event_result,
            mock_candidate_edge_result,
        ]

        merge_result = DonationMergeResult(
            total_records=1,
            merged=[merged_no_donor],
        )

        result = persist_donation_events(merge_result, engine, "CL")

        assert result.events_created == 1
        assert result.donor_edges_created == 0  # Skipped, no match
        assert result.candidate_edges_created == 1

    def test_handles_org_donor(self, mock_engine, merged_org_donor):
        """Handles organisation donor correctly."""
        engine, mock_conn = mock_engine

        mock_event_result = MagicMock()
        mock_event_result.fetchone.return_value = ("event-uuid",)

        mock_donor_edge_result = MagicMock()
        mock_donor_edge_result.fetchone.return_value = ("donor-edge-uuid",)

        mock_candidate_edge_result = MagicMock()
        mock_candidate_edge_result.fetchone.return_value = ("candidate-edge-uuid",)

        mock_conn.execute.side_effect = [
            mock_event_result,
            mock_donor_edge_result,
            mock_candidate_edge_result,
        ]

        merge_result = DonationMergeResult(
            total_records=1,
            merged=[merged_org_donor],
        )

        result = persist_donation_events(merge_result, engine, "CL")

        assert result.events_created == 1
        assert result.donor_edges_created == 1

        # Verify org ID was used
        donor_edge_call = mock_conn.execute.call_args_list[1]
        params = donor_edge_call[0][1]
        assert params["to_org_id"] == "uuid-org-1"
        assert params["to_person_id"] is None


# ============================================================================
# Test Idempotency
# ============================================================================

class TestIdempotency:
    """Tests for idempotent behavior."""

    def test_second_run_returns_existing(self, mock_engine, merged_person_donor):
        """Second run detects existing events."""
        engine, mock_conn = mock_engine

        # First run: creates event
        mock_insert_result = MagicMock()
        mock_insert_result.fetchone.return_value = None  # Conflict

        mock_select_result = MagicMock()
        mock_select_result.fetchone.return_value = ("existing-event-uuid",)

        # Edges also conflict
        mock_edge_result = MagicMock()
        mock_edge_result.fetchone.return_value = None

        mock_conn.execute.side_effect = [
            mock_insert_result,  # Event insert (conflict)
            mock_select_result,  # Event select
            mock_edge_result,    # Donor edge (conflict)
            mock_edge_result,    # Candidate edge (conflict)
        ]

        merge_result = DonationMergeResult(
            total_records=1,
            merged=[merged_person_donor],
        )

        result = persist_donation_events(merge_result, engine, "CL")

        assert result.events_existing == 1
        assert result.events_created == 0
        assert result.skipped_duplicates == 2  # Both edges

    def test_same_input_same_metrics(self, mock_engine, merged_person_donor):
        """Running twice with same input gives consistent metrics."""
        engine, mock_conn = mock_engine

        # Both runs return existing
        mock_insert_result = MagicMock()
        mock_insert_result.fetchone.return_value = None

        mock_select_result = MagicMock()
        mock_select_result.fetchone.return_value = ("existing-uuid",)

        mock_edge_result = MagicMock()
        mock_edge_result.fetchone.return_value = None

        merge_result = DonationMergeResult(
            total_records=1,
            merged=[merged_person_donor],
        )

        # Run 1
        mock_conn.execute.side_effect = [
            mock_insert_result, mock_select_result,
            mock_edge_result, mock_edge_result,
        ]
        result1 = persist_donation_events(merge_result, engine, "CL")

        # Run 2
        mock_conn.execute.side_effect = [
            mock_insert_result, mock_select_result,
            mock_edge_result, mock_edge_result,
        ]
        result2 = persist_donation_events(merge_result, engine, "CL")

        assert result1.events_existing == result2.events_existing
        assert result1.skipped_duplicates == result2.skipped_duplicates


# ============================================================================
# Test DonationPersistResult
# ============================================================================

class TestDonationPersistResult:
    """Tests for DonationPersistResult dataclass."""

    def test_default_values(self):
        """Test default initialization."""
        result = DonationPersistResult()

        assert result.events_created == 0
        assert result.events_existing == 0
        assert result.donor_edges_created == 0
        assert result.candidate_edges_created == 0
        assert result.skipped_no_candidate == 0
        assert result.skipped_duplicates == 0
        assert result.skipped_invalid == 0
        assert result.errors == []

    def test_total_processed(self):
        """Test total_processed calculation."""
        result = DonationPersistResult(
            events_created=5,
            events_existing=3,
            skipped_no_candidate=2,
            skipped_duplicates=1,
            skipped_invalid=1,
        )

        assert result.total_processed == 12

    def test_duration_seconds(self):
        """Test duration calculation."""
        result = DonationPersistResult(
            started_at=datetime(2021, 1, 1, 12, 0, 0),
            finished_at=datetime(2021, 1, 1, 12, 0, 5),
        )

        assert result.duration_seconds == 5.0

    def test_to_dict(self):
        """Test serialization to dict."""
        result = DonationPersistResult(
            events_created=10,
            events_existing=5,
            donor_edges_created=8,
            candidate_edges_created=10,
            skipped_no_candidate=2,
        )

        d = result.to_dict()

        assert d["events_created"] == 10
        assert d["events_existing"] == 5
        assert d["donor_edges_created"] == 8
        assert d["candidate_edges_created"] == 10
        assert d["skipped_no_candidate"] == 2


# ============================================================================
# Test Edge Cases
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_handles_database_error(self, mock_engine, merged_person_donor):
        """Handles database errors gracefully."""
        engine, mock_conn = mock_engine

        mock_conn.execute.side_effect = Exception("DB connection lost")

        merge_result = DonationMergeResult(
            total_records=1,
            merged=[merged_person_donor],
        )

        result = persist_donation_events(merge_result, engine, "CL")

        assert result.skipped_invalid == 1
        assert len(result.errors) == 1
        assert "abc123def456" in result.errors[0]

    def test_handles_none_checksum(self, mock_engine, merged_person_donor):
        """Handles None checksum."""
        engine, mock_conn = mock_engine

        merged_person_donor.donation.checksum = None

        merge_result = DonationMergeResult(
            total_records=1,
            merged=[merged_person_donor],
        )

        result = persist_donation_events(merge_result, engine, "CL")

        assert result.skipped_invalid == 1

    def test_multiple_donations_processed(self, mock_engine, merged_person_donor, merged_org_donor):
        """Processes multiple donations correctly."""
        engine, mock_conn = mock_engine

        # Mock for both donations
        mock_event_result = MagicMock()
        mock_event_result.fetchone.return_value = ("event-uuid",)

        mock_edge_result = MagicMock()
        mock_edge_result.fetchone.return_value = ("edge-uuid",)

        # 3 calls per donation: event, donor edge, candidate edge
        mock_conn.execute.side_effect = [
            mock_event_result, mock_edge_result, mock_edge_result,  # First
            mock_event_result, mock_edge_result, mock_edge_result,  # Second
        ]

        merge_result = DonationMergeResult(
            total_records=2,
            merged=[merged_person_donor, merged_org_donor],
        )

        result = persist_donation_events(merge_result, engine, "CL")

        assert result.events_created == 2
        assert result.donor_edges_created == 2
        assert result.candidate_edges_created == 2
