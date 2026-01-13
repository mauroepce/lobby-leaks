"""Tests for SERVEL parser module."""

import pytest
from datetime import date

from ..parser import (
    ParsedDonation,
    parse_donation,
    parse_all_donations,
    normalize_name,
    ParseError,
    MissingRequiredFieldError,
    _find_column,
    _parse_date,
    _parse_amount,
    _parse_year,
    COLUMN_ALIASES,
)


class TestNormalizeName:
    """Tests for name normalization."""

    def test_lowercase(self):
        assert normalize_name("JUAN PÉREZ") == "juan perez"

    def test_remove_accents(self):
        assert normalize_name("José María García") == "jose maria garcia"
        assert normalize_name("Ñoño Muñoz") == "nono munoz"

    def test_remove_punctuation(self):
        assert normalize_name("Juan, Pérez (Jr.)") == "juan perez jr"
        assert normalize_name("María - García") == "maria garcia"

    def test_collapse_whitespace(self):
        assert normalize_name("Juan    Pérez") == "juan perez"
        assert normalize_name("  María  García  ") == "maria garcia"

    def test_empty_input(self):
        assert normalize_name("") == ""
        assert normalize_name("   ") == ""

    def test_special_characters(self):
        assert normalize_name("O'Brien") == "o brien"
        assert normalize_name("Mc'Donald") == "mc donald"


class TestFindColumn:
    """Tests for column alias resolution."""

    def test_find_exact_match(self):
        record = {"NOMBRE_DONANTE": "Juan"}
        assert _find_column(record, "donor_name") == "Juan"

    def test_find_alternative_alias(self):
        record = {"DONANTE": "Juan"}
        assert _find_column(record, "donor_name") == "Juan"

        record = {"APORTANTE": "María"}
        assert _find_column(record, "donor_name") == "María"

    def test_find_lowercase_alias(self):
        record = {"nombre_donante": "Juan"}
        assert _find_column(record, "donor_name") == "Juan"

    def test_returns_none_if_not_found(self):
        record = {"other_field": "value"}
        assert _find_column(record, "donor_name") is None

    def test_required_raises_error(self):
        record = {"other_field": "value"}
        with pytest.raises(MissingRequiredFieldError):
            _find_column(record, "donor_name", required=True)

    def test_strips_whitespace(self):
        record = {"NOMBRE_DONANTE": "  Juan  "}
        assert _find_column(record, "donor_name") == "Juan"

    def test_empty_string_returns_none(self):
        record = {"NOMBRE_DONANTE": ""}
        assert _find_column(record, "donor_name") is None

        record = {"NOMBRE_DONANTE": "   "}
        assert _find_column(record, "donor_name") is None


class TestParseDate:
    """Tests for date parsing."""

    def test_parse_iso_format(self):
        assert _parse_date("2021-03-15") == date(2021, 3, 15)

    def test_parse_chilean_format(self):
        assert _parse_date("15-03-2021") == date(2021, 3, 15)
        assert _parse_date("15/03/2021") == date(2021, 3, 15)

    def test_parse_european_format(self):
        assert _parse_date("15.03.2021") == date(2021, 3, 15)

    def test_parse_iso_with_time(self):
        assert _parse_date("2021-03-15T10:30:00") == date(2021, 3, 15)

    def test_parse_short_year(self):
        assert _parse_date("15-03-21") == date(2021, 3, 15)

    def test_parse_year_only(self):
        assert _parse_date("2021") == date(2021, 1, 1)

    def test_invalid_date_returns_none(self):
        assert _parse_date("invalid") is None
        assert _parse_date("32-13-2021") is None

    def test_empty_returns_none(self):
        assert _parse_date("") is None
        assert _parse_date(None) is None


