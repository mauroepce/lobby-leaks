"""
Persistence layer for SERVEL donation events and edges.

Persists MergedDonation objects into the canonical graph:
- DonationEvent nodes in the Event table
- Directed edges in the Edge table:
  - Donor → DonationEvent labeled "DONANTE" (optional)
  - DonationEvent → Candidate labeled "DONATARIO" (mandatory)

This module:
- Creates Event records for matched donations
- Creates Edge records linking events to persons/organisations
- Uses UPSERT for idempotency
- Stores source="servel" in metadata JSON
- ONLY creates Event if candidate is matched (hard rule)
- Donor edge is optional, candidate edge is mandatory
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import json
import uuid

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .merge import MergedDonation, DonationMergeResult


@dataclass
class DonationPersistResult:
    """Result of donation persistence operation with metrics."""
    events_created: int = 0
    events_existing: int = 0

    donor_edges_created: int = 0
    candidate_edges_created: int = 0

    skipped_no_candidate: int = 0
    skipped_duplicates: int = 0
    skipped_invalid: int = 0

    errors: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    @property
    def duration_seconds(self) -> float:
        """Calculate duration in seconds."""
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return 0.0

    @property
    def total_processed(self) -> int:
        """Total donations processed."""
        return (
            self.events_created
            + self.events_existing
            + self.skipped_no_candidate
            + self.skipped_duplicates
            + self.skipped_invalid
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "events_created": self.events_created,
            "events_existing": self.events_existing,
            "donor_edges_created": self.donor_edges_created,
            "candidate_edges_created": self.candidate_edges_created,
            "skipped_no_candidate": self.skipped_no_candidate,
            "skipped_duplicates": self.skipped_duplicates,
            "skipped_invalid": self.skipped_invalid,
            "total_processed": self.total_processed,
            "errors": self.errors,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_seconds": self.duration_seconds,
        }


def _build_external_id(checksum: str) -> str:
    """
    Build external ID for SERVEL donation event.

    Format: SERVEL:{checksum}
    The checksum comes from ParsedDonation.checksum (SHA256).
    """
    return f"SERVEL:{checksum}"


def _build_event_metadata(merged: MergedDonation) -> Dict[str, Any]:
    """
    Build metadata JSON for the event.

    Includes source, amount, and donation_date.
    """
    donation = merged.donation
    metadata = {
        "source": "servel",
        "amount": donation.amount_clp,
        "campaign_year": donation.campaign_year,
        "donor_matched_by": merged.donor_matched_by,
        "candidate_matched_by": merged.candidate_matched_by,
    }

    if donation.donation_date:
        metadata["donation_date"] = donation.donation_date.isoformat()

    if donation.donor_name:
        metadata["donor_name"] = donation.donor_name

    if donation.candidate_name:
        metadata["candidate_name"] = donation.candidate_name

    if donation.election_type:
        metadata["election_type"] = donation.election_type

    if donation.candidate_party:
        metadata["candidate_party"] = donation.candidate_party

    return metadata


def _persist_event(
    conn,
    merged: MergedDonation,
    tenant_code: str,
) -> tuple[Optional[str], str]:
    """
    Persist a single donation event.

    Returns:
        Tuple of (event_id, outcome) where outcome is:
        - "created": new event was inserted
        - "existing": event already existed (ON CONFLICT)
        - "skipped_no_candidate": no candidate match
        - "skipped_invalid": invalid data

    Note: Only creates Event if candidate_person_id is present.
    """
    # Hard rule: must have candidate match
    if not merged.candidate_person_id:
        return None, "skipped_no_candidate"

    # Validate checksum exists
    donation = merged.donation
    if not donation.checksum:
        return None, "skipped_invalid"

    external_id = _build_external_id(donation.checksum)
    metadata = _build_event_metadata(merged)
    event_date = donation.donation_date

    now = datetime.utcnow()
    new_id = str(uuid.uuid4())

    # UPSERT with ON CONFLICT DO NOTHING
    insert_query = text("""
        INSERT INTO "Event" (
            id, "externalId", "tenantCode", kind,
            date, metadata,
            "createdAt", "updatedAt"
        )
        VALUES (
            :id, :external_id, :tenant_code, :kind,
            :date, :metadata::jsonb,
            :created_at, :updated_at
        )
        ON CONFLICT ("externalId", "tenantCode")
        DO NOTHING
        RETURNING id
    """)

    result = conn.execute(insert_query, {
        "id": new_id,
        "external_id": external_id,
        "tenant_code": tenant_code,
        "kind": "donation",
        "date": event_date,
        "metadata": json.dumps(metadata),
        "created_at": now,
        "updated_at": now,
    })

    row = result.fetchone()

    if row:
        # New event was created
        return new_id, "created"
    else:
        # Event already existed, fetch its ID
        select_query = text("""
            SELECT id FROM "Event"
            WHERE "externalId" = :external_id
              AND "tenantCode" = :tenant_code
        """)
        existing = conn.execute(select_query, {
            "external_id": external_id,
            "tenant_code": tenant_code,
        }).fetchone()

        if existing:
            event_id = existing[0] if not hasattr(existing, '_mapping') else existing._mapping['id']
            return event_id, "existing"
        else:
            return None, "skipped_invalid"


def _persist_donor_edge(
    conn,
    event_id: str,
    merged: MergedDonation,
    tenant_code: str,
) -> str:
    """
    Persist donor edge: Event → Donor (Person or Org).

    Returns: "created" or "duplicate"
    """
    # Determine target entity
    if merged.donor_person_id:
        to_person_id = merged.donor_person_id
        to_org_id = None
    elif merged.donor_org_id:
        to_person_id = None
        to_org_id = merged.donor_org_id
    else:
        # No donor match - this is allowed (optional edge)
        return "skipped"

    metadata = json.dumps({"source": "servel"})
    now = datetime.utcnow()
    new_id = str(uuid.uuid4())

    insert_query = text("""
        INSERT INTO "Edge" (
            id, "tenantCode", "eventId",
            "fromPersonId", "fromOrgId",
            "toPersonId", "toOrgId",
            label, metadata,
            "createdAt", "updatedAt"
        )
        VALUES (
            :id, :tenant_code, :event_id,
            NULL, NULL,
            :to_person_id, :to_org_id,
            :label, :metadata::jsonb,
            :created_at, :updated_at
        )
        ON CONFLICT ("eventId", "fromPersonId", "fromOrgId", "toPersonId", "toOrgId", "label")
        DO NOTHING
        RETURNING id
    """)

    result = conn.execute(insert_query, {
        "id": new_id,
        "tenant_code": tenant_code,
        "event_id": event_id,
        "to_person_id": to_person_id,
        "to_org_id": to_org_id,
        "label": "DONANTE",
        "metadata": metadata,
        "created_at": now,
        "updated_at": now,
    })

    row = result.fetchone()
    return "created" if row else "duplicate"


def _persist_candidate_edge(
    conn,
    event_id: str,
    merged: MergedDonation,
    tenant_code: str,
) -> str:
    """
    Persist candidate edge: Event → Candidate (always Person).

    Returns: "created" or "duplicate"
    """
    # Candidate is always a person
    if not merged.candidate_person_id:
        return "skipped"

    metadata = json.dumps({"source": "servel"})
    now = datetime.utcnow()
    new_id = str(uuid.uuid4())

    insert_query = text("""
        INSERT INTO "Edge" (
            id, "tenantCode", "eventId",
            "fromPersonId", "fromOrgId",
            "toPersonId", "toOrgId",
            label, metadata,
            "createdAt", "updatedAt"
        )
        VALUES (
            :id, :tenant_code, :event_id,
            NULL, NULL,
            :to_person_id, NULL,
            :label, :metadata::jsonb,
            :created_at, :updated_at
        )
        ON CONFLICT ("eventId", "fromPersonId", "fromOrgId", "toPersonId", "toOrgId", "label")
        DO NOTHING
        RETURNING id
    """)

    result = conn.execute(insert_query, {
        "id": new_id,
        "tenant_code": tenant_code,
        "event_id": event_id,
        "to_person_id": merged.candidate_person_id,
        "label": "DONATARIO",
        "metadata": metadata,
        "created_at": now,
        "updated_at": now,
    })

    row = result.fetchone()
    return "created" if row else "duplicate"


def persist_donation_events(
    merge_result: DonationMergeResult,
    engine: Engine,
    tenant_code: str = "CL",
) -> DonationPersistResult:
    """
    Persist merged SERVEL donations as Events and Edges.

    Creates:
    - DonationEvent in Event table (kind="donation")
    - DONANTE edge: Event → Donor (optional, if matched)
    - DONATARIO edge: Event → Candidate (mandatory)

    Hard rules:
    - Event is ONLY created if candidate_person_id exists
    - Candidate edge is mandatory, donor edge is optional
    - Never creates orphan Events

    Uses UPSERT (ON CONFLICT DO NOTHING) for idempotency.

    Args:
        merge_result: DonationMergeResult from merge_donations()
        engine: SQLAlchemy database engine
        tenant_code: Tenant code for data isolation (default "CL")

    Returns:
        DonationPersistResult with operation counts

    Example:
        >>> from services.servel_sync.donation_persistence import (
        ...     persist_donation_events
        ... )
        >>> result = persist_donation_events(merge_result, engine, "CL")
        >>> print(f"Events created: {result.events_created}")
        >>> print(f"Candidate edges: {result.candidate_edges_created}")
    """
    result = DonationPersistResult(started_at=datetime.utcnow())

    if not merge_result.merged:
        result.finished_at = datetime.utcnow()
        return result

    try:
        with engine.begin() as conn:
            for merged in merge_result.merged:
                try:
                    # Step 1: Persist event (only if candidate matched)
                    event_id, event_outcome = _persist_event(
                        conn, merged, tenant_code
                    )

                    if event_outcome == "skipped_no_candidate":
                        result.skipped_no_candidate += 1
                        continue

                    if event_outcome == "skipped_invalid":
                        result.skipped_invalid += 1
                        continue

                    if event_outcome == "created":
                        result.events_created += 1
                    elif event_outcome == "existing":
                        result.events_existing += 1

                    # Step 2: Persist donor edge (optional)
                    if event_id:
                        donor_outcome = _persist_donor_edge(
                            conn, event_id, merged, tenant_code
                        )
                        if donor_outcome == "created":
                            result.donor_edges_created += 1
                        elif donor_outcome == "duplicate":
                            result.skipped_duplicates += 1

                    # Step 3: Persist candidate edge (mandatory)
                    if event_id:
                        candidate_outcome = _persist_candidate_edge(
                            conn, event_id, merged, tenant_code
                        )
                        if candidate_outcome == "created":
                            result.candidate_edges_created += 1
                        elif candidate_outcome == "duplicate":
                            result.skipped_duplicates += 1

                except Exception as e:
                    checksum = merged.donation.checksum or "unknown"
                    result.errors.append(
                        f"Donation {checksum}: {str(e)}"
                    )
                    result.skipped_invalid += 1

    except Exception as e:
        result.errors.append(f"Database error: {str(e)}")

    result.finished_at = datetime.utcnow()
    return result
