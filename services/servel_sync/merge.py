"""
Merge logic for SERVEL campaign financing donations.

Matches ParsedDonation entities (donors and candidates) against the canonical
database (Person, Organisation) using deterministic matching:
1. RUT as primary key (if valid)
2. Normalized name as fallback (exact match only, no duplicates)

This module is READ-ONLY - no entities are created or modified.
Pure function design for testability.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

from .parser import ParsedDonation


@dataclass
class MergedDonation:
    """
    A ParsedDonation with resolved entity IDs.

    Links donation to canonical Person/Organisation entities
    when a match is found.
    """
    donation: ParsedDonation

    # Donor entity (XOR: person or org, not both)
    donor_person_id: Optional[str] = None
    donor_org_id: Optional[str] = None

    # Candidate entity (always a person in elections)
    candidate_person_id: Optional[str] = None

    # How the donor was matched
    donor_matched_by: Literal["RUT", "NAME", "NONE"] = "NONE"

    # How the candidate was matched
    candidate_matched_by: Literal["RUT", "NAME", "NONE"] = "NONE"


@dataclass
class DonationMergeResult:
    """
    Result of merge operation with detailed metrics.

    Tracks matching outcomes separately for donors and candidates.
    """
    # Total input
    total_records: int = 0

    # Donor matching metrics
    donors_matched_by_rut: int = 0
    donors_matched_by_name: int = 0
    donors_unmatched: int = 0

    # Candidate matching metrics
    candidates_matched_by_rut: int = 0
    candidates_matched_by_name: int = 0
    candidates_unmatched: int = 0

    # Merged donations
    merged: List[MergedDonation] = field(default_factory=list)

    # Breakdown by donor type
    person_donors: int = 0
    org_donors: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_records": self.total_records,
            "donors_matched_by_rut": self.donors_matched_by_rut,
            "donors_matched_by_name": self.donors_matched_by_name,
            "donors_unmatched": self.donors_unmatched,
            "candidates_matched_by_rut": self.candidates_matched_by_rut,
            "candidates_matched_by_name": self.candidates_matched_by_name,
            "candidates_unmatched": self.candidates_unmatched,
            "person_donors": self.person_donors,
            "org_donors": self.org_donors,
            "merged_count": len(self.merged),
        }


def _is_persona_natural(donor_type: Optional[str]) -> bool:
    """
    Determine if donor type indicates a natural person.

    Args:
        donor_type: Normalized donor type from ParsedDonation

    Returns:
        True for persona_natural (or None/unknown), False for persona_juridica
    """
    if not donor_type:
        return True

    return donor_type.lower().strip() != "persona_juridica"


def _match_donor(
    donation: ParsedDonation,
    persons_by_rut: Dict[str, str],
    persons_by_name: Dict[str, List[str]],
    orgs_by_rut: Dict[str, str],
    orgs_by_name: Dict[str, List[str]],
) -> tuple[Optional[str], Optional[str], Literal["RUT", "NAME", "NONE"]]:
    """
    Match donor to Person or Organisation.

    Matching priority:
    1. RUT (if valid) - deterministic
    2. Normalized name (if unique match) - skip if multiple matches

    Args:
        donation: The donation to match
        persons_by_rut: Dict mapping RUT -> Person.id
        persons_by_name: Dict mapping normalized_name -> List[Person.id]
        orgs_by_rut: Dict mapping RUT -> Organisation.id
        orgs_by_name: Dict mapping normalized_name -> List[Organisation.id]

    Returns:
        Tuple of (person_id, org_id, matched_by)
        Only one of person_id/org_id will be set.
    """
    is_person = _is_persona_natural(donation.donor_type)

    if is_person:
        # Try Person matching
        # 1. By RUT (if valid)
        if donation.donor_rut_valid and donation.donor_rut:
            person_id = persons_by_rut.get(donation.donor_rut)
            if person_id:
                return person_id, None, "RUT"

        # 2. By normalized name (only if unique)
        if donation.donor_name_normalized:
            person_ids = persons_by_name.get(donation.donor_name_normalized, [])
            if len(person_ids) == 1:
                return person_ids[0], None, "NAME"
            # If len > 1, skip due to collision

        return None, None, "NONE"

    else:
        # Try Organisation matching
        # 1. By RUT (if valid)
        if donation.donor_rut_valid and donation.donor_rut:
            org_id = orgs_by_rut.get(donation.donor_rut)
            if org_id:
                return None, org_id, "RUT"

        # 2. By normalized name (only if unique)
        if donation.donor_name_normalized:
            org_ids = orgs_by_name.get(donation.donor_name_normalized, [])
            if len(org_ids) == 1:
                return None, org_ids[0], "NAME"
            # If len > 1, skip due to collision

        return None, None, "NONE"


def _match_candidate(
    donation: ParsedDonation,
    persons_by_rut: Dict[str, str],
    persons_by_name: Dict[str, List[str]],
) -> tuple[Optional[str], Literal["RUT", "NAME", "NONE"]]:
    """
    Match candidate to Person.

    Candidates are always persons (electoral candidates).
    Matching priority:
    1. RUT (if valid) - deterministic
    2. Normalized name (if unique match) - skip if multiple matches

    Args:
        donation: The donation to match
        persons_by_rut: Dict mapping RUT -> Person.id
        persons_by_name: Dict mapping normalized_name -> List[Person.id]

    Returns:
        Tuple of (person_id, matched_by)
    """
    # 1. By RUT (if valid)
    if donation.candidate_rut_valid and donation.candidate_rut:
        person_id = persons_by_rut.get(donation.candidate_rut)
        if person_id:
            return person_id, "RUT"

    # 2. By normalized name (only if unique)
    if donation.candidate_name_normalized:
        person_ids = persons_by_name.get(donation.candidate_name_normalized, [])
        if len(person_ids) == 1:
            return person_ids[0], "NAME"
        # If len > 1, skip due to collision

    return None, "NONE"


def merge_donations(
    donations: List[ParsedDonation],
    persons_by_rut: Dict[str, str],
    persons_by_name: Dict[str, List[str]],
    orgs_by_rut: Dict[str, str],
    orgs_by_name: Dict[str, List[str]],
) -> DonationMergeResult:
    """
    Merge SERVEL donations against canonical entities.

    Pure function - no database access, no side effects.
    Matching is deterministic:
    1. RUT match (if valid RUT present)
    2. Exact normalized name match (only if unique - no collisions)
    3. Unmatched (no match found or collision)

    Args:
        donations: List of ParsedDonation from parser
        persons_by_rut: Dict mapping RUT -> Person.id
        persons_by_name: Dict mapping normalized_name -> List[Person.id]
        orgs_by_rut: Dict mapping RUT -> Organisation.id
        orgs_by_name: Dict mapping normalized_name -> List[Organisation.id]

    Returns:
        DonationMergeResult with merged donations and metrics

    Example:
        >>> from services.servel_sync.merge import merge_donations
        >>> result = merge_donations(
        ...     donations,
        ...     persons_by_rut={"12345678-9": "uuid-1"},
        ...     persons_by_name={"juan perez": ["uuid-2"]},
        ...     orgs_by_rut={},
        ...     orgs_by_name={},
        ... )
        >>> print(f"Matched by RUT: {result.donors_matched_by_rut}")
    """
    result = DonationMergeResult(total_records=len(donations))

    for donation in donations:
        # Match donor
        donor_person_id, donor_org_id, donor_matched_by = _match_donor(
            donation,
            persons_by_rut,
            persons_by_name,
            orgs_by_rut,
            orgs_by_name,
        )

        # Track donor metrics
        if donor_matched_by == "RUT":
            result.donors_matched_by_rut += 1
        elif donor_matched_by == "NAME":
            result.donors_matched_by_name += 1
        else:
            result.donors_unmatched += 1

        # Track donor type
        if _is_persona_natural(donation.donor_type):
            result.person_donors += 1
        else:
            result.org_donors += 1

        # Match candidate
        candidate_person_id, candidate_matched_by = _match_candidate(
            donation,
            persons_by_rut,
            persons_by_name,
        )

        # Track candidate metrics
        if candidate_matched_by == "RUT":
            result.candidates_matched_by_rut += 1
        elif candidate_matched_by == "NAME":
            result.candidates_matched_by_name += 1
        else:
            result.candidates_unmatched += 1

        # Create merged donation
        merged = MergedDonation(
            donation=donation,
            donor_person_id=donor_person_id,
            donor_org_id=donor_org_id,
            candidate_person_id=candidate_person_id,
            donor_matched_by=donor_matched_by,
            candidate_matched_by=candidate_matched_by,
        )

        result.merged.append(merged)

    return result
