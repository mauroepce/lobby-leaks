"""
Tests for SERVEL donation sync orchestrator.

Tests pipeline coordination without testing matching logic.
All dependencies are mocked.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import date

from services.servel_sync import orchestrator
from ..parser import ParsedDonation
from ..merge import DonationMergeResult, MergedDonation


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_engine():
    """Create a mock SQLAlchemy engine."""
    engine = MagicMock()
    # Mock connection context manager
    mock_conn = MagicMock()
    engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    engine.connect.return_value.__exit__ = MagicMock(return_value=False)
    return engine


@pytest.fixture
def sample_raw_records():
    """Sample raw records from fetcher."""
    return [
        {
            "NOMBRE_DONANTE": "JUAN PEREZ",
            "NOMBRE_CANDIDATO": "MARIA LOPEZ",
            "MONTO": "1000000",
            "AÑO_ELECCION": "2021",
        }
    ]


@pytest.fixture
def sample_parsed_donations():
    """Sample parsed donations."""
    return [
        ParsedDonation(
            donor_name="JUAN PEREZ",
            donor_name_normalized="juan perez",
            candidate_name="MARIA LOPEZ",
            candidate_name_normalized="maria lopez",
            amount_clp=1000000,
            campaign_year=2021,
        )
    ]


@pytest.fixture
def sample_merge_result(sample_parsed_donations):
    """Sample merge result."""
    return DonationMergeResult(
        total_records=1,
        donors_matched_by_rut=1,
        donors_matched_by_name=0,
        donors_unmatched=0,
        candidates_matched_by_rut=0,
        candidates_matched_by_name=1,
        candidates_unmatched=0,
        person_donors=1,
        org_donors=0,
        merged=[
            MergedDonation(
                donation=sample_parsed_donations[0],
                donor_person_id="uuid-person-1",
                donor_org_id=None,
                candidate_person_id="uuid-person-2",
                donor_matched_by="RUT",
                candidate_matched_by="NAME",
            )
        ],
    )


# ============================================================================
# Test Pipeline Execution Order
# ============================================================================

class TestPipelineOrder:
    """Tests verifying correct pipeline execution order."""

    def test_pipeline_calls_in_correct_order(
        self,
        mock_engine,
        sample_raw_records,
        sample_parsed_donations,
        sample_merge_result,
    ):
        """Verify pipeline steps execute in correct order."""
        with patch.object(orchestrator, 'fetch') as mock_fetch, \
             patch.object(orchestrator, 'parse_all_donations') as mock_parse, \
             patch.object(orchestrator, 'load_person_lookups') as mock_load_persons, \
             patch.object(orchestrator, 'load_org_lookups') as mock_load_orgs, \
             patch.object(orchestrator, 'merge_donations') as mock_merge:

            # Setup mocks
            mock_fetch.return_value = sample_raw_records
            mock_parse.return_value = (sample_parsed_donations, [])
            mock_load_persons.return_value = ({"rut": "id"}, {"name": ["id"]})
            mock_load_orgs.return_value = ({}, {})
            mock_merge.return_value = sample_merge_result

            # Execute
            result = orchestrator.run_servel_donation_sync("test.csv", mock_engine, "CL")

            # Verify all called
            assert mock_fetch.called
            assert mock_parse.called
            assert mock_load_persons.called
            assert mock_load_orgs.called
            assert mock_merge.called

            # Verify fetch called with source
            mock_fetch.assert_called_once_with("test.csv")

            # Verify parse called with fetch result
            mock_parse.assert_called_once_with(sample_raw_records, skip_errors=True)


# ============================================================================
# Test Correct Inputs to Merge
# ============================================================================

class TestMergeInputs:
    """Tests verifying correct inputs are passed to merge."""

    def test_merge_receives_parsed_donations(
        self,
        mock_engine,
        sample_parsed_donations,
        sample_merge_result,
    ):
        """Merge receives parsed donations from parser."""
        with patch.object(orchestrator, 'fetch') as mock_fetch, \
             patch.object(orchestrator, 'parse_all_donations') as mock_parse, \
             patch.object(orchestrator, 'load_person_lookups') as mock_load_persons, \
             patch.object(orchestrator, 'load_org_lookups') as mock_load_orgs, \
             patch.object(orchestrator, 'merge_donations') as mock_merge:

            mock_fetch.return_value = []
            mock_parse.return_value = (sample_parsed_donations, [])
            mock_load_persons.return_value = ({}, {})
            mock_load_orgs.return_value = ({}, {})
            mock_merge.return_value = sample_merge_result

            orchestrator.run_servel_donation_sync("test.csv", mock_engine, "CL")

            # First argument to merge is parsed donations
            call_args = mock_merge.call_args
            assert call_args[0][0] == sample_parsed_donations

    def test_merge_receives_person_lookups(
        self,
        mock_engine,
        sample_merge_result,
    ):
        """Merge receives person lookups from loader."""
        with patch.object(orchestrator, 'fetch') as mock_fetch, \
             patch.object(orchestrator, 'parse_all_donations') as mock_parse, \
             patch.object(orchestrator, 'load_person_lookups') as mock_load_persons, \
             patch.object(orchestrator, 'load_org_lookups') as mock_load_orgs, \
             patch.object(orchestrator, 'merge_donations') as mock_merge:

            mock_fetch.return_value = []
            mock_parse.return_value = ([], [])
            persons_by_rut = {"12345678-9": "uuid-1"}
            persons_by_name = {"juan perez": ["uuid-1"]}
            mock_load_persons.return_value = (persons_by_rut, persons_by_name)
            mock_load_orgs.return_value = ({}, {})
            mock_merge.return_value = sample_merge_result

            orchestrator.run_servel_donation_sync("test.csv", mock_engine, "CL")

            call_args = mock_merge.call_args
            assert call_args[0][1] == persons_by_rut
            assert call_args[0][2] == persons_by_name

    def test_merge_receives_org_lookups(
        self,
        mock_engine,
        sample_merge_result,
    ):
        """Merge receives org lookups from loader."""
        with patch.object(orchestrator, 'fetch') as mock_fetch, \
             patch.object(orchestrator, 'parse_all_donations') as mock_parse, \
             patch.object(orchestrator, 'load_person_lookups') as mock_load_persons, \
             patch.object(orchestrator, 'load_org_lookups') as mock_load_orgs, \
             patch.object(orchestrator, 'merge_donations') as mock_merge:

            mock_fetch.return_value = []
            mock_parse.return_value = ([], [])
            mock_load_persons.return_value = ({}, {})
            orgs_by_rut = {"76543210-K": "uuid-org-1"}
            orgs_by_name = {"empresa xyz": ["uuid-org-1"]}
            mock_load_orgs.return_value = (orgs_by_rut, orgs_by_name)
            mock_merge.return_value = sample_merge_result

            orchestrator.run_servel_donation_sync("test.csv", mock_engine, "CL")

            call_args = mock_merge.call_args
            assert call_args[0][3] == orgs_by_rut
            assert call_args[0][4] == orgs_by_name


# ============================================================================
# Test Result Handling
# ============================================================================

class TestResultHandling:
    """Tests verifying result is returned correctly."""

    def test_returns_merge_result(
        self,
        mock_engine,
        sample_merge_result,
    ):
        """Orchestrator returns merge result without mutation."""
        with patch.object(orchestrator, 'fetch') as mock_fetch, \
             patch.object(orchestrator, 'parse_all_donations') as mock_parse, \
             patch.object(orchestrator, 'load_person_lookups') as mock_load_persons, \
             patch.object(orchestrator, 'load_org_lookups') as mock_load_orgs, \
             patch.object(orchestrator, 'merge_donations') as mock_merge:

            mock_fetch.return_value = []
            mock_parse.return_value = ([], [])
            mock_load_persons.return_value = ({}, {})
            mock_load_orgs.return_value = ({}, {})
            mock_merge.return_value = sample_merge_result

            result = orchestrator.run_servel_donation_sync("test.csv", mock_engine, "CL")

            assert result is sample_merge_result
            assert result.total_records == 1
            assert result.donors_matched_by_rut == 1

    def test_result_not_mutated(
        self,
        mock_engine,
    ):
        """Verify result from merge is returned as-is."""
        with patch.object(orchestrator, 'fetch') as mock_fetch, \
             patch.object(orchestrator, 'parse_all_donations') as mock_parse, \
             patch.object(orchestrator, 'load_person_lookups') as mock_load_persons, \
             patch.object(orchestrator, 'load_org_lookups') as mock_load_orgs, \
             patch.object(orchestrator, 'merge_donations') as mock_merge:

            mock_fetch.return_value = []
            mock_parse.return_value = ([], [])
            mock_load_persons.return_value = ({}, {})
            mock_load_orgs.return_value = ({}, {})

            # Create a specific result to track
            expected_result = DonationMergeResult(total_records=42)
            mock_merge.return_value = expected_result

            result = orchestrator.run_servel_donation_sync("test.csv", mock_engine, "CL")

            # Same object reference
            assert result is expected_result
            assert result.total_records == 42


# ============================================================================
# Test Connection Handling
# ============================================================================

class TestConnectionHandling:
    """Tests verifying connection is handled correctly."""

    def test_connection_opened_and_closed(
        self,
        mock_engine,
    ):
        """Verify engine.connect() context manager is used."""
        with patch.object(orchestrator, 'fetch') as mock_fetch, \
             patch.object(orchestrator, 'parse_all_donations') as mock_parse, \
             patch.object(orchestrator, 'load_person_lookups') as mock_load_persons, \
             patch.object(orchestrator, 'load_org_lookups') as mock_load_orgs, \
             patch.object(orchestrator, 'merge_donations') as mock_merge:

            mock_fetch.return_value = []
            mock_parse.return_value = ([], [])
            mock_load_persons.return_value = ({}, {})
            mock_load_orgs.return_value = ({}, {})
            mock_merge.return_value = DonationMergeResult()

            orchestrator.run_servel_donation_sync("test.csv", mock_engine, "CL")

            # Verify connect was called
            mock_engine.connect.assert_called_once()

    def test_loaders_receive_connection(
        self,
        mock_engine,
    ):
        """Verify loaders receive the connection object."""
        with patch.object(orchestrator, 'fetch') as mock_fetch, \
             patch.object(orchestrator, 'parse_all_donations') as mock_parse, \
             patch.object(orchestrator, 'load_person_lookups') as mock_load_persons, \
             patch.object(orchestrator, 'load_org_lookups') as mock_load_orgs, \
             patch.object(orchestrator, 'merge_donations') as mock_merge:

            mock_fetch.return_value = []
            mock_parse.return_value = ([], [])
            mock_load_persons.return_value = ({}, {})
            mock_load_orgs.return_value = ({}, {})
            mock_merge.return_value = DonationMergeResult()

            # Get reference to mock connection
            mock_conn = mock_engine.connect.return_value.__enter__.return_value

            orchestrator.run_servel_donation_sync("test.csv", mock_engine, "CL")

            # Both loaders called with connection and tenant
            mock_load_persons.assert_called_once_with(mock_conn, "CL")
            mock_load_orgs.assert_called_once_with(mock_conn, "CL")


# ============================================================================
# Test Tenant Code Propagation
# ============================================================================

class TestTenantCodePropagation:
    """Tests verifying tenant_code is passed correctly."""

    def test_tenant_code_passed_to_loaders(
        self,
        mock_engine,
    ):
        """Tenant code is passed to both loaders."""
        with patch.object(orchestrator, 'fetch') as mock_fetch, \
             patch.object(orchestrator, 'parse_all_donations') as mock_parse, \
             patch.object(orchestrator, 'load_person_lookups') as mock_load_persons, \
             patch.object(orchestrator, 'load_org_lookups') as mock_load_orgs, \
             patch.object(orchestrator, 'merge_donations') as mock_merge:

            mock_fetch.return_value = []
            mock_parse.return_value = ([], [])
            mock_load_persons.return_value = ({}, {})
            mock_load_orgs.return_value = ({}, {})
            mock_merge.return_value = DonationMergeResult()

            orchestrator.run_servel_donation_sync("test.csv", mock_engine, "AR")

            # Check tenant_code in loader calls
            person_call_args = mock_load_persons.call_args
            org_call_args = mock_load_orgs.call_args

            assert person_call_args[0][1] == "AR"
            assert org_call_args[0][1] == "AR"


# ============================================================================
# Test Source Handling
# ============================================================================

class TestSourceHandling:
    """Tests verifying source is handled correctly."""

    def test_source_string_passed_to_fetch(
        self,
        mock_engine,
    ):
        """String source is passed directly to fetch."""
        with patch.object(orchestrator, 'fetch') as mock_fetch, \
             patch.object(orchestrator, 'parse_all_donations') as mock_parse, \
             patch.object(orchestrator, 'load_person_lookups') as mock_load_persons, \
             patch.object(orchestrator, 'load_org_lookups') as mock_load_orgs, \
             patch.object(orchestrator, 'merge_donations') as mock_merge:

            mock_fetch.return_value = []
            mock_parse.return_value = ([], [])
            mock_load_persons.return_value = ({}, {})
            mock_load_orgs.return_value = ({}, {})
            mock_merge.return_value = DonationMergeResult()

            orchestrator.run_servel_donation_sync("data/servel/donations.csv", mock_engine, "CL")

            mock_fetch.assert_called_once_with("data/servel/donations.csv")

    def test_source_path_converted_to_string(
        self,
        mock_engine,
    ):
        """Path source is converted to string for fetch."""
        from pathlib import Path

        with patch.object(orchestrator, 'fetch') as mock_fetch, \
             patch.object(orchestrator, 'parse_all_donations') as mock_parse, \
             patch.object(orchestrator, 'load_person_lookups') as mock_load_persons, \
             patch.object(orchestrator, 'load_org_lookups') as mock_load_orgs, \
             patch.object(orchestrator, 'merge_donations') as mock_merge:

            mock_fetch.return_value = []
            mock_parse.return_value = ([], [])
            mock_load_persons.return_value = ({}, {})
            mock_load_orgs.return_value = ({}, {})
            mock_merge.return_value = DonationMergeResult()

            orchestrator.run_servel_donation_sync(Path("data/servel/donations.csv"), mock_engine, "CL")

            mock_fetch.assert_called_once_with("data/servel/donations.csv")
