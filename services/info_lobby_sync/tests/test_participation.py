"""Tests for participation extraction module."""

from datetime import date

import pytest

from ..events import AudienceEvent, DonationEvent, TravelEvent
from ..participation import (
    EntityRef,
    ParticipationEdge,
    ParticipationResult,
    extract_participations,
    _extract_audience_participations,
    _extract_travel_participations,
    _extract_donation_participations,
)


class TestParticipationEdge:
    """Tests for ParticipationEdge dataclass."""

    def test_edge_creation(self):
        """ParticipationEdge should store all fields correctly."""
        edge = ParticipationEdge(
            event_external_id="AUD-123",
            event_type="audience",
            entity_type="person",
            entity_id="uuid-456",
            role="PASIVO",
        )

        assert edge.event_external_id == "AUD-123"
        assert edge.event_type == "audience"
        assert edge.entity_type == "person"
        assert edge.entity_id == "uuid-456"
        assert edge.role == "PASIVO"
        assert edge.source == "infolobby_sparql"

    def test_edge_custom_source(self):
        """ParticipationEdge should allow custom source."""
        edge = ParticipationEdge(
            event_external_id="AUD-123",
            event_type="audience",
            entity_type="person",
            entity_id="uuid-456",
            role="ACTIVO",
            source="custom_source",
        )

        assert edge.source == "custom_source"


class TestEntityRef:
    """Tests for EntityRef dataclass."""

    def test_entity_ref_creation(self):
        """EntityRef should store id and normalized_name."""
        ref = EntityRef(id="uuid-123", normalized_name="juan perez")

        assert ref.id == "uuid-123"
        assert ref.normalized_name == "juan perez"


class TestParticipationResult:
    """Tests for ParticipationResult dataclass."""

    def test_default_values(self):
        """ParticipationResult should have correct defaults."""
        result = ParticipationResult()

        assert result.edges == []
        assert result.unmatched_persons == []
        assert result.unmatched_orgs == []
        assert result.edges_by_role == {}
        assert result.total_edges == 0
        assert result.total_skipped == 0

    def test_to_dict(self):
        """to_dict should serialize result correctly."""
        result = ParticipationResult(
            total_edges=10,
            total_skipped=3,
            edges_by_role={"PASIVO": 5, "ACTIVO": 5},
            unmatched_persons=["person1", "person2"],
            unmatched_orgs=["org1"],
        )

        d = result.to_dict()

        assert d["total_edges"] == 10
        assert d["total_skipped"] == 3
        assert d["edges_by_role"] == {"PASIVO": 5, "ACTIVO": 5}
        assert d["unmatched_persons_count"] == 2
        assert d["unmatched_orgs_count"] == 1
        assert d["unmatched_persons_sample"] == ["person1", "person2"]
        assert d["unmatched_orgs_sample"] == ["org1"]

    def test_to_dict_limits_samples(self):
        """to_dict should limit unmatched samples to 10."""
        result = ParticipationResult(
            unmatched_persons=[f"person{i}" for i in range(20)],
            unmatched_orgs=[f"org{i}" for i in range(15)],
        )

        d = result.to_dict()

        assert len(d["unmatched_persons_sample"]) == 10
        assert len(d["unmatched_orgs_sample"]) == 10