class TestParseAmount:
    """Tests for amount parsing."""

    def test_parse_simple_number(self):
        assert _parse_amount("1000") == 1000
        assert _parse_amount("1000000") == 1000000

    def test_parse_with_dots_thousands(self):
        # Chilean format: dots as thousand separators
        assert _parse_amount("1.000") == 1000
        assert _parse_amount("1.000.000") == 1000000

    def test_parse_with_commas_thousands(self):
        assert _parse_amount("1,000") == 1000
        assert _parse_amount("1,000,000") == 1000000

    def test_parse_mixed_separators(self):
        # Chilean: 1.234,56
        assert _parse_amount("1.234,56") == 1235  # rounded

    def test_parse_with_currency_symbol(self):
        assert _parse_amount("$1000") == 1000
        assert _parse_amount("$ 1.000") == 1000

    def test_parse_decimal_values(self):
        # Python uses banker's rounding (round half to even)
        assert _parse_amount("1000.50") == 1000  # banker's rounds to even
        assert _parse_amount("1000.49") == 1000  # rounded down
        assert _parse_amount("1000.51") == 1001  # rounded up

    def test_invalid_amount_returns_none(self):
        assert _parse_amount("invalid") is None
        assert _parse_amount("abc123") is None

    def test_empty_returns_none(self):
        assert _parse_amount("") is None
        assert _parse_amount(None) is None


class TestParseYear:
    """Tests for year parsing."""

    def test_parse_simple_year(self):
        assert _parse_year("2021") == 2021
        assert _parse_year("2017") == 2017

    def test_parse_from_string(self):
        assert _parse_year("Elección 2021") == 2021
        assert _parse_year("Periodo 2017-2021") == 2017

    def test_parse_float_string(self):
        assert _parse_year("2021.0") == 2021

    def test_invalid_year_returns_none(self):
        assert _parse_year("invalid") is None
        assert _parse_year("1800") is None  # too old
        assert _parse_year("2200") is None  # too far

    def test_empty_returns_none(self):
        assert _parse_year("") is None
        assert _parse_year(None) is None


