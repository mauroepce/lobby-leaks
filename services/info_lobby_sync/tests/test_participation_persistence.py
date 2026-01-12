"""Tests for participation persistence module."""

import json
import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

from ..participation import ParticipationEdge
from ..participation_persistence import (
    ParticipationPersistResult,
    persist_participations,
    _load_events_dict,
    _persist_edge,
    _map_event_type_to_kind,
    load_events_for_persistence,
)


class TestParticipationPersistResult:
    """Tests for ParticipationPersistResult dataclass."""

    def test_default_values(self):
        """Default values should be zeros and empty lists."""
        result = ParticipationPersistResult()

        assert result.inserted_edges == 0
        assert result.skipped_missing_event == 0
        assert result.skipped_duplicates == 0
        assert result.edges_by_role == {}
        assert result.errors == []

    def test_total_processed(self):
        """total_processed should sum all outcomes."""
        result = ParticipationPersistResult(
            inserted_edges=10,
            skipped_missing_event=3,
            skipped_duplicates=2,
        )

        assert result.total_processed == 15

    def test_duration_calculation(self):
        """Duration should calculate correctly."""
        start = datetime(2025, 1, 1, 10, 0, 0)
        end = datetime(2025, 1, 1, 10, 0, 45)

        result = ParticipationPersistResult(
            started_at=start,
            finished_at=end
        )

        assert result.duration_seconds == 45.0

    def test_duration_without_times(self):
        """Duration should be 0 if times not set."""
        result = ParticipationPersistResult()
        assert result.duration_seconds == 0.0

    def test_to_dict(self):
        """to_dict should serialize all fields."""
        result = ParticipationPersistResult(
            inserted_edges=5,
            skipped_missing_event=2,
            skipped_duplicates=1,
            edges_by_role={"PASIVO": 3, "ACTIVO": 2},
            errors=["error1"],
            started_at=datetime(2025, 1, 1, 10, 0, 0),
            finished_at=datetime(2025, 1, 1, 10, 0, 10),
        )

        d = result.to_dict()

        assert d["inserted_edges"] == 5
        assert d["skipped_missing_event"] == 2
        assert d["skipped_duplicates"] == 1
        assert d["edges_by_role"] == {"PASIVO": 3, "ACTIVO": 2}
        assert d["total_processed"] == 8
        assert d["errors"] == ["error1"]
        assert d["duration_seconds"] == 10.0


class TestMapEventTypeToKind:
    """Tests for event type mapping."""

    def test_audience_mapping(self):
        assert _map_event_type_to_kind("audience") == "audience"

    def test_travel_mapping(self):
        assert _map_event_type_to_kind("travel") == "travel"

    def test_donation_mapping(self):
        assert _map_event_type_to_kind("donation") == "donation"

    def test_unknown_passthrough(self):
        """Unknown types should pass through unchanged."""
        assert _map_event_type_to_kind("unknown") == "unknown"


class TestLoadEventsDict:
    """Tests for _load_events_dict function."""

    def test_load_empty_result(self):
        """Empty DB should return empty dict."""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__ = Mock(return_value=iter([]))
        mock_conn.execute.return_value = mock_result

        events = _load_events_dict(mock_conn, "CL")

        assert events == {}

    def test_load_events_with_mapping(self):
        """Should create correct key format."""
        mock_conn = MagicMock()

        # Mock rows with _mapping attribute
        mock_row = MagicMock()
        mock_row._mapping = {
            'id': 'event-uuid-1',
            'externalId': 'AUD-123',
            'kind': 'audience',
        }

        mock_result = MagicMock()
        mock_result.__iter__ = Mock(return_value=iter([mock_row]))
        mock_conn.execute.return_value = mock_result

        events = _load_events_dict(mock_conn, "CL")

        assert "AUD-123:audience" in events
        assert events["AUD-123:audience"] == "event-uuid-1"

    def test_load_events_tuple_result(self):
        """Should handle tuple results without _mapping."""
        mock_conn = MagicMock()

        # Mock row without _mapping (tuple-like)
        mock_row = MagicMock()
        mock_row._mapping = None
        del mock_row._mapping  # Remove attribute
        mock_row.__getitem__ = lambda self, i: ["event-uuid-1", "VIA-456", "travel"][i]

        mock_result = MagicMock()
        mock_result.__iter__ = Mock(return_value=iter([mock_row]))
        mock_conn.execute.return_value = mock_result

        events = _load_events_dict(mock_conn, "CL")

        assert "VIA-456:travel" in events
        assert events["VIA-456:travel"] == "event-uuid-1"