class TestExtractAudienceParticipations:
    """Tests for audience participation extraction."""

    def test_extract_pasivo_match(self):
        """Should create PASIVO edge when person matches."""
        event = AudienceEvent(
            external_id="AUD-123",
            date_start=date(2025, 1, 15),
            pasivo_ref="juan perez",
            activos_refs=[],
            representados_refs=[],
        )

        persons = {
            "juan perez": EntityRef(id="person-uuid-1", normalized_name="juan perez")
        }
        orgs: dict = {}
        result = ParticipationResult()

        _extract_audience_participations(event, persons, orgs, result)

        assert len(result.edges) == 1
        assert result.edges[0].role == "PASIVO"
        assert result.edges[0].entity_id == "person-uuid-1"
        assert result.edges[0].entity_type == "person"
        assert result.total_edges == 1
        assert result.edges_by_role["PASIVO"] == 1

    def test_extract_pasivo_no_match(self):
        """Should track unmatched pasivo reference."""
        event = AudienceEvent(
            external_id="AUD-123",
            date_start=date(2025, 1, 15),
            pasivo_ref="unknown person",
            activos_refs=[],
            representados_refs=[],
        )

        persons: dict = {}
        orgs: dict = {}
        result = ParticipationResult()

        _extract_audience_participations(event, persons, orgs, result)

        assert len(result.edges) == 0
        assert result.total_skipped == 1
        assert "unknown person" in result.unmatched_persons

    def test_extract_activos_match(self):
        """Should create ACTIVO edges for matching persons."""
        event = AudienceEvent(
            external_id="AUD-123",
            date_start=date(2025, 1, 15),
            pasivo_ref=None,
            activos_refs=["maria garcia", "pedro lopez"],
            representados_refs=[],
        )

        persons = {
            "maria garcia": EntityRef(id="person-uuid-2", normalized_name="maria garcia"),
            "pedro lopez": EntityRef(id="person-uuid-3", normalized_name="pedro lopez"),
        }
        orgs: dict = {}
        result = ParticipationResult()

        _extract_audience_participations(event, persons, orgs, result)

        assert len(result.edges) == 2
        assert all(e.role == "ACTIVO" for e in result.edges)
        assert result.edges_by_role["ACTIVO"] == 2

    def test_extract_representados_match(self):
        """Should create REPRESENTADO edges for matching organisations."""
        event = AudienceEvent(
            external_id="AUD-123",
            date_start=date(2025, 1, 15),
            pasivo_ref=None,
            activos_refs=[],
            representados_refs=["empresa abc", "corporacion xyz"],
        )

        persons: dict = {}
        orgs = {
            "empresa abc": EntityRef(id="org-uuid-1", normalized_name="empresa abc"),
            "corporacion xyz": EntityRef(id="org-uuid-2", normalized_name="corporacion xyz"),
        }
        result = ParticipationResult()

        _extract_audience_participations(event, persons, orgs, result)

        assert len(result.edges) == 2
        assert all(e.role == "REPRESENTADO" for e in result.edges)
        assert all(e.entity_type == "organisation" for e in result.edges)
        assert result.edges_by_role["REPRESENTADO"] == 2

    def test_extract_mixed_matches_and_misses(self):
        """Should handle partial matches correctly."""
        event = AudienceEvent(
            external_id="AUD-123",
            date_start=date(2025, 1, 15),
            pasivo_ref="juan perez",
            activos_refs=["maria garcia", "unknown lobbyist"],
            representados_refs=["empresa abc", "unknown org"],
        )

        persons = {
            "juan perez": EntityRef(id="p1", normalized_name="juan perez"),
            "maria garcia": EntityRef(id="p2", normalized_name="maria garcia"),
        }
        orgs = {
            "empresa abc": EntityRef(id="o1", normalized_name="empresa abc"),
        }
        result = ParticipationResult()

        _extract_audience_participations(event, persons, orgs, result)

        assert result.total_edges == 3  # pasivo + 1 activo + 1 representado
        assert result.total_skipped == 2  # 1 activo + 1 org
        assert "unknown lobbyist" in result.unmatched_persons
        assert "unknown org" in result.unmatched_orgs


class TestExtractTravelParticipations:
    """Tests for travel participation extraction."""

    def test_extract_financiadores_match(self):
        """Should create FINANCIADOR edges for matching organisations."""
        event = TravelEvent(
            external_id="VIA-123",
            date_start=date(2025, 2, 1),
            financiadores_refs=["organismo internacional"],
        )

        persons: dict = {}
        orgs = {
            "organismo internacional": EntityRef(id="org-uuid-1", normalized_name="organismo internacional"),
        }
        result = ParticipationResult()

        _extract_travel_participations(event, persons, orgs, result)

        assert len(result.edges) == 1
        assert result.edges[0].role == "FINANCIADOR"
        assert result.edges[0].entity_type == "organisation"
        assert result.edges_by_role["FINANCIADOR"] == 1

    def test_extract_travel_pasivo_if_present(self):
        """Should create PASIVO edge if travel has pasivo_ref."""
        event = TravelEvent(
            external_id="VIA-123",
            date_start=date(2025, 2, 1),
            pasivo_ref="ministro viajero",
            financiadores_refs=[],
        )

        persons = {
            "ministro viajero": EntityRef(id="p1", normalized_name="ministro viajero"),
        }
        orgs: dict = {}
        result = ParticipationResult()

        _extract_travel_participations(event, persons, orgs, result)

        assert len(result.edges) == 1
        assert result.edges[0].role == "PASIVO"