class TestParseDonation:
    """Tests for parse_donation function."""

    def test_parse_minimal_record(self):
        """Should parse record with minimum required fields."""
        record = {
            "NOMBRE_DONANTE": "Juan Pérez",
            "NOMBRE_CANDIDATO": "María García",
            "MONTO": "1000000",
            "AÑO_ELECCION": "2021",
        }

        donation = parse_donation(record)

        assert donation.donor_name == "Juan Pérez"
        assert donation.donor_name_normalized == "juan perez"
        assert donation.candidate_name == "María García"
        assert donation.candidate_name_normalized == "maria garcia"
        assert donation.amount_clp == 1000000
        assert donation.campaign_year == 2021

    def test_parse_full_record(self):
        """Should parse record with all fields."""
        record = {
            "NOMBRE_DONANTE": "Juan Pérez",
            "RUT_DONANTE": "12.345.678-5",
            "NOMBRE_CANDIDATO": "María García",
            "RUT_CANDIDATO": "11.111.111-1",
            "MONTO": "1.000.000",
            "FECHA": "15-03-2021",
            "AÑO_ELECCION": "2021",
            "TIPO_ELECCION": "parlamentaria",
            "PARTIDO": "Partido X",
            "TIPO_DONANTE": "persona_natural",
            "REGION": "Metropolitana",
        }

        donation = parse_donation(record)

        assert donation.donor_name == "Juan Pérez"
        assert donation.donor_rut == "12345678-5"
        assert donation.donor_rut_valid is True
        assert donation.candidate_rut == "11111111-1"
        assert donation.candidate_rut_valid is True
        assert donation.donation_date == date(2021, 3, 15)
        assert donation.election_type == "parlamentaria"
        assert donation.candidate_party == "Partido X"
        assert donation.donor_type == "persona_natural"
        assert donation.region == "Metropolitana"

    def test_parse_alternative_column_names(self):
        """Should handle alternative column aliases."""
        record = {
            "DONANTE": "Juan",
            "CANDIDATO": "María",
            "MONTO_APORTE": "1000",
            "ANIO": "2021",
        }

        donation = parse_donation(record)

        assert donation.donor_name == "Juan"
        assert donation.candidate_name == "María"
        assert donation.amount_clp == 1000
        assert donation.campaign_year == 2021

    def test_parse_missing_donor_name_raises(self):
        """Should raise error if donor_name is missing."""
        record = {
            "NOMBRE_CANDIDATO": "María",
            "MONTO": "1000",
            "AÑO_ELECCION": "2021",
        }

        with pytest.raises(MissingRequiredFieldError):
            parse_donation(record)

    def test_parse_missing_candidate_name_raises(self):
        """Should raise error if candidate_name is missing."""
        record = {
            "NOMBRE_DONANTE": "Juan",
            "MONTO": "1000",
            "AÑO_ELECCION": "2021",
        }

        with pytest.raises(MissingRequiredFieldError):
            parse_donation(record)

    def test_parse_missing_amount_raises(self):
        """Should raise error if amount is missing."""
        record = {
            "NOMBRE_DONANTE": "Juan",
            "NOMBRE_CANDIDATO": "María",
            "AÑO_ELECCION": "2021",
        }

        with pytest.raises(MissingRequiredFieldError):
            parse_donation(record)

    def test_parse_invalid_amount_raises(self):
        """Should raise error if amount is invalid."""
        record = {
            "NOMBRE_DONANTE": "Juan",
            "NOMBRE_CANDIDATO": "María",
            "MONTO": "invalid",
            "AÑO_ELECCION": "2021",
        }

        with pytest.raises(ParseError):
            parse_donation(record)

    def test_parse_missing_year_raises(self):
        """Should raise error if campaign_year is missing."""
        record = {
            "NOMBRE_DONANTE": "Juan",
            "NOMBRE_CANDIDATO": "María",
            "MONTO": "1000",
        }

        with pytest.raises(MissingRequiredFieldError):
            parse_donation(record)

    def test_parse_invalid_year_raises(self):
        """Should raise error if year is invalid."""
        record = {
            "NOMBRE_DONANTE": "Juan",
            "NOMBRE_CANDIDATO": "María",
            "MONTO": "1000",
            "AÑO_ELECCION": "invalid",
        }

        with pytest.raises(ParseError):
            parse_donation(record)

    def test_parse_invalid_rut_stores_none(self):
        """Should store None for invalid RUT but continue parsing."""
        record = {
            "NOMBRE_DONANTE": "Juan",
            "RUT_DONANTE": "invalid-rut",
            "NOMBRE_CANDIDATO": "María",
            "MONTO": "1000",
            "AÑO_ELECCION": "2021",
        }

        donation = parse_donation(record)

        assert donation.donor_rut is None
        assert donation.donor_rut_valid is False

    def test_parse_generates_checksum(self):
        """Should generate SHA256 checksum."""
        record = {
            "NOMBRE_DONANTE": "Juan",
            "NOMBRE_CANDIDATO": "María",
            "MONTO": "1000",
            "AÑO_ELECCION": "2021",
        }

        donation = parse_donation(record)

        assert donation.checksum
        assert len(donation.checksum) == 64  # SHA256 hex

    def test_parse_same_data_same_checksum(self):
        """Same data should produce same checksum."""
        record1 = {
            "NOMBRE_DONANTE": "Juan",
            "NOMBRE_CANDIDATO": "María",
            "MONTO": "1000",
            "AÑO_ELECCION": "2021",
        }
        record2 = {
            "DONANTE": "Juan",  # Different column name
            "CANDIDATO": "María",
            "MONTO_APORTE": "1000",
            "ANIO": "2021",
        }

        donation1 = parse_donation(record1)
        donation2 = parse_donation(record2)

        assert donation1.checksum == donation2.checksum

    def test_parse_different_data_different_checksum(self):
        """Different data should produce different checksum."""
        record1 = {
            "NOMBRE_DONANTE": "Juan",
            "NOMBRE_CANDIDATO": "María",
            "MONTO": "1000",
            "AÑO_ELECCION": "2021",
        }
        record2 = {
            "NOMBRE_DONANTE": "Juan",
            "NOMBRE_CANDIDATO": "María",
            "MONTO": "2000",  # Different amount
            "AÑO_ELECCION": "2021",
        }

        donation1 = parse_donation(record1)
        donation2 = parse_donation(record2)

        assert donation1.checksum != donation2.checksum