class TestPersistEdge:
    """Tests for _persist_edge function."""

    def test_persist_person_participation(self):
        """Should persist person participation with correct fields."""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("new-edge-id",)
        mock_conn.execute.return_value = mock_result

        edge = ParticipationEdge(
            event_external_id="AUD-123",
            event_type="audience",
            entity_type="person",
            entity_id="person-uuid-1",
            role="PASIVO",
        )

        events_lookup = {"AUD-123:audience": "event-uuid-1"}

        outcome = _persist_edge(mock_conn, edge, events_lookup, "CL")

        assert outcome == "inserted"

        # Verify the SQL was called with correct params
        call_args = mock_conn.execute.call_args
        params = call_args[0][1]

        assert params["event_id"] == "event-uuid-1"
        assert params["to_person_id"] == "person-uuid-1"
        assert params["to_org_id"] is None
        assert params["label"] == "PASIVO"
        assert '"source": "infolobby_sparql"' in params["metadata"]

    def test_persist_organisation_participation(self):
        """Should persist organisation participation with correct fields."""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("new-edge-id",)
        mock_conn.execute.return_value = mock_result

        edge = ParticipationEdge(
            event_external_id="VIA-456",
            event_type="travel",
            entity_type="organisation",
            entity_id="org-uuid-1",
            role="FINANCIADOR",
        )

        events_lookup = {"VIA-456:travel": "event-uuid-2"}

        outcome = _persist_edge(mock_conn, edge, events_lookup, "CL")

        assert outcome == "inserted"

        call_args = mock_conn.execute.call_args
        params = call_args[0][1]

        assert params["event_id"] == "event-uuid-2"
        assert params["to_person_id"] is None
        assert params["to_org_id"] == "org-uuid-1"
        assert params["label"] == "FINANCIADOR"

    def test_persist_missing_event(self):
        """Should return missing_event when event not found."""
        mock_conn = MagicMock()

        edge = ParticipationEdge(
            event_external_id="UNKNOWN-999",
            event_type="audience",
            entity_type="person",
            entity_id="person-uuid-1",
            role="PASIVO",
        )

        events_lookup = {}  # Empty lookup

        outcome = _persist_edge(mock_conn, edge, events_lookup, "CL")

        assert outcome == "missing_event"
        # Should not have called execute
        mock_conn.execute.assert_not_called()

    def test_persist_duplicate_edge(self):
        """Should return duplicate when conflict occurs."""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None  # No row returned = conflict
        mock_conn.execute.return_value = mock_result

        edge = ParticipationEdge(
            event_external_id="AUD-123",
            event_type="audience",
            entity_type="person",
            entity_id="person-uuid-1",
            role="PASIVO",
        )

        events_lookup = {"AUD-123:audience": "event-uuid-1"}

        outcome = _persist_edge(mock_conn, edge, events_lookup, "CL")

        assert outcome == "duplicate"

    def test_persist_invalid_entity_type(self):
        """Should raise ValueError for invalid entity_type."""
        mock_conn = MagicMock()

        edge = ParticipationEdge(
            event_external_id="AUD-123",
            event_type="audience",
            entity_type="invalid",  # type: ignore
            entity_id="some-id",
            role="PASIVO",
        )

        events_lookup = {"AUD-123:audience": "event-uuid-1"}

        with pytest.raises(ValueError, match="Invalid entity_type"):
            _persist_edge(mock_conn, edge, events_lookup, "CL")