class TestExtractDonationParticipations:
    """Tests for donation participation extraction."""

    def test_extract_donantes_match(self):
        """Should create DONANTE edges for matching organisations."""
        event = DonationEvent(
            external_id="DON-123",
            date_start=date(2025, 3, 10),
            donantes_refs=["fundacion cultural"],
        )

        persons: dict = {}
        orgs = {
            "fundacion cultural": EntityRef(id="org-uuid-1", normalized_name="fundacion cultural"),
        }
        result = ParticipationResult()

        _extract_donation_participations(event, persons, orgs, result)

        assert len(result.edges) == 1
        assert result.edges[0].role == "DONANTE"
        assert result.edges[0].entity_type == "organisation"
        assert result.edges_by_role["DONANTE"] == 1

    def test_extract_donation_pasivo_if_present(self):
        """Should create PASIVO edge if donation has pasivo_ref."""
        event = DonationEvent(
            external_id="DON-123",
            date_start=date(2025, 3, 10),
            pasivo_ref="funcionario receptor",
            donantes_refs=[],
        )

        persons = {
            "funcionario receptor": EntityRef(id="p1", normalized_name="funcionario receptor"),
        }
        orgs: dict = {}
        result = ParticipationResult()

        _extract_donation_participations(event, persons, orgs, result)

        assert len(result.edges) == 1
        assert result.edges[0].role == "PASIVO"


class TestExtractParticipations:
    """Tests for main extract_participations function."""

    def test_extract_from_multiple_event_types(self):
        """Should extract participations from all event types."""
        events = [
            AudienceEvent(
                external_id="AUD-1",
                date_start=date(2025, 1, 1),
                pasivo_ref="juan perez",
                activos_refs=["maria garcia"],
                representados_refs=["empresa abc"],
            ),
            TravelEvent(
                external_id="VIA-1",
                date_start=date(2025, 2, 1),
                financiadores_refs=["org internacional"],
            ),
            DonationEvent(
                external_id="DON-1",
                date_start=date(2025, 3, 1),
                donantes_refs=["fundacion xyz"],
            ),
        ]

        persons = {
            "juan perez": EntityRef(id="p1", normalized_name="juan perez"),
            "maria garcia": EntityRef(id="p2", normalized_name="maria garcia"),
        }
        orgs = {
            "empresa abc": EntityRef(id="o1", normalized_name="empresa abc"),
            "org internacional": EntityRef(id="o2", normalized_name="org internacional"),
            "fundacion xyz": EntityRef(id="o3", normalized_name="fundacion xyz"),
        }

        result = extract_participations(events, persons, orgs)

        assert result.total_edges == 5
        assert result.total_skipped == 0
        assert result.edges_by_role["PASIVO"] == 1
        assert result.edges_by_role["ACTIVO"] == 1
        assert result.edges_by_role["REPRESENTADO"] == 1
        assert result.edges_by_role["FINANCIADOR"] == 1
        assert result.edges_by_role["DONANTE"] == 1

    def test_extract_empty_events(self):
        """Should return empty result for no events."""
        result = extract_participations([], {}, {})

        assert result.total_edges == 0
        assert result.total_skipped == 0
        assert result.edges == []

    def test_extract_no_matches(self):
        """Should track all unmatched when no entities in lookup."""
        events = [
            AudienceEvent(
                external_id="AUD-1",
                date_start=date(2025, 1, 1),
                pasivo_ref="unknown pasivo",
                activos_refs=["unknown activo"],
                representados_refs=["unknown org"],
            ),
        ]

        result = extract_participations(events, {}, {})

        assert result.total_edges == 0
        assert result.total_skipped == 3
        assert "unknown pasivo" in result.unmatched_persons
        assert "unknown activo" in result.unmatched_persons
        assert "unknown org" in result.unmatched_orgs

    def test_idempotency_same_input(self):
        """Running twice with same input should produce same result."""
        events = [
            AudienceEvent(
                external_id="AUD-1",
                date_start=date(2025, 1, 1),
                pasivo_ref="juan perez",
                activos_refs=[],
                representados_refs=[],
            ),
        ]
        persons = {
            "juan perez": EntityRef(id="p1", normalized_name="juan perez"),
        }

        result1 = extract_participations(events, persons, {})
        result2 = extract_participations(events, persons, {})

        assert result1.total_edges == result2.total_edges
        assert len(result1.edges) == len(result2.edges)
        assert result1.edges[0].entity_id == result2.edges[0].entity_id


