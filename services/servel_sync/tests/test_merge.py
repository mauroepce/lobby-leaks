"""
Tests for SERVEL donation merge logic.

Tests deterministic matching:
- RUT as primary key
- Normalized name as fallback (unique only)
- No entity creation
- Idempotency
"""

import pytest
from datetime import date

from ..parser import ParsedDonation
from ..merge import (
    merge_donations,
    MergedDonation,
    DonationMergeResult,
    _is_persona_natural,
    _match_donor,
    _match_candidate,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_donation() -> ParsedDonation:
    """Create a sample ParsedDonation for testing."""
    return ParsedDonation(
        donor_name="JUAN PÉREZ GARCÍA",
        donor_name_normalized="juan perez garcia",
        candidate_name="MARÍA LÓPEZ SILVA",
        candidate_name_normalized="maria lopez silva",
        amount_clp=1000000,
        campaign_year=2021,
        donor_rut="12345678-9",
        donor_rut_valid=True,
        candidate_rut="98765432-1",
        candidate_rut_valid=True,
        donation_date=date(2021, 3, 15),
        donor_type="persona_natural",
        checksum="abc123",
    )


@pytest.fixture
def org_donation() -> ParsedDonation:
    """Create a donation from an organisation."""
    return ParsedDonation(
        donor_name="EMPRESA XYZ S.A.",
        donor_name_normalized="empresa xyz sa",
        candidate_name="CARLOS RUIZ",
        candidate_name_normalized="carlos ruiz",
        amount_clp=5000000,
        campaign_year=2021,
        donor_rut="76543210-K",
        donor_rut_valid=True,
        candidate_rut="11111111-1",
        candidate_rut_valid=True,
        donor_type="persona_juridica",
        checksum="def456",
    )


@pytest.fixture
def persons_by_rut():
    """Sample persons lookup by RUT."""
    return {
        "12345678-9": "person-uuid-1",
        "98765432-1": "person-uuid-2",
        "11111111-1": "person-uuid-3",
    }


@pytest.fixture
def persons_by_name():
    """Sample persons lookup by normalized name."""
    return {
        "juan perez garcia": ["person-uuid-1"],
        "maria lopez silva": ["person-uuid-2"],
        "carlos ruiz": ["person-uuid-3"],
    }


@pytest.fixture
def orgs_by_rut():
    """Sample orgs lookup by RUT."""
    return {
        "76543210-K": "org-uuid-1",
    }


@pytest.fixture
def orgs_by_name():
    """Sample orgs lookup by normalized name."""
    return {
        "empresa xyz sa": ["org-uuid-1"],
    }


# ============================================================================
# Test _is_persona_natural
# ============================================================================

class TestIsPersonaNatural:
    """Tests for donor type detection."""

    def test_persona_natural_explicit(self):
        assert _is_persona_natural("persona_natural") is True

    def test_persona_juridica_explicit(self):
        assert _is_persona_natural("persona_juridica") is False

    def test_none_defaults_to_natural(self):
        assert _is_persona_natural(None) is True

    def test_empty_string_defaults_to_natural(self):
        assert _is_persona_natural("") is True

    def test_case_insensitive(self):
        assert _is_persona_natural("PERSONA_JURIDICA") is False
        assert _is_persona_natural("Persona_Natural") is True

    def test_whitespace_handling(self):
        assert _is_persona_natural("  persona_juridica  ") is False


# ============================================================================
# Test _match_donor - Person
# ============================================================================

class TestMatchDonorPerson:
    """Tests for matching person donors."""

    def test_match_person_by_rut(self, sample_donation, persons_by_rut, persons_by_name):
        """RUT match takes priority."""
        person_id, org_id, matched_by = _match_donor(
            sample_donation,
            persons_by_rut,
            persons_by_name,
            {},
            {},
        )

        assert person_id == "person-uuid-1"
        assert org_id is None
        assert matched_by == "RUT"

    def test_match_person_by_name_when_no_rut(self, persons_by_name):
        """Fallback to name when no valid RUT."""
        donation = ParsedDonation(
            donor_name="JUAN PÉREZ GARCÍA",
            donor_name_normalized="juan perez garcia",
            candidate_name="TEST",
            candidate_name_normalized="test",
            amount_clp=1000,
            campaign_year=2021,
            donor_rut=None,
            donor_rut_valid=False,
            donor_type="persona_natural",
        )

        person_id, org_id, matched_by = _match_donor(
            donation,
            {},  # empty RUT lookup
            persons_by_name,
            {},
            {},
        )

        assert person_id == "person-uuid-1"
        assert org_id is None
        assert matched_by == "NAME"

    def test_match_person_by_name_when_invalid_rut(self, persons_by_name):
        """Fallback to name when RUT is invalid."""
        donation = ParsedDonation(
            donor_name="JUAN PÉREZ GARCÍA",
            donor_name_normalized="juan perez garcia",
            candidate_name="TEST",
            candidate_name_normalized="test",
            amount_clp=1000,
            campaign_year=2021,
            donor_rut="invalid",
            donor_rut_valid=False,
            donor_type="persona_natural",
        )

        person_id, org_id, matched_by = _match_donor(
            donation,
            {},
            persons_by_name,
            {},
            {},
        )

        assert person_id == "person-uuid-1"
        assert matched_by == "NAME"

    def test_no_match_returns_none(self):
        """No match when neither RUT nor name found."""
        donation = ParsedDonation(
            donor_name="UNKNOWN PERSON",
            donor_name_normalized="unknown person",
            candidate_name="TEST",
            candidate_name_normalized="test",
            amount_clp=1000,
            campaign_year=2021,
            donor_type="persona_natural",
        )

        person_id, org_id, matched_by = _match_donor(
            donation,
            {},
            {},
            {},
            {},
        )

        assert person_id is None
        assert org_id is None
        assert matched_by == "NONE"

    def test_name_collision_skips_match(self):
        """Multiple matches by name → skip (no merge)."""
        donation = ParsedDonation(
            donor_name="HOMONYM NAME",
            donor_name_normalized="homonym name",
            candidate_name="TEST",
            candidate_name_normalized="test",
            amount_clp=1000,
            campaign_year=2021,
            donor_type="persona_natural",
        )

        # Two persons with same normalized name
        persons_by_name = {
            "homonym name": ["person-uuid-a", "person-uuid-b"],
        }

        person_id, org_id, matched_by = _match_donor(
            donation,
            {},
            persons_by_name,
            {},
            {},
        )

        assert person_id is None
        assert org_id is None
        assert matched_by == "NONE"


# ============================================================================
# Test _match_donor - Organisation
# ============================================================================

class TestMatchDonorOrg:
    """Tests for matching organisation donors."""

    def test_match_org_by_rut(self, org_donation, orgs_by_rut, orgs_by_name):
        """Match organisation by RUT."""
        person_id, org_id, matched_by = _match_donor(
            org_donation,
            {},
            {},
            orgs_by_rut,
            orgs_by_name,
        )

        assert person_id is None
        assert org_id == "org-uuid-1"
        assert matched_by == "RUT"

    def test_match_org_by_name_when_no_rut(self, orgs_by_name):
        """Fallback to name for org when no RUT."""
        donation = ParsedDonation(
            donor_name="EMPRESA XYZ S.A.",
            donor_name_normalized="empresa xyz sa",
            candidate_name="TEST",
            candidate_name_normalized="test",
            amount_clp=1000,
            campaign_year=2021,
            donor_rut=None,
            donor_rut_valid=False,
            donor_type="persona_juridica",
        )

        person_id, org_id, matched_by = _match_donor(
            donation,
            {},
            {},
            {},
            orgs_by_name,
        )

        assert person_id is None
        assert org_id == "org-uuid-1"
        assert matched_by == "NAME"

    def test_org_name_collision_skips_match(self):
        """Multiple org matches by name → skip."""
        donation = ParsedDonation(
            donor_name="DUPLICATE ORG",
            donor_name_normalized="duplicate org",
            candidate_name="TEST",
            candidate_name_normalized="test",
            amount_clp=1000,
            campaign_year=2021,
            donor_type="persona_juridica",
        )

        orgs_by_name = {
            "duplicate org": ["org-uuid-a", "org-uuid-b"],
        }

        person_id, org_id, matched_by = _match_donor(
            donation,
            {},
            {},
            {},
            orgs_by_name,
        )

        assert person_id is None
        assert org_id is None
        assert matched_by == "NONE"


# ============================================================================
# Test _match_candidate
# ============================================================================

class TestMatchCandidate:
    """Tests for matching candidates (always Person)."""

    def test_match_candidate_by_rut(self, sample_donation, persons_by_rut, persons_by_name):
        """Match candidate by RUT."""
        person_id, matched_by = _match_candidate(
            sample_donation,
            persons_by_rut,
            persons_by_name,
        )

        assert person_id == "person-uuid-2"  # 98765432-1
        assert matched_by == "RUT"

    def test_match_candidate_by_name_when_no_rut(self, persons_by_name):
        """Fallback to name when no valid RUT."""
        donation = ParsedDonation(
            donor_name="TEST",
            donor_name_normalized="test",
            candidate_name="MARÍA LÓPEZ SILVA",
            candidate_name_normalized="maria lopez silva",
            amount_clp=1000,
            campaign_year=2021,
            candidate_rut=None,
            candidate_rut_valid=False,
        )

        person_id, matched_by = _match_candidate(
            donation,
            {},
            persons_by_name,
        )

        assert person_id == "person-uuid-2"
        assert matched_by == "NAME"

    def test_candidate_no_match(self):
        """No match for unknown candidate."""
        donation = ParsedDonation(
            donor_name="TEST",
            donor_name_normalized="test",
            candidate_name="UNKNOWN CANDIDATE",
            candidate_name_normalized="unknown candidate",
            amount_clp=1000,
            campaign_year=2021,
        )

        person_id, matched_by = _match_candidate(
            donation,
            {},
            {},
        )

        assert person_id is None
        assert matched_by == "NONE"

    def test_candidate_name_collision_skips_match(self):
        """Multiple candidate matches by name → skip."""
        donation = ParsedDonation(
            donor_name="TEST",
            donor_name_normalized="test",
            candidate_name="HOMONYM",
            candidate_name_normalized="homonym",
            amount_clp=1000,
            campaign_year=2021,
        )

        persons_by_name = {
            "homonym": ["uuid-1", "uuid-2"],
        }

        person_id, matched_by = _match_candidate(
            donation,
            {},
            persons_by_name,
        )

        assert person_id is None
        assert matched_by == "NONE"


# ============================================================================
# Test merge_donations
# ============================================================================

class TestMergeDonations:
    """Tests for the main merge_donations function."""

    def test_merge_single_donation_matched_by_rut(
        self,
        sample_donation,
        persons_by_rut,
        persons_by_name,
    ):
        """Single donation fully matched by RUT."""
        result = merge_donations(
            [sample_donation],
            persons_by_rut,
            persons_by_name,
            {},
            {},
        )

        assert result.total_records == 1
        assert result.donors_matched_by_rut == 1
        assert result.donors_matched_by_name == 0
        assert result.donors_unmatched == 0
        assert result.candidates_matched_by_rut == 1
        assert result.person_donors == 1
        assert result.org_donors == 0
        assert len(result.merged) == 1

        merged = result.merged[0]
        assert merged.donor_person_id == "person-uuid-1"
        assert merged.donor_org_id is None
        assert merged.candidate_person_id == "person-uuid-2"
        assert merged.donor_matched_by == "RUT"
        assert merged.candidate_matched_by == "RUT"

    def test_merge_org_donation(
        self,
        org_donation,
        persons_by_rut,
        persons_by_name,
        orgs_by_rut,
        orgs_by_name,
    ):
        """Organisation donation matched by RUT."""
        result = merge_donations(
            [org_donation],
            persons_by_rut,
            persons_by_name,
            orgs_by_rut,
            orgs_by_name,
        )

        assert result.total_records == 1
        assert result.donors_matched_by_rut == 1
        assert result.person_donors == 0
        assert result.org_donors == 1

        merged = result.merged[0]
        assert merged.donor_person_id is None
        assert merged.donor_org_id == "org-uuid-1"
        assert merged.candidate_person_id == "person-uuid-3"

    def test_merge_multiple_donations(
        self,
        sample_donation,
        org_donation,
        persons_by_rut,
        persons_by_name,
        orgs_by_rut,
        orgs_by_name,
    ):
        """Multiple donations of different types."""
        result = merge_donations(
            [sample_donation, org_donation],
            persons_by_rut,
            persons_by_name,
            orgs_by_rut,
            orgs_by_name,
        )

        assert result.total_records == 2
        assert result.donors_matched_by_rut == 2
        assert result.person_donors == 1
        assert result.org_donors == 1
        assert len(result.merged) == 2

    def test_merge_empty_list(self):
        """Empty donation list returns empty result."""
        result = merge_donations([], {}, {}, {}, {})

        assert result.total_records == 0
        assert result.donors_matched_by_rut == 0
        assert result.donors_matched_by_name == 0
        assert result.donors_unmatched == 0
        assert len(result.merged) == 0

    def test_merge_unmatched_donations(self):
        """Donations with no matches."""
        donation = ParsedDonation(
            donor_name="UNKNOWN",
            donor_name_normalized="unknown",
            candidate_name="ALSO UNKNOWN",
            candidate_name_normalized="also unknown",
            amount_clp=1000,
            campaign_year=2021,
        )

        result = merge_donations([donation], {}, {}, {}, {})

        assert result.total_records == 1
        assert result.donors_unmatched == 1
        assert result.candidates_unmatched == 1

        merged = result.merged[0]
        assert merged.donor_person_id is None
        assert merged.donor_org_id is None
        assert merged.candidate_person_id is None
        assert merged.donor_matched_by == "NONE"
        assert merged.candidate_matched_by == "NONE"


# ============================================================================
# Test no entity creation
# ============================================================================

class TestNoEntityCreation:
    """Verify that merge does NOT create new entities."""

    def test_merge_does_not_modify_lookups(
        self,
        sample_donation,
        persons_by_rut,
        persons_by_name,
    ):
        """Lookup dictionaries remain unchanged after merge."""
        original_rut_count = len(persons_by_rut)
        original_name_count = len(persons_by_name)

        merge_donations(
            [sample_donation],
            persons_by_rut,
            persons_by_name,
            {},
            {},
        )

        assert len(persons_by_rut) == original_rut_count
        assert len(persons_by_name) == original_name_count

    def test_unmatched_does_not_create_entities(self):
        """Unmatched donations do not add to lookups."""
        persons_by_rut = {}
        persons_by_name = {}
        orgs_by_rut = {}
        orgs_by_name = {}

        donation = ParsedDonation(
            donor_name="NEW PERSON",
            donor_name_normalized="new person",
            candidate_name="NEW CANDIDATE",
            candidate_name_normalized="new candidate",
            amount_clp=1000,
            campaign_year=2021,
            donor_rut="99999999-9",
            donor_rut_valid=True,
        )

        result = merge_donations(
            [donation],
            persons_by_rut,
            persons_by_name,
            orgs_by_rut,
            orgs_by_name,
        )

        # Lookups remain empty
        assert len(persons_by_rut) == 0
        assert len(persons_by_name) == 0
        assert len(orgs_by_rut) == 0
        assert len(orgs_by_name) == 0

        # Donation marked as unmatched
        assert result.donors_unmatched == 1
        assert result.candidates_unmatched == 1


# ============================================================================
# Test idempotency
# ============================================================================

class TestIdempotency:
    """Verify that same input produces same output."""

    def test_same_input_same_output(
        self,
        sample_donation,
        persons_by_rut,
        persons_by_name,
    ):
        """Running merge twice with same input gives identical results."""
        result1 = merge_donations(
            [sample_donation],
            persons_by_rut,
            persons_by_name,
            {},
            {},
        )

        result2 = merge_donations(
            [sample_donation],
            persons_by_rut,
            persons_by_name,
            {},
            {},
        )

        assert result1.total_records == result2.total_records
        assert result1.donors_matched_by_rut == result2.donors_matched_by_rut
        assert result1.donors_matched_by_name == result2.donors_matched_by_name
        assert result1.donors_unmatched == result2.donors_unmatched
        assert len(result1.merged) == len(result2.merged)

        # Compare individual merged donations
        for m1, m2 in zip(result1.merged, result2.merged):
            assert m1.donor_person_id == m2.donor_person_id
            assert m1.donor_org_id == m2.donor_org_id
            assert m1.candidate_person_id == m2.candidate_person_id
            assert m1.donor_matched_by == m2.donor_matched_by
            assert m1.candidate_matched_by == m2.candidate_matched_by


# ============================================================================
# Test DonationMergeResult
# ============================================================================

class TestDonationMergeResult:
    """Tests for DonationMergeResult dataclass."""

    def test_to_dict(self):
        """Test serialization to dict."""
        result = DonationMergeResult(
            total_records=10,
            donors_matched_by_rut=5,
            donors_matched_by_name=3,
            donors_unmatched=2,
            candidates_matched_by_rut=4,
            candidates_matched_by_name=4,
            candidates_unmatched=2,
            person_donors=7,
            org_donors=3,
        )

        d = result.to_dict()

        assert d["total_records"] == 10
        assert d["donors_matched_by_rut"] == 5
        assert d["donors_matched_by_name"] == 3
        assert d["donors_unmatched"] == 2
        assert d["candidates_matched_by_rut"] == 4
        assert d["candidates_matched_by_name"] == 4
        assert d["candidates_unmatched"] == 2
        assert d["person_donors"] == 7
        assert d["org_donors"] == 3
        assert d["merged_count"] == 0

    def test_default_values(self):
        """Test default initialization."""
        result = DonationMergeResult()

        assert result.total_records == 0
        assert result.donors_matched_by_rut == 0
        assert result.donors_matched_by_name == 0
        assert result.donors_unmatched == 0
        assert result.merged == []


# ============================================================================
# Test MergedDonation
# ============================================================================

class TestMergedDonation:
    """Tests for MergedDonation dataclass."""

    def test_default_values(self, sample_donation):
        """Test default initialization."""
        merged = MergedDonation(donation=sample_donation)

        assert merged.donor_person_id is None
        assert merged.donor_org_id is None
        assert merged.candidate_person_id is None
        assert merged.donor_matched_by == "NONE"
        assert merged.candidate_matched_by == "NONE"

    def test_xor_donor_fields(self, sample_donation):
        """Either person or org, not both."""
        # Person donor
        merged_person = MergedDonation(
            donation=sample_donation,
            donor_person_id="person-1",
            donor_org_id=None,
        )
        assert merged_person.donor_person_id is not None
        assert merged_person.donor_org_id is None

        # Org donor
        merged_org = MergedDonation(
            donation=sample_donation,
            donor_person_id=None,
            donor_org_id="org-1",
        )
        assert merged_org.donor_person_id is None
        assert merged_org.donor_org_id is not None
