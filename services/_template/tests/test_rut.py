"""
Tests for RUT (Rol Único Tributario) normalization and validation.

Tests the Chilean tax ID normalization and módulo 11 validation algorithm
using parametrized test cases.
"""

import pytest
from services._template.helpers.rut import normalize_rut, validate_rut


class TestNormalizeRUT:
    """Tests for RUT normalization."""

    @pytest.mark.parametrize(
        "input_rut,expected",
        [
            # Valid formats - with dots and hyphen
            ("12.345.678-9", "12345678-9"),
            ("1.234.567-8", "1234567-8"),
            ("11.111.111-1", "11111111-1"),

            # Valid formats - without dots
            ("12345678-9", "12345678-9"),
            ("1234567-8", "1234567-8"),

            # Valid formats - without hyphen
            ("123456785", "12345678-5"),
            ("1000005K", "1000005-K"),

            # With DV = K (uppercase)
            ("1.000.005-K", "1000005-K"),
            ("1000005-K", "1000005-K"),
            ("1000005K", "1000005-K"),

            # With DV = k (lowercase - should be normalized to uppercase)
            ("1.000.005-k", "1000005-K"),
            ("1000005-k", "1000005-K"),
            ("1000005k", "1000005-K"),

            # With extra spaces
            ("  12.345.678-9  ", "12345678-9"),
            (" 12345678-9 ", "12345678-9"),
            ("12 345 678-9", "12345678-9"),

            # Short RUTs (valid)
            ("1-9", "1-9"),
            ("12-3", "12-3"),
            ("123-4", "123-4"),

            # DV = 0
            ("12345678-0", "12345678-0"),
            ("11.111.111-1", "11111111-1"),

            # Invalid cases - should return None
            ("invalid", None),
            ("", None),
            ("12345678-", None),  # Missing DV after hyphen
            ("12345678-99", None),  # DV too long
            ("12345678-A", None),  # Invalid DV (not 0-9 or K)
            ("abc.def.ghi-j", None),  # Non-numeric
            ("123456789-9", None),  # Body too long (9 digits)
            (None, None),  # None input
        ],
        ids=[
            "with_dots_and_hyphen",
            "with_dots_short",
            "with_dots_ones",
            "without_dots",
            "without_dots_short",
            "without_hyphen",
            "without_hyphen_K",
            "DV_K_uppercase_dots",
            "DV_K_uppercase",
            "DV_K_uppercase_no_hyphen",
            "DV_k_lowercase_dots",
            "DV_k_lowercase",
            "DV_k_lowercase_no_hyphen",
            "with_leading_trailing_spaces",
            "with_spaces_around",
            "with_spaces_inside",
            "short_rut_1",
            "short_rut_2",
            "short_rut_3",
            "DV_zero",
            "DV_one_repeated",
            "invalid_text",
            "empty_string",
            "missing_dv_after_hyphen",
            "dv_too_long",
            "invalid_dv_letter",
            "non_numeric",
            "body_too_long",
            "none_input",
        ],
    )
    def test_normalize_rut(self, input_rut, expected):
        """Test RUT normalization with various input formats."""
        assert normalize_rut(input_rut) == expected


class TestValidateRUT:
    """Tests for RUT validation using módulo 11 algorithm."""

    @pytest.mark.parametrize(
        "rut,expected",
        [
            # Valid RUTs (calculated using módulo 11)
            ("11.111.111-1", True),
            ("12.345.678-5", True),
            ("7.654.321-6", True),
            ("1-9", True),
            ("12-4", True),

            # Valid RUTs with DV = K
            ("1.000.005-K", True),
            ("1000005-K", True),
            ("1000005K", True),

            # Valid RUTs with DV = 0
            ("1.000.013-0", True),

            # Invalid RUTs (wrong DV)
            ("12.345.678-9", False),  # Correct DV is 5
            ("11.111.111-2", False),  # Correct DV is 1
            ("7.654.321-0", False),   # Correct DV is 6
            ("12345678-K", False),    # Correct DV is 5

            # Invalid formats (should return False after normalization fails)
            ("invalid", False),
            ("", False),
            (None, False),

            # Edge cases
            ("1.111.111-4", True),  # Short valid RUT
            ("1.111.111-2", False),  # Short invalid RUT
        ],
        ids=[
            "valid_ones",
            "valid_standard",
            "valid_with_zero",
            "valid_short_1",
            "valid_short_2",
            "valid_dv_K_dots",
            "valid_dv_K_no_dots",
            "valid_dv_K_no_hyphen",
            "valid_dv_zero",
            "invalid_wrong_dv_1",
            "invalid_wrong_dv_2",
            "invalid_wrong_dv_3",
            "invalid_wrong_dv_K",
            "invalid_text",
            "invalid_empty",
            "invalid_none",
            "edge_short_valid",
            "edge_short_invalid",
        ],
    )
    def test_validate_rut(self, rut, expected):
        """Test RUT validation using módulo 11 algorithm."""
        assert validate_rut(rut) == expected

    def test_validate_normalized_rut(self):
        """Test that validation works after normalization."""
        # Should normalize and then validate
        assert validate_rut("11.111.111-1") is True
        assert validate_rut("11111111-1") is True
        assert validate_rut("111111111") is True  # Without hyphen

        # All should give same result (invalid)
        assert validate_rut("11.111.111-2") is False
        assert validate_rut("11111111-2") is False
        assert validate_rut("111111112") is False


class TestRUTAdapter:
    """Tests for RUT adapter pattern."""

    def test_can_import_adapter_protocol(self):
        """Test that RUTAdapter protocol can be imported."""
        from services._template.helpers.rut import RUTAdapter
        assert RUTAdapter is not None

    def test_can_import_default_adapter(self):
        """Test that DefaultRUTAdapter can be imported."""
        from services._template.helpers.rut import DefaultRUTAdapter
        assert DefaultRUTAdapter is not None

    def test_default_adapter_works(self):
        """Test that default adapter implementation works."""
        from services._template.helpers.rut import DefaultRUTAdapter

        adapter = DefaultRUTAdapter()
        assert adapter.normalize("12.345.678-5") == "12345678-5"
        assert adapter.validate("12.345.678-5") is True
        assert adapter.validate("12.345.678-9") is False

    def test_can_set_custom_adapter(self):
        """Test that custom adapters can be plugged in."""
        from services._template.helpers.rut import set_adapter, normalize_rut

        # Create a mock adapter
        class MockAdapter:
            def normalize(self, rut: str) -> str | None:
                return "MOCKED"

            def validate(self, rut: str) -> bool:
                return True

        # Set mock adapter
        set_adapter(MockAdapter())

        # Test it's being used
        assert normalize_rut("anything") == "MOCKED"

        # Restore default adapter
        from services._template.helpers.rut import DefaultRUTAdapter
        set_adapter(DefaultRUTAdapter())