class TestPersistParticipations:
    """Tests for persist_participations function."""

    def test_persist_empty_list(self):
        """Empty edge list should return empty result."""
        mock_engine = MagicMock()

        result = persist_participations([], mock_engine)

        assert result.inserted_edges == 0
        assert result.skipped_missing_event == 0
        assert result.total_processed == 0

    def test_persist_valid_person_edge(self):
        """Should insert valid person participation."""
        mock_conn = MagicMock()

        # Mock events lookup
        events_result = MagicMock()
        mock_event_row = MagicMock()
        mock_event_row._mapping = {
            'id': 'event-uuid-1',
            'externalId': 'AUD-123',
            'kind': 'audience',
        }
        events_result.__iter__ = Mock(return_value=iter([mock_event_row]))

        # Mock insert result
        insert_result = MagicMock()
        insert_result.fetchone.return_value = ("new-edge-id",)

        call_count = [0]
        def mock_execute(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return events_result
            return insert_result

        mock_conn.execute.side_effect = mock_execute

        mock_engine = MagicMock()
        mock_engine.begin.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = Mock(return_value=None)

        edges = [
            ParticipationEdge(
                event_external_id="AUD-123",
                event_type="audience",
                entity_type="person",
                entity_id="person-uuid-1",
                role="PASIVO",
            )
        ]

        result = persist_participations(edges, mock_engine)

        assert result.inserted_edges == 1
        assert result.edges_by_role["PASIVO"] == 1
        assert result.skipped_missing_event == 0

    def test_persist_valid_organisation_edge(self):
        """Should insert valid organisation participation."""
        mock_conn = MagicMock()

        # Mock events lookup
        events_result = MagicMock()
        mock_event_row = MagicMock()
        mock_event_row._mapping = {
            'id': 'event-uuid-2',
            'externalId': 'DON-456',
            'kind': 'donation',
        }
        events_result.__iter__ = Mock(return_value=iter([mock_event_row]))

        # Mock insert result
        insert_result = MagicMock()
        insert_result.fetchone.return_value = ("new-edge-id",)

        call_count = [0]
        def mock_execute(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return events_result
            return insert_result

        mock_conn.execute.side_effect = mock_execute

        mock_engine = MagicMock()
        mock_engine.begin.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = Mock(return_value=None)

        edges = [
            ParticipationEdge(
                event_external_id="DON-456",
                event_type="donation",
                entity_type="organisation",
                entity_id="org-uuid-1",
                role="DONANTE",
            )
        ]

        result = persist_participations(edges, mock_engine)

        assert result.inserted_edges == 1
        assert result.edges_by_role["DONANTE"] == 1

    def test_persist_missing_event_skipped(self):
        """Should skip edge when event not found."""
        mock_conn = MagicMock()

        # Mock empty events lookup
        events_result = MagicMock()
        events_result.__iter__ = Mock(return_value=iter([]))
        mock_conn.execute.return_value = events_result

        mock_engine = MagicMock()
        mock_engine.begin.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = Mock(return_value=None)

        edges = [
            ParticipationEdge(
                event_external_id="UNKNOWN-999",
                event_type="audience",
                entity_type="person",
                entity_id="person-uuid-1",
                role="PASIVO",
            )
        ]

        result = persist_participations(edges, mock_engine)

        assert result.inserted_edges == 0
        assert result.skipped_missing_event == 1

    def test_persist_duplicate_skipped(self):
        """Should handle duplicate edge correctly."""
        mock_conn = MagicMock()

        # Mock events lookup
        events_result = MagicMock()
        mock_event_row = MagicMock()
        mock_event_row._mapping = {
            'id': 'event-uuid-1',
            'externalId': 'AUD-123',
            'kind': 'audience',
        }
        events_result.__iter__ = Mock(return_value=iter([mock_event_row]))

        # Mock insert returning None (conflict)
        insert_result = MagicMock()
        insert_result.fetchone.return_value = None

        call_count = [0]
        def mock_execute(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return events_result
            return insert_result

        mock_conn.execute.side_effect = mock_execute

        mock_engine = MagicMock()
        mock_engine.begin.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = Mock(return_value=None)

        edges = [
            ParticipationEdge(
                event_external_id="AUD-123",
                event_type="audience",
                entity_type="person",
                entity_id="person-uuid-1",
                role="PASIVO",
            )
        ]

        result = persist_participations(edges, mock_engine)

        assert result.inserted_edges == 0
        assert result.skipped_duplicates == 1

    def test_persist_multiple_roles_same_event(self):
        """Different roles for same event/entity should create multiple edges."""
        mock_conn = MagicMock()

        # Mock events lookup
        events_result = MagicMock()
        mock_event_row = MagicMock()
        mock_event_row._mapping = {
            'id': 'event-uuid-1',
            'externalId': 'AUD-123',
            'kind': 'audience',
        }
        events_result.__iter__ = Mock(return_value=iter([mock_event_row]))

        # Mock insert always succeeds
        insert_result = MagicMock()
        insert_result.fetchone.return_value = ("new-edge-id",)

        call_count = [0]
        def mock_execute(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return events_result
            return insert_result

        mock_conn.execute.side_effect = mock_execute

        mock_engine = MagicMock()
        mock_engine.begin.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = Mock(return_value=None)

        edges = [
            ParticipationEdge(
                event_external_id="AUD-123",
                event_type="audience",
                entity_type="person",
                entity_id="person-uuid-1",
                role="PASIVO",
            ),
            ParticipationEdge(
                event_external_id="AUD-123",
                event_type="audience",
                entity_type="person",
                entity_id="person-uuid-2",
                role="ACTIVO",
            ),
        ]

        result = persist_participations(edges, mock_engine)

        assert result.inserted_edges == 2
        assert result.edges_by_role["PASIVO"] == 1
        assert result.edges_by_role["ACTIVO"] == 1

    def test_persist_handles_db_error(self):
        """Database errors should be captured."""
        mock_engine = MagicMock()
        mock_engine.begin.side_effect = Exception("Connection failed")

        edges = [
            ParticipationEdge(
                event_external_id="AUD-123",
                event_type="audience",
                entity_type="person",
                entity_id="person-uuid-1",
                role="PASIVO",
            )
        ]

        result = persist_participations(edges, mock_engine)

        assert len(result.errors) > 0
        assert "Connection failed" in result.errors[0]


class TestIdempotency:
    """Tests to verify idempotent behavior."""

    def test_same_edge_twice_only_one_row(self):
        """Inserting same edge twice should result in one insert, one duplicate."""
        mock_conn = MagicMock()

        # Mock events lookup
        events_result = MagicMock()
        mock_event_row = MagicMock()
        mock_event_row._mapping = {
            'id': 'event-uuid-1',
            'externalId': 'AUD-123',
            'kind': 'audience',
        }
        events_result.__iter__ = Mock(return_value=iter([mock_event_row]))

        # First insert succeeds, second is conflict
        insert_results = [
            MagicMock(fetchone=Mock(return_value=("id1",))),  # inserted
            MagicMock(fetchone=Mock(return_value=None)),  # conflict
        ]

        call_count = [0]
        def mock_execute(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return events_result
            idx = min(call_count[0] - 2, len(insert_results) - 1)
            return insert_results[idx]

        mock_conn.execute.side_effect = mock_execute

        mock_engine = MagicMock()
        mock_engine.begin.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = Mock(return_value=None)

        # Same edge twice
        edge = ParticipationEdge(
            event_external_id="AUD-123",
            event_type="audience",
            entity_type="person",
            entity_id="person-uuid-1",
            role="PASIVO",
        )

        result = persist_participations([edge, edge], mock_engine)

        assert result.inserted_edges == 1
        assert result.skipped_duplicates == 1


class TestEdgeCases:
    """Edge case tests."""

    def test_persist_with_custom_source(self):
        """Should store custom source in metadata."""
        mock_conn = MagicMock()

        # Mock events lookup
        events_result = MagicMock()
        mock_event_row = MagicMock()
        mock_event_row._mapping = {
            'id': 'event-uuid-1',
            'externalId': 'AUD-123',
            'kind': 'audience',
        }
        events_result.__iter__ = Mock(return_value=iter([mock_event_row]))

        insert_result = MagicMock()
        insert_result.fetchone.return_value = ("new-id",)

        call_count = [0]
        def mock_execute(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return events_result
            return insert_result

        mock_conn.execute.side_effect = mock_execute

        mock_engine = MagicMock()
        mock_engine.begin.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = Mock(return_value=None)

        edge = ParticipationEdge(
            event_external_id="AUD-123",
            event_type="audience",
            entity_type="person",
            entity_id="person-uuid-1",
            role="PASIVO",
            source="custom_source",
        )

        persist_participations([edge], mock_engine)

        # Check that metadata contains custom source
        insert_call = mock_conn.execute.call_args_list[-1]
        params = insert_call[0][1]
        metadata = json.loads(params["metadata"])
        assert metadata["source"] == "custom_source"

    def test_xor_invariant_person(self):
        """Person edge should have toPersonId set, toOrgId null."""
        mock_conn = MagicMock()

        events_result = MagicMock()
        mock_event_row = MagicMock()
        mock_event_row._mapping = {
            'id': 'event-uuid-1',
            'externalId': 'AUD-123',
            'kind': 'audience',
        }
        events_result.__iter__ = Mock(return_value=iter([mock_event_row]))

        insert_result = MagicMock()
        insert_result.fetchone.return_value = ("new-id",)

        call_count = [0]
        def mock_execute(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return events_result
            return insert_result

        mock_conn.execute.side_effect = mock_execute

        mock_engine = MagicMock()
        mock_engine.begin.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = Mock(return_value=None)

        edge = ParticipationEdge(
            event_external_id="AUD-123",
            event_type="audience",
            entity_type="person",
            entity_id="person-uuid-1",
            role="PASIVO",
        )

        persist_participations([edge], mock_engine)

        insert_call = mock_conn.execute.call_args_list[-1]
        params = insert_call[0][1]

        assert params["to_person_id"] == "person-uuid-1"
        assert params["to_org_id"] is None

    def test_xor_invariant_organisation(self):
        """Organisation edge should have toOrgId set, toPersonId null."""
        mock_conn = MagicMock()

        events_result = MagicMock()
        mock_event_row = MagicMock()
        mock_event_row._mapping = {
            'id': 'event-uuid-1',
            'externalId': 'VIA-123',
            'kind': 'travel',
        }
        events_result.__iter__ = Mock(return_value=iter([mock_event_row]))

        insert_result = MagicMock()
        insert_result.fetchone.return_value = ("new-id",)

        call_count = [0]
        def mock_execute(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return events_result
            return insert_result

        mock_conn.execute.side_effect = mock_execute

        mock_engine = MagicMock()
        mock_engine.begin.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = Mock(return_value=None)

        edge = ParticipationEdge(
            event_external_id="VIA-123",
            event_type="travel",
            entity_type="organisation",
            entity_id="org-uuid-1",
            role="FINANCIADOR",
        )

        persist_participations([edge], mock_engine)

        insert_call = mock_conn.execute.call_args_list[-1]
        params = insert_call[0][1]

        assert params["to_person_id"] is None
        assert params["to_org_id"] == "org-uuid-1"

    def test_timestamps_set(self):
        """Should set started_at and finished_at timestamps."""
        mock_engine = MagicMock()
        mock_engine.begin.return_value.__enter__ = Mock(return_value=MagicMock())
        mock_engine.begin.return_value.__exit__ = Mock(return_value=None)

        result = persist_participations([], mock_engine)

        assert result.started_at is not None
        assert result.finished_at is not None
        assert result.finished_at >= result.started_at
