"""Tests for persistence module."""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

from ..persistence import (
    PersistenceResult,
    persist_merge_result,
    _upsert_person,
    _upsert_organisation,
    _extract_nombres,
    _extract_apellidos,
)
from ..merge import MergeResult


class TestPersistenceResult:
    """Tests for PersistenceResult dataclass."""

    def test_default_values(self):
        result = PersistenceResult()
        assert result.persons_inserted == 0
        assert result.persons_updated == 0
        assert result.persons_unchanged == 0
        assert result.orgs_inserted == 0
        assert result.total_processed == 0
        assert result.errors == []

    def test_duration_calculation(self):
        start = datetime(2025, 1, 1, 10, 0, 0)
        end = datetime(2025, 1, 1, 10, 0, 30)

        result = PersistenceResult(
            started_at=start,
            finished_at=end
        )

        assert result.duration_seconds == 30.0

    def test_duration_without_times(self):
        result = PersistenceResult()
        assert result.duration_seconds == 0.0

    def test_to_dict(self):
        result = PersistenceResult(
            persons_inserted=5,
            orgs_inserted=3,
            total_processed=8,
            started_at=datetime(2025, 1, 1, 10, 0, 0),
            finished_at=datetime(2025, 1, 1, 10, 0, 10),
        )

        d = result.to_dict()

        assert d["persons_inserted"] == 5
        assert d["orgs_inserted"] == 3
        assert d["total_processed"] == 8
        assert d["duration_seconds"] == 10.0
        assert "started_at" in d
        assert "finished_at" in d


class TestExtractNames:
    """Tests for name extraction helpers."""

    @pytest.mark.parametrize("full_name,expected_nombres", [
        ("Juan Pérez García", "Juan"),
        ("María", "María"),
        ("Ana María López Silva", "Ana"),
        ("", None),
        (None, None),
    ])
    def test_extract_nombres(self, full_name, expected_nombres):
        assert _extract_nombres(full_name) == expected_nombres

    @pytest.mark.parametrize("full_name,expected_apellidos", [
        ("Juan Pérez García", "Pérez García"),
        ("María", None),
        ("Ana María López Silva", "María López Silva"),
        ("", None),
        (None, None),
    ])
    def test_extract_apellidos(self, full_name, expected_apellidos):
        assert _extract_apellidos(full_name) == expected_apellidos


class TestPersistMergeResult:
    """Tests for persist_merge_result function."""

    def test_persist_empty_result(self):
        """Empty merge result should return empty persistence result."""
        mock_engine = MagicMock()
        mock_engine.begin.return_value.__enter__ = Mock(return_value=MagicMock())
        mock_engine.begin.return_value.__exit__ = Mock(return_value=None)

        merge_result = MergeResult(
            persons=[],
            organisations=[],
            duplicates_found=0,
            merged_count=0,
        )

        result = persist_merge_result(mock_engine, merge_result)

        assert result.total_processed == 0
        assert result.persons_inserted == 0
        assert result.orgs_inserted == 0
        assert len(result.errors) == 0

    def test_persist_handles_db_error(self):
        """Database errors should be captured in result."""
        mock_engine = MagicMock()
        mock_engine.begin.side_effect = Exception("Connection failed")

        merge_result = MergeResult(
            persons=[{"name": "Test", "normalized_name": "test"}],
            organisations=[],
            duplicates_found=0,
            merged_count=1,
        )

        result = persist_merge_result(mock_engine, merge_result)

        assert len(result.errors) > 0
        assert "Connection failed" in result.errors[0]

    def test_persist_counts_persons(self):
        """Should count inserted/updated persons correctly."""
        mock_conn = MagicMock()

        # Mock insert returning inserted=True
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (True,)  # inserted
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.begin.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = Mock(return_value=None)

        merge_result = MergeResult(
            persons=[
                {"name": "Juan Pérez", "normalized_name": "juan perez", "cargo": None},
                {"name": "Ana García", "normalized_name": "ana garcia", "cargo": "Director"},
            ],
            organisations=[],
            duplicates_found=0,
            merged_count=2,
        )

        result = persist_merge_result(mock_engine, merge_result)

        assert result.persons_inserted == 2
        assert result.total_processed == 2

    def test_persist_handles_existing_person(self):
        """Existing persons should be counted as unchanged."""
        mock_conn = MagicMock()

        # Mock for existing person check
        mock_check_result = MagicMock()
        mock_check_result.fetchone.return_value = ("existing_cargo",)
        mock_conn.execute.return_value = mock_check_result

        mock_engine = MagicMock()
        mock_engine.begin.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = Mock(return_value=None)

        merge_result = MergeResult(
            persons=[
                {
                    "name": "Juan Pérez",
                    "normalized_name": "juan perez",
                    "cargo": "New Cargo",
                    "existing_id": "uuid-123",
                },
            ],
            organisations=[],
            duplicates_found=0,
            merged_count=1,
        )

        result = persist_merge_result(mock_engine, merge_result)

        # Existing person with cargo already set → unchanged
        assert result.persons_unchanged == 1


class TestIdempotence:
    """Tests to verify idempotent behavior."""

    def test_same_data_twice_is_idempotent(self):
        """Running same data twice should not create duplicates."""
        mock_conn = MagicMock()

        # First call: insert
        # Second call: update (conflict)
        call_count = [0]

        def mock_execute(*args, **kwargs):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                result.fetchone.return_value = (True,)  # inserted
            else:
                result.fetchone.return_value = (False,)  # updated
            return result

        mock_conn.execute.side_effect = mock_execute

        mock_engine = MagicMock()
        mock_engine.begin.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = Mock(return_value=None)

        merge_result = MergeResult(
            persons=[{"name": "Test", "normalized_name": "test"}],
            organisations=[],
            duplicates_found=0,
            merged_count=1,
        )

        # First persist
        result1 = persist_merge_result(mock_engine, merge_result)

        # Reset connection mock
        call_count[0] = 1  # Skip to "updated" behavior

        # Second persist (same data)
        result2 = persist_merge_result(mock_engine, merge_result)

        # First should insert, second should update
        assert result1.persons_inserted == 1
        assert result2.persons_updated == 1


class TestOrganisationPersistence:
    """Tests for organisation persistence."""

    def test_persist_new_organisation(self):
        """New organisations should be inserted."""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (True,)  # inserted
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.begin.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = Mock(return_value=None)

        merge_result = MergeResult(
            persons=[],
            organisations=[
                {"name": "Empresa ABC", "normalized_name": "empresa abc", "tipo": "representado"},
            ],
            duplicates_found=0,
            merged_count=1,
        )

        result = persist_merge_result(mock_engine, merge_result)

        assert result.orgs_inserted == 1
        assert result.total_processed == 1

    def test_persist_existing_organisation_unchanged(self):
        """Existing org with tipo should be unchanged."""
        mock_conn = MagicMock()
        mock_check = MagicMock()
        mock_check.fetchone.return_value = ("existing_tipo",)
        mock_conn.execute.return_value = mock_check

        mock_engine = MagicMock()
        mock_engine.begin.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = Mock(return_value=None)

        merge_result = MergeResult(
            persons=[],
            organisations=[
                {
                    "name": "Empresa ABC",
                    "normalized_name": "empresa abc",
                    "tipo": "new_tipo",
                    "existing_id": "org-uuid",
                },
            ],
            duplicates_found=0,
            merged_count=1,
        )

        result = persist_merge_result(mock_engine, merge_result)

        assert result.orgs_unchanged == 1