class TestParseAllDonations:
    """Tests for parse_all_donations function."""

    def test_parse_multiple_records(self):
        """Should parse multiple valid records."""
        records = [
            {
                "NOMBRE_DONANTE": "Juan",
                "NOMBRE_CANDIDATO": "María",
                "MONTO": "1000",
                "AÑO_ELECCION": "2021",
            },
            {
                "NOMBRE_DONANTE": "Pedro",
                "NOMBRE_CANDIDATO": "Ana",
                "MONTO": "2000",
                "AÑO_ELECCION": "2021",
            },
        ]

        donations, errors = parse_all_donations(records)

        assert len(donations) == 2
        assert len(errors) == 0
        assert donations[0].donor_name == "Juan"
        assert donations[1].donor_name == "Pedro"

    def test_parse_skips_errors_by_default(self):
        """Should skip records with errors and continue."""
        records = [
            {
                "NOMBRE_DONANTE": "Juan",
                "NOMBRE_CANDIDATO": "María",
                "MONTO": "1000",
                "AÑO_ELECCION": "2021",
            },
            {
                # Missing required fields
                "OTHER_FIELD": "value",
            },
            {
                "NOMBRE_DONANTE": "Pedro",
                "NOMBRE_CANDIDATO": "Ana",
                "MONTO": "2000",
                "AÑO_ELECCION": "2021",
            },
        ]

        donations, errors = parse_all_donations(records)

        assert len(donations) == 2
        assert len(errors) == 1
        assert errors[0]["row_index"] == 1

    def test_parse_raises_on_error_when_requested(self):
        """Should raise error when skip_errors=False."""
        records = [
            {
                "NOMBRE_DONANTE": "Juan",
                "NOMBRE_CANDIDATO": "María",
                "MONTO": "1000",
                "AÑO_ELECCION": "2021",
            },
            {
                # Missing required fields
                "OTHER_FIELD": "value",
            },
        ]

        with pytest.raises((ParseError, MissingRequiredFieldError)):
            parse_all_donations(records, skip_errors=False)

    def test_parse_empty_list(self):
        """Should handle empty input."""
        donations, errors = parse_all_donations([])

        assert donations == []
        assert errors == []

    def test_error_info_contains_record(self):
        """Error info should include original record."""
        records = [
            {
                "BAD_COLUMN": "value",
            },
        ]

        donations, errors = parse_all_donations(records)

        assert len(errors) == 1
        assert errors[0]["record"]["BAD_COLUMN"] == "value"
        assert "error" in errors[0]


class TestParsedDonationDataclass:
    """Tests for ParsedDonation dataclass."""

    def test_default_values(self):
        """Should have correct default values."""
        donation = ParsedDonation(
            donor_name="Juan",
            donor_name_normalized="juan",
            candidate_name="María",
            candidate_name_normalized="maria",
            amount_clp=1000,
            campaign_year=2021,
        )

        assert donation.donor_rut is None
        assert donation.donor_rut_valid is False
        assert donation.candidate_rut is None
        assert donation.candidate_rut_valid is False
        assert donation.donation_date is None
        assert donation.election_type is None
        assert donation.candidate_party is None
        assert donation.donor_type is None
        assert donation.region is None
        assert donation.checksum == ""

    def test_all_fields_settable(self):
        """Should allow setting all fields."""
        donation = ParsedDonation(
            donor_name="Juan Pérez",
            donor_name_normalized="juan perez",
            candidate_name="María García",
            candidate_name_normalized="maria garcia",
            amount_clp=1000000,
            campaign_year=2021,
            donor_rut="12345678-5",
            donor_rut_valid=True,
            candidate_rut="11111111-1",
            candidate_rut_valid=True,
            donation_date=date(2021, 3, 15),
            election_type="presidencial",
            candidate_party="Partido X",
            donor_type="persona_juridica",
            region="Metropolitana",
            checksum="abc123",
        )

        assert donation.donor_name == "Juan Pérez"
        assert donation.donor_rut == "12345678-5"
        assert donation.donor_rut_valid is True
        assert donation.donation_date == date(2021, 3, 15)
        assert donation.election_type == "presidencial"


class TestColumnAliases:
    """Tests for column alias configuration."""

    def test_all_required_fields_have_aliases(self):
        """All required fields should have multiple aliases."""
        required_fields = ["donor_name", "candidate_name", "amount_clp", "campaign_year"]

        for field in required_fields:
            assert field in COLUMN_ALIASES
            assert len(COLUMN_ALIASES[field]) >= 2

    def test_aliases_include_lowercase_variants(self):
        """Aliases should include lowercase variants."""
        for field, aliases in COLUMN_ALIASES.items():
            lowercase_aliases = [a for a in aliases if a.islower()]
            assert len(lowercase_aliases) >= 1, f"{field} should have lowercase aliases"