class TestExactMatchOnly:
    """Tests to verify exact match behavior (no fuzzy matching)."""

    def test_case_sensitivity(self):
        """Normalized names are already lowercase, match should be exact."""
        event = AudienceEvent(
            external_id="AUD-1",
            date_start=date(2025, 1, 1),
            pasivo_ref="juan perez",  # lowercase from normalization
            activos_refs=[],
            representados_refs=[],
        )

        # Different case should NOT match (names should be pre-normalized)
        persons = {
            "Juan Perez": EntityRef(id="p1", normalized_name="Juan Perez"),
        }

        result = extract_participations([event], persons, {})

        assert result.total_edges == 0
        assert result.total_skipped == 1

    def test_no_partial_match(self):
        """Should not match partial names."""
        event = AudienceEvent(
            external_id="AUD-1",
            date_start=date(2025, 1, 1),
            pasivo_ref="juan perez garcia",
            activos_refs=[],
            representados_refs=[],
        )

        persons = {
            "juan perez": EntityRef(id="p1", normalized_name="juan perez"),
        }

        result = extract_participations([event], persons, {})

        assert result.total_edges == 0
        assert result.total_skipped == 1

    def test_exact_match_works(self):
        """Exact normalized name should match."""
        event = AudienceEvent(
            external_id="AUD-1",
            date_start=date(2025, 1, 1),
            pasivo_ref="juan perez garcia",
            activos_refs=[],
            representados_refs=[],
        )

        persons = {
            "juan perez garcia": EntityRef(id="p1", normalized_name="juan perez garcia"),
        }

        result = extract_participations([event], persons, {})

        assert result.total_edges == 1
        assert result.edges[0].entity_id == "p1"


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_refs_in_event(self):
        """Events with no refs should produce no edges."""
        event = AudienceEvent(
            external_id="AUD-1",
            date_start=date(2025, 1, 1),
            pasivo_ref=None,
            activos_refs=[],
            representados_refs=[],
        )

        result = extract_participations([event], {}, {})

        assert result.total_edges == 0
        assert result.total_skipped == 0

    def test_duplicate_refs_in_event(self):
        """Duplicate refs should create duplicate edges (caller handles dedup)."""
        event = AudienceEvent(
            external_id="AUD-1",
            date_start=date(2025, 1, 1),
            pasivo_ref=None,
            activos_refs=["juan perez", "juan perez"],  # Same person twice
            representados_refs=[],
        )

        persons = {
            "juan perez": EntityRef(id="p1", normalized_name="juan perez"),
        }

        result = extract_participations([event], persons, {})

        # Creates 2 edges (persistence layer handles unique constraint)
        assert result.total_edges == 2
        assert result.edges_by_role["ACTIVO"] == 2

    def test_event_external_id_preserved(self):
        """Edge should preserve event external_id."""
        event = AudienceEvent(
            external_id="AUD-UNIQUE-ID-123",
            date_start=date(2025, 1, 1),
            pasivo_ref="juan perez",
            activos_refs=[],
            representados_refs=[],
        )

        persons = {
            "juan perez": EntityRef(id="p1", normalized_name="juan perez"),
        }

        result = extract_participations([event], persons, {})

        assert result.edges[0].event_external_id == "AUD-UNIQUE-ID-123"

    def test_event_type_preserved(self):
        """Edge should preserve event type."""
        events = [
            AudienceEvent(
                external_id="AUD-1",
                date_start=None,
                pasivo_ref="juan perez",
                activos_refs=[],
                representados_refs=[],
            ),
            TravelEvent(
                external_id="VIA-1",
                date_start=None,
                pasivo_ref="juan perez",
                financiadores_refs=[],
            ),
        ]

        persons = {
            "juan perez": EntityRef(id="p1", normalized_name="juan perez"),
        }

        result = extract_participations(events, persons, {})

        event_types = [e.event_type for e in result.edges]
        assert "audience" in event_types
        assert "travel" in event_types
