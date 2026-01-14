"""
Tests for SERVEL entity loaders.

Tests loading of Person and Organisation lookups from DB.
Uses mocked SQL results (no real database).
"""

import pytest
from unittest.mock import MagicMock, patch

from ..loaders import load_person_lookups, load_org_lookups


# ============================================================================
# Mock Row Helper
# ============================================================================

class MockRow:
    """Mock SQLAlchemy row with _mapping attribute."""

    def __init__(self, data: dict):
        self._mapping = data


def create_mock_conn(rows: list) -> MagicMock:
    """Create a mock connection that returns given rows."""
    mock_conn = MagicMock()
    mock_result = MagicMock()
    mock_result.__iter__ = lambda self: iter(rows)
    mock_conn.execute.return_value = mock_result
    return mock_conn


# ============================================================================
# Test load_person_lookups
# ============================================================================

class TestLoadPersonLookups:
    """Tests for Person lookup loading."""

    def test_load_single_person_with_valid_rut(self):
        """Single person with valid RUT loads into both lookups."""
        rows = [
            MockRow({
                "id": "uuid-person-1",
                "rut": "12345678-5",  # Valid RUT
                "normalizedName": "juan perez",
            })
        ]
        mock_conn = create_mock_conn(rows)

        by_rut, by_name = load_person_lookups(mock_conn, "CL")

        assert by_rut == {"12345678-5": "uuid-person-1"}
        assert by_name == {"juan perez": ["uuid-person-1"]}

    def test_load_person_with_invalid_rut_excluded_from_rut_lookup(self):
        """Invalid RUT excluded from by_rut but included in by_name."""
        rows = [
            MockRow({
                "id": "uuid-person-1",
                "rut": "invalid-rut",
                "normalizedName": "juan perez",
            })
        ]
        mock_conn = create_mock_conn(rows)

        by_rut, by_name = load_person_lookups(mock_conn, "CL")

        assert by_rut == {}  # Invalid RUT not included
        assert by_name == {"juan perez": ["uuid-person-1"]}

    def test_load_person_with_null_rut(self):
        """Null RUT excluded from by_rut but included in by_name."""
        rows = [
            MockRow({
                "id": "uuid-person-1",
                "rut": None,
                "normalizedName": "juan perez",
            })
        ]
        mock_conn = create_mock_conn(rows)

        by_rut, by_name = load_person_lookups(mock_conn, "CL")

        assert by_rut == {}
        assert by_name == {"juan perez": ["uuid-person-1"]}

    def test_load_person_with_empty_rut(self):
        """Empty string RUT excluded from by_rut."""
        rows = [
            MockRow({
                "id": "uuid-person-1",
                "rut": "",
                "normalizedName": "juan perez",
            })
        ]
        mock_conn = create_mock_conn(rows)

        by_rut, by_name = load_person_lookups(mock_conn, "CL")

        assert by_rut == {}
        assert by_name == {"juan perez": ["uuid-person-1"]}

    def test_name_collisions_preserved(self):
        """Multiple persons with same name creates list."""
        rows = [
            MockRow({
                "id": "uuid-person-1",
                "rut": "12345678-5",  # Valid RUT
                "normalizedName": "juan perez",
            }),
            MockRow({
                "id": "uuid-person-2",
                "rut": "98765432-5",  # Valid RUT (different)
                "normalizedName": "juan perez",  # Same name!
            }),
        ]
        mock_conn = create_mock_conn(rows)

        by_rut, by_name = load_person_lookups(mock_conn, "CL")

        # Both in RUT lookup (different RUTs)
        assert by_rut == {
            "12345678-5": "uuid-person-1",
            "98765432-5": "uuid-person-2",
        }
        # Collision preserved in name lookup
        assert by_name == {
            "juan perez": ["uuid-person-1", "uuid-person-2"],
        }

    def test_multiple_different_persons(self):
        """Multiple persons with different names."""
        rows = [
            MockRow({
                "id": "uuid-person-1",
                "rut": "12345678-5",
                "normalizedName": "juan perez",
            }),
            MockRow({
                "id": "uuid-person-2",
                "rut": "11111111-1",
                "normalizedName": "maria lopez",
            }),
        ]
        mock_conn = create_mock_conn(rows)

        by_rut, by_name = load_person_lookups(mock_conn, "CL")

        assert by_rut == {
            "12345678-5": "uuid-person-1",
            "11111111-1": "uuid-person-2",
        }
        assert by_name == {
            "juan perez": ["uuid-person-1"],
            "maria lopez": ["uuid-person-2"],
        }

    def test_empty_result(self):
        """Empty DB returns empty lookups."""
        mock_conn = create_mock_conn([])

        by_rut, by_name = load_person_lookups(mock_conn, "CL")

        assert by_rut == {}
        assert by_name == {}

    def test_ids_are_uuid_strings(self):
        """Verify IDs are stored as strings (UUID format)."""
        rows = [
            MockRow({
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "rut": "12345678-5",
                "normalizedName": "test person",
            })
        ]
        mock_conn = create_mock_conn(rows)

        by_rut, by_name = load_person_lookups(mock_conn, "CL")

        # Verify type is string
        assert isinstance(by_rut["12345678-5"], str)
        assert isinstance(by_name["test person"][0], str)
        # Verify value
        assert by_rut["12345678-5"] == "550e8400-e29b-41d4-a716-446655440000"

    def test_tenant_code_passed_to_query(self):
        """Verify tenant_code is passed to SQL query."""
        mock_conn = create_mock_conn([])

        load_person_lookups(mock_conn, "CL")

        # Check execute was called with tenant_code
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        # Parameters are passed as second positional arg
        assert call_args[0][1]["tenant_code"] == "CL"

    def test_null_normalized_name_excluded(self):
        """Person with null normalizedName excluded from name lookup."""
        rows = [
            MockRow({
                "id": "uuid-person-1",
                "rut": "12345678-5",
                "normalizedName": None,
            })
        ]
        mock_conn = create_mock_conn(rows)

        by_rut, by_name = load_person_lookups(mock_conn, "CL")

        assert by_rut == {"12345678-5": "uuid-person-1"}
        assert by_name == {}  # No name to lookup


