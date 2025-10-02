"""
Tests for name normalization utilities.

Tests Chilean name normalization including honorific removal,
unicode normalization, and whitespace handling using parametrized tests.
"""

import pytest
from services._template.helpers.name import normalize_name


class TestNormalizeName:
    """Tests for name normalization."""

    @pytest.mark.parametrize(
        "input_name,expected",
        [
            # Basic whitespace handling
            ("  JUAN   PÉREZ  ", "Juan Pérez"),
            ("Juan Pérez", "Juan Pérez"),
            ("   María   ", "María"),

            # Multiple spaces between words
            ("José  López  Díaz", "José López Díaz"),
            ("Pedro    Pablo    González", "Pedro Pablo González"),

            # Case conversion
            ("JUAN PÉREZ", "Juan Pérez"),
            ("juan pérez", "Juan Pérez"),
            ("JuAn PéReZ", "Juan Pérez"),
            ("MARÍA JOSÉ GONZÁLEZ", "María José González"),

            # Honorifics - general
            ("Sr. Juan Pérez", "Juan Pérez"),
            ("sr. juan pérez", "Juan Pérez"),
            ("SR. JUAN PÉREZ", "Juan Pérez"),
            ("Sra. María González", "María González"),
            ("Srta. Ana Silva", "Ana Silva"),
            ("Don Pedro López", "Pedro López"),
            ("Doña María Díaz", "María Díaz"),

            # Honorifics - professional
            ("Dr. Juan Pérez", "Juan Pérez"),
            ("Dra. María González", "María González"),
            ("Dr Juan Pérez", "Juan Pérez"),
            ("Prof. Carlos Díaz", "Carlos Díaz"),
            ("Profa. Ana López", "Ana López"),
            ("Ing. Pedro Sánchez", "Pedro Sánchez"),
            ("Inga. María Rojas", "María Rojas"),
            ("Abog. Luis Torres", "Luis Torres"),
            ("Aboga. Carmen Vera", "Carmen Vera"),

            # Honorifics - political
            ("Dip. Juan Pérez", "Juan Pérez"),
            ("Diputado Juan Pérez", "Juan Pérez"),
            ("Diputada María González", "María González"),
            ("Sen. Pedro López", "Pedro López"),
            ("Senador Carlos Díaz", "Carlos Díaz"),
            ("Senadora Ana Silva", "Ana Silva"),
            ("Ministro Juan Pérez", "Juan Pérez"),
            ("Ministra María González", "María González"),
            ("Alcalde Pedro López", "Pedro López"),
            ("Alcaldesa Ana Silva", "Ana Silva"),
            ("Concejal Luis Torres", "Luis Torres"),
            ("Concejala Carmen Vera", "Carmen Vera"),

            # Unicode normalization (accented characters)
            ("José López", "José López"),
            ("María Pérez", "María Pérez"),
            ("Andrés Sánchez", "Andrés Sánchez"),
            ("Mónica Núñez", "Mónica Núñez"),

            # Combined: honorifics + spaces + case
            ("  SR.   JUAN   PÉREZ  ", "Juan Pérez"),
            ("dip.  maría   gonzález", "María González"),
            ("DR.    PEDRO    SÁNCHEZ", "Pedro Sánchez"),

            # Composite names
            ("María José Silva", "María José Silva"),
            ("Juan Pablo González", "Juan Pablo González"),
            ("Ana María López Díaz", "Ana María López Díaz"),

            # Edge cases
            ("", ""),  # Empty string
            ("   ", ""),  # Only spaces
            ("Sr.", "Sr."),  # Only honorific (no name following)
            ("A", "A"),  # Single letter
            ("Ñ", "Ñ"),  # Single special character

            # Names without honorifics (should remain unchanged except formatting)
            ("Juan Pérez López", "Juan Pérez López"),
            ("María González Silva", "María González Silva"),

            # Multiple honorifics (only first should be removed)
            ("Sr. Dr. Juan Pérez", "Dr. Juan Pérez"),
        ],
        ids=[
            "basic_whitespace_upper",
            "basic_no_change",
            "basic_whitespace_single",
            "multiple_spaces_between",
            "multiple_spaces_many",
            "case_upper",
            "case_lower",
            "case_mixed",
            "case_composite_upper",
            "honorific_sr_title",
            "honorific_sr_lower",
            "honorific_sr_upper",
            "honorific_sra",
            "honorific_srta",
            "honorific_don",
            "honorific_dona",
            "honorific_dr_title",
            "honorific_dra",
            "honorific_dr_no_dot",
            "honorific_prof",
            "honorific_profa",
            "honorific_ing",
            "honorific_inga",
            "honorific_abog",
            "honorific_aboga",
            "honorific_dip_title",
            "honorific_diputado",
            "honorific_diputada",
            "honorific_sen",
            "honorific_senador",
            "honorific_senadora",
            "honorific_ministro",
            "honorific_ministra",
            "honorific_alcalde",
            "honorific_alcaldesa",
            "honorific_concejal",
            "honorific_concejala",
            "unicode_jose",
            "unicode_maria",
            "unicode_andres",
            "unicode_monica",
            "combined_sr_spaces_upper",
            "combined_dip_spaces_lower",
            "combined_dr_spaces_upper",
            "composite_maria_jose",
            "composite_juan_pablo",
            "composite_four_names",
            "edge_empty",
            "edge_only_spaces",
            "edge_only_honorific",
            "edge_single_letter",
            "edge_single_special",
            "no_honorific_three_names",
            "no_honorific_four_names",
            "multiple_honorifics",
        ],
    )
    def test_normalize_name(self, input_name, expected):
        """Test name normalization with various inputs."""
        assert normalize_name(input_name) == expected

    def test_normalize_name_none_input(self):
        """Test that None input returns empty string."""
        assert normalize_name(None) == ""

    def test_normalize_name_non_string_input(self):
        """Test that non-string input returns empty string."""
        assert normalize_name(123) == ""
        assert normalize_name([]) == ""
        assert normalize_name({}) == ""

    def test_unicode_consistency(self):
        """Test that unicode normalization produces consistent results."""
        # These should all produce the same normalized output
        # (different unicode representations of "José")
        name1 = "José"  # Composed form (single character é)
        name2 = "José"  # Decomposed form (e + combining acute accent)

        result1 = normalize_name(name1)
        result2 = normalize_name(name2)

        # Both should normalize to the same canonical form
        assert result1 == result2
        assert result1 == "José"

    def test_preserves_chilean_characters(self):
        """Test that Chilean-specific characters are preserved."""
        assert normalize_name("Ñuñoa") == "Ñuñoa"
        assert normalize_name("Piñera") == "Piñera"
        assert normalize_name("Peñalolén") == "Peñalolén"
