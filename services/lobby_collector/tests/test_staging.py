"""
Tests for staging layer helpers (normalization and VIEW reading).
"""

import pytest
from services.lobby_collector.staging import (
    normalize_person_name,
    validate_rut,
    normalize_rut,
    extract_rut_from_raw,
)


class TestNormalizePersonName:
    """Test person name normalization."""

    def test_normalize_basic(self):
        """Test basic name normalization."""
        result = normalize_person_name("Juan Carlos", "Pérez García")
        assert result == "juan carlos pérez garcía"

    def test_normalize_with_extra_spaces(self):
        """Test normalization with extra whitespace."""
        result = normalize_person_name("  Mario  ", "  Desbordes  ")
        assert result == "mario desbordes"

    def test_normalize_only_nombres(self):
        """Test with only first names."""
        result = normalize_person_name("Juan", None)
        assert result == "juan"

    def test_normalize_only_apellidos(self):
        """Test with only last names."""
        result = normalize_person_name(None, "Pérez")
        assert result == "pérez"

    def test_normalize_empty(self):
        """Test with empty strings."""
        result = normalize_person_name("", "")
        assert result == ""

    def test_normalize_none(self):
        """Test with None values."""
        result = normalize_person_name(None, None)
        assert result == ""

    def test_normalize_multiple_spaces(self):
        """Test with multiple spaces between words."""
        result = normalize_person_name("Juan    Carlos", "Pérez    García")
        assert result == "juan carlos pérez garcía"

    def test_normalize_accents(self):
        """Test that accents are preserved."""
        result = normalize_person_name("José María", "González Íñiguez")
        assert result == "josé maría gonzález íñiguez"


class TestValidateRut:
    """Test Chilean RUT validation using módulo 11."""

    def test_valid_rut_with_hyphen(self):
        """Test valid RUT with hyphen."""
        assert validate_rut("12345678-5") is True

    def test_valid_rut_with_dots_and_hyphen(self):
        """Test valid RUT with dots and hyphen."""
        assert validate_rut("12.345.678-5") is True

    def test_valid_rut_with_k(self):
        """Test valid RUT ending in K."""
        assert validate_rut("1000005-K") is True

    def test_valid_rut_with_zero(self):
        """Test valid RUT ending in 0."""
        assert validate_rut("1000013-0") is True

    def test_invalid_rut_wrong_digit(self):
        """Test invalid RUT with wrong verification digit."""
        assert validate_rut("12345678-0") is False

    def test_invalid_rut_too_short(self):
        """Test invalid RUT that's too short."""
        assert validate_rut("1-2") is False

    def test_invalid_rut_not_numeric(self):
        """Test invalid RUT with non-numeric characters."""
        assert validate_rut("ABCDEFGH-5") is False

    def test_invalid_rut_empty(self):
        """Test empty RUT."""
        assert validate_rut("") is False

    def test_valid_rut_lowercase_k(self):
        """Test valid RUT with lowercase k."""
        assert validate_rut("1000005-k") is True


class TestNormalizeRut:
    """Test RUT normalization."""

    def test_normalize_with_dots_and_hyphen(self):
        """Test normalizing RUT with dots and hyphen."""
        result = normalize_rut("12.345.678-5")
        assert result == "123456785"

    def test_normalize_with_hyphen_only(self):
        """Test normalizing RUT with hyphen only."""
        result = normalize_rut("12345678-5")
        assert result == "123456785"

    def test_normalize_with_k(self):
        """Test normalizing RUT ending in K."""
        result = normalize_rut("1.000.005-K")
        assert result == "1000005K"

    def test_normalize_invalid_rut(self):
        """Test that invalid RUT returns None."""
        result = normalize_rut("12345678-0")
        assert result is None

    def test_normalize_empty_string(self):
        """Test empty string returns None."""
        result = normalize_rut("")
        assert result is None

    def test_normalize_none(self):
        """Test None returns None."""
        result = normalize_rut(None)
        assert result is None

    def test_normalize_with_spaces(self):
        """Test RUT with spaces."""
        result = normalize_rut("12 345 678-5")
        assert result == "123456785"

    def test_normalize_lowercase_k(self):
        """Test RUT with lowercase k is normalized to uppercase."""
        result = normalize_rut("1000005-k")
        assert result == "1000005K"


class TestExtractRutFromRaw:
    """Test RUT extraction from raw JSONB data."""

    def test_extract_from_rut_field(self):
        """Test extracting from 'rut' field."""
        raw = {"rut": "12.345.678-5"}
        result = extract_rut_from_raw(raw)
        assert result == "123456785"

    def test_extract_from_rut_sujeto_field(self):
        """Test extracting from 'rut_sujeto' field."""
        raw = {"rut_sujeto": "12345678-5"}
        result = extract_rut_from_raw(raw)
        assert result == "123456785"

    def test_extract_from_run_field(self):
        """Test extracting from 'run' field."""
        raw = {"run": "12.345.678-5"}
        result = extract_rut_from_raw(raw)
        assert result == "123456785"

    def test_extract_invalid_rut(self):
        """Test that invalid RUT returns None."""
        raw = {"rut": "12345678-0"}
        result = extract_rut_from_raw(raw)
        assert result is None

    def test_extract_no_rut_field(self):
        """Test when no RUT field exists."""
        raw = {"nombres": "Juan", "apellidos": "Pérez"}
        result = extract_rut_from_raw(raw)
        assert result is None

    def test_extract_non_string_rut(self):
        """Test when RUT field is not a string."""
        raw = {"rut": 12345678}
        result = extract_rut_from_raw(raw)
        assert result is None

    def test_extract_first_valid_rut(self):
        """Test that first valid RUT is returned when multiple fields exist."""
        raw = {
            "rut": "12.345.678-5",
            "rut_sujeto": "11.111.111-K"
        }
        result = extract_rut_from_raw(raw)
        assert result == "123456785"  # First valid one