# ============================================================================
# Test load_org_lookups
# ============================================================================

class TestLoadOrgLookups:
    """Tests for Organisation lookup loading."""

    def test_load_single_org_with_valid_rut(self):
        """Single org with valid RUT loads into both lookups."""
        rows = [
            MockRow({
                "id": "uuid-org-1",
                "rut": "76543210-3",  # Valid RUT
                "normalizedName": "empresa xyz",
            })
        ]
        mock_conn = create_mock_conn(rows)

        by_rut, by_name = load_org_lookups(mock_conn, "CL")

        assert by_rut == {"76543210-3": "uuid-org-1"}
        assert by_name == {"empresa xyz": ["uuid-org-1"]}

    def test_load_org_with_invalid_rut_excluded(self):
        """Invalid RUT excluded from by_rut."""
        rows = [
            MockRow({
                "id": "uuid-org-1",
                "rut": "bad-rut",
                "normalizedName": "empresa xyz",
            })
        ]
        mock_conn = create_mock_conn(rows)

        by_rut, by_name = load_org_lookups(mock_conn, "CL")

        assert by_rut == {}
        assert by_name == {"empresa xyz": ["uuid-org-1"]}

    def test_org_name_collisions_preserved(self):
        """Multiple orgs with same name creates list."""
        rows = [
            MockRow({
                "id": "uuid-org-1",
                "rut": "76543210-3",  # Valid RUT
                "normalizedName": "empresa abc",
            }),
            MockRow({
                "id": "uuid-org-2",
                "rut": "77777777-7",  # Valid RUT
                "normalizedName": "empresa abc",  # Same name!
            }),
        ]
        mock_conn = create_mock_conn(rows)

        by_rut, by_name = load_org_lookups(mock_conn, "CL")

        assert by_name == {
            "empresa abc": ["uuid-org-1", "uuid-org-2"],
        }

    def test_empty_result(self):
        """Empty DB returns empty lookups."""
        mock_conn = create_mock_conn([])

        by_rut, by_name = load_org_lookups(mock_conn, "CL")

        assert by_rut == {}
        assert by_name == {}

    def test_org_ids_are_uuid_strings(self):
        """Verify org IDs are stored as strings."""
        rows = [
            MockRow({
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "rut": "76543210-3",  # Valid RUT
                "normalizedName": "test org",
            })
        ]
        mock_conn = create_mock_conn(rows)

        by_rut, by_name = load_org_lookups(mock_conn, "CL")

        assert isinstance(by_rut["76543210-3"], str)
        assert by_rut["76543210-3"] == "550e8400-e29b-41d4-a716-446655440001"


# ============================================================================
# Test RUT validation behavior
# ============================================================================

class TestRutValidation:
    """Tests verifying RUT validation behavior."""

    def test_valid_rut_included_in_lookup(self):
        """Valid RUTs are included in the by_rut lookup."""
        rows = [
            MockRow({
                "id": "uuid-1",
                "rut": "12345678-5",  # Valid RUT
                "normalizedName": "test",
            }),
        ]
        mock_conn = create_mock_conn(rows)

        by_rut, _ = load_person_lookups(mock_conn, "CL")

        assert "12345678-5" in by_rut

    def test_invalid_rut_excluded_from_lookup(self):
        """Invalid RUTs are excluded from the by_rut lookup."""
        rows = [
            MockRow({
                "id": "uuid-1",
                "rut": "12345678-0",  # Invalid RUT (wrong check digit)
                "normalizedName": "test",
            }),
        ]
        mock_conn = create_mock_conn(rows)

        by_rut, _ = load_person_lookups(mock_conn, "CL")

        assert "12345678-0" not in by_rut

    def test_null_rut_excluded_from_lookup(self):
        """Null RUTs are excluded from the by_rut lookup."""
        rows = [
            MockRow({
                "id": "uuid-1",
                "rut": None,
                "normalizedName": "test",
            }),
        ]
        mock_conn = create_mock_conn(rows)

        by_rut, by_name = load_person_lookups(mock_conn, "CL")

        assert len(by_rut) == 0
        assert "test" in by_name  # But name lookup still works
