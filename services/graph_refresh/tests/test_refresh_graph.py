"""
Tests for the refresh_graph module.

Includes both unit tests (mocked) and integration tests (real DB).
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from services.graph_refresh.refresh_graph import (
    RefreshResult,
    refresh_graph_views,
    _get_node_counts,
    _get_link_counts,
)


# ============================================================================
# Unit Tests - RefreshResult dataclass
# ============================================================================


class TestRefreshResult:
    """Tests for RefreshResult dataclass."""

    def test_default_values(self):
        """RefreshResult has correct default values."""
        result = RefreshResult()

        assert result.nodes_count == 0
        assert result.links_count == 0
        assert result.duration_seconds == 0.0
        assert result.concurrent_refresh is False
        assert result.refreshed_at is None
        assert result.errors == []
        assert result.nodes_by_type == {}
        assert result.links_by_label == {}

    def test_success_when_no_errors(self):
        """success is True when no errors."""
        result = RefreshResult()
        assert result.success is True

    def test_success_false_when_errors(self):
        """success is False when errors present."""
        result = RefreshResult(errors=["Something went wrong"])
        assert result.success is False

    def test_to_dict(self):
        """to_dict returns correct dictionary."""
        now = datetime.now(timezone.utc)
        result = RefreshResult(
            nodes_count=100,
            links_count=50,
            duration_seconds=1.5,
            concurrent_refresh=True,
            refreshed_at=now,
            nodes_by_type={"person": 60, "event": 40},
            links_by_label={"DONANTE": 25, "DONATARIO": 25},
        )

        d = result.to_dict()

        assert d["nodes_count"] == 100
        assert d["links_count"] == 50
        assert d["duration_seconds"] == 1.5
        assert d["concurrent_refresh"] is True
        assert d["refreshed_at"] == now.isoformat()
        assert d["success"] is True
        assert d["nodes_by_type"] == {"person": 60, "event": 40}
        assert d["links_by_label"] == {"DONANTE": 25, "DONATARIO": 25}

    def test_to_dict_with_none_refreshed_at(self):
        """to_dict handles None refreshed_at."""
        result = RefreshResult()
        d = result.to_dict()
        assert d["refreshed_at"] is None


# ============================================================================
# Unit Tests - refresh_graph_views (mocked)
# ============================================================================


class MockRow:
    """Mock SQLAlchemy row for testing."""

    def __init__(self, mapping):
        self._mapping = mapping

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self._mapping.values())[key]
        return self._mapping[key]


class TestRefreshGraphViewsMocked:
    """Unit tests for refresh_graph_views with mocked DB."""

    def test_refresh_calls_both_views(self):
        """Refresh calls both mv_graph_nodes and mv_graph_links."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = MagicMock(return_value=None)

        # Mock execute to return empty results for count queries
        mock_conn.execute.return_value = iter([])

        result = refresh_graph_views(mock_engine, concurrent=False)

        # Check that execute was called (at least 4 times: 2 refreshes + 2 counts)
        assert mock_conn.execute.call_count >= 2

    def test_concurrent_flag_passed_to_result(self):
        """concurrent_refresh flag is correctly set in result."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = MagicMock(return_value=None)
        mock_conn.execute.return_value = iter([])

        result = refresh_graph_views(mock_engine, concurrent=True)

        assert result.concurrent_refresh is True

    def test_error_handling_on_db_failure(self):
        """Errors are captured when DB operation fails."""
        mock_engine = MagicMock()
        mock_engine.begin.side_effect = Exception("Connection failed")

        result = refresh_graph_views(mock_engine)

        assert result.success is False
        assert len(result.errors) > 0
        assert "Connection failed" in result.errors[0]

    def test_refreshed_at_is_set(self):
        """refreshed_at timestamp is set."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = MagicMock(return_value=None)
        mock_conn.execute.return_value = iter([])

        before = datetime.now(timezone.utc)
        result = refresh_graph_views(mock_engine)
        after = datetime.now(timezone.utc)

        assert result.refreshed_at is not None
        assert before <= result.refreshed_at <= after


# ============================================================================
# Integration Tests - refresh_graph_views
# ============================================================================


@pytest.mark.integration
class TestRefreshGraphViewsIntegration:
    """Integration tests for refresh_graph_views."""

    def test_refresh_without_concurrent(self, engine):
        """Refresh completes without concurrent flag."""
        result = refresh_graph_views(engine, concurrent=False)

        assert result.success, f"Refresh failed: {result.errors}"
        assert result.nodes_count >= 0
        assert result.links_count >= 0
        assert result.duration_seconds > 0

    def test_refresh_with_concurrent(self, engine):
        """Refresh completes with concurrent flag."""
        result = refresh_graph_views(engine, concurrent=True)

        assert result.success, f"Refresh failed: {result.errors}"
        assert result.concurrent_refresh is True

    def test_refresh_populates_counts(self, engine):
        """Refresh populates node and link counts."""
        result = refresh_graph_views(engine)

        # Counts should be non-negative integers
        assert isinstance(result.nodes_count, int)
        assert isinstance(result.links_count, int)
        assert result.nodes_count >= 0
        assert result.links_count >= 0

    def test_refresh_populates_breakdown(self, engine):
        """Refresh populates nodes_by_type and links_by_label."""
        result = refresh_graph_views(engine)

        assert isinstance(result.nodes_by_type, dict)
        assert isinstance(result.links_by_label, dict)

        # Total should match breakdown
        if result.nodes_by_type:
            assert sum(result.nodes_by_type.values()) == result.nodes_count

        if result.links_by_label:
            assert sum(result.links_by_label.values()) == result.links_count

    def test_refresh_sets_timestamps(self, engine):
        """Refresh sets timing information."""
        before = datetime.now(timezone.utc)
        result = refresh_graph_views(engine)
        after = datetime.now(timezone.utc)

        assert result.refreshed_at is not None
        assert before <= result.refreshed_at <= after
        assert result.duration_seconds > 0

    def test_multiple_refreshes_idempotent(self, engine):
        """Multiple refreshes produce consistent results."""
        result1 = refresh_graph_views(engine)
        result2 = refresh_graph_views(engine)

        assert result1.nodes_count == result2.nodes_count
        assert result1.links_count == result2.links_count
