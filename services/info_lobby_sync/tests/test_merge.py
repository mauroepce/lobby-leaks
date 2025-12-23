"""Tests for merge module."""

import pytest
from ..merge import (
    normalize_for_matching,
    extract_persons_from_record,
    extract_organisations_from_record,
    merge_records_in_memory,
    MergeResult,
    _merge_person_fields,
    _merge_org_fields,
)
from ..parser import ParsedPasivo, ParsedAudiencia


class TestNormalizeForMatching:
    """Tests for name normalization."""

    @pytest.mark.parametrize("input_name,expected", [
        # Basic cases
        ("Juan Pérez", "juan perez"),
        ("MARÍA GARCÍA", "maria garcia"),
        ("josé lópez", "jose lopez"),
        # Accents
        ("José María López Ñuñez", "jose maria lopez nunez"),
        ("Ángel Óscar Ávila", "angel oscar avila"),
        ("Güiraldes Ümlauts", "guiraldes umlauts"),
        # Punctuation
        ("García-Huidobro, Juan", "garcia huidobro juan"),
        ("Corporación (CORFO)", "corporacion corfo"),
        ("O'Brien Smith", "o brien smith"),
        # Whitespace
        ("  Juan   Pérez  ", "juan perez"),
        ("Ana\tMaría\nLópez", "ana maria lopez"),
        # Empty/None
        ("", ""),
        (None, ""),
    ])
    def test_normalize_for_matching(self, input_name, expected):
        assert normalize_for_matching(input_name) == expected


class TestExtractPersons:
    """Tests for person extraction from records."""

    def test_extract_pasivo_from_dict(self):
        record = {
            "pasivo": {
                "nombre": "Juan Pérez",
                "cargo": "Ministro",
                "institucion": "Interior",
            },
            "activos": [],
        }
        persons = extract_persons_from_record(record)

        assert len(persons) == 1
        assert persons[0]["name"] == "Juan Pérez"
        assert persons[0]["normalized_name"] == "juan perez"
        assert persons[0]["cargo"] == "Ministro"
        assert persons[0]["role"] == "pasivo"

    def test_extract_activos_from_dict(self):
        record = {
            "pasivo": None,
            "activos": ["Ana García", "Pedro López"],
        }
        persons = extract_persons_from_record(record)

        assert len(persons) == 2
        assert persons[0]["name"] == "Ana García"
        assert persons[0]["normalized_name"] == "ana garcia"
        assert persons[0]["role"] == "activo"
        assert persons[1]["name"] == "Pedro López"
        assert persons[1]["role"] == "activo"

    def test_extract_pasivo_and_activos(self):
        record = {
            "pasivo": {"nombre": "Ministro Juan", "cargo": "Ministro", "institucion": "X"},
            "activos": ["Lobista A", "Lobista B"],
        }
        persons = extract_persons_from_record(record)

        assert len(persons) == 3
        assert persons[0]["role"] == "pasivo"
        assert persons[1]["role"] == "activo"
        assert persons[2]["role"] == "activo"

    def test_extract_empty_record(self):
        record = {"pasivo": None, "activos": []}
        persons = extract_persons_from_record(record)
        assert len(persons) == 0

    def test_extract_from_parsed_dataclass(self):
        pasivo = ParsedPasivo(
            nombre="Carolina Tohá",
            cargo="Ministra",
            institucion="Interior"
        )
        record = {
            "pasivo": pasivo,
            "activos": ["Lobista X"],
        }
        persons = extract_persons_from_record(record)

        assert len(persons) == 2
        assert persons[0]["name"] == "Carolina Tohá"
        assert persons[0]["cargo"] == "Ministra"


class TestExtractOrganisations:
    """Tests for organisation extraction from records."""

    def test_extract_representados(self):
        record = {
            "representados": "Corporación Chilena de la Madera",
        }
        orgs = extract_organisations_from_record(record)

        assert len(orgs) == 1
        assert orgs[0]["name"] == "Corporación Chilena de la Madera"
        assert orgs[0]["normalized_name"] == "corporacion chilena de la madera"
        assert orgs[0]["tipo"] == "representado"

    def test_extract_donantes(self):
        record = {
            "donantes": "Editorial PUCV",
        }
        orgs = extract_organisations_from_record(record)

        assert len(orgs) == 1
        assert orgs[0]["name"] == "Editorial PUCV"
        assert orgs[0]["tipo"] == "donante"

    def test_extract_financistas(self):
        record = {
            "financistas": "Gobierno de Chile",
        }
        orgs = extract_organisations_from_record(record)

        assert len(orgs) == 1
        assert orgs[0]["name"] == "Gobierno de Chile"
        assert orgs[0]["tipo"] == "financista"

    def test_skip_financistas_si(self):
        """S/I means 'sin información' - should be skipped."""
        record = {
            "financistas": "S/I",
        }
        orgs = extract_organisations_from_record(record)
        assert len(orgs) == 0

    def test_skip_financistas_si_lowercase(self):
        record = {
            "financistas": "s/i",
        }
        orgs = extract_organisations_from_record(record)
        assert len(orgs) == 0

    def test_extract_multiple_orgs(self):
        record = {
            "representados": "Empresa A",
            "donantes": "Fundación B",
            "financistas": "Gobierno C",
        }
        orgs = extract_organisations_from_record(record)

        assert len(orgs) == 3
        tipos = {o["tipo"] for o in orgs}
        assert tipos == {"representado", "donante", "financista"}


class TestMergeFields:
    """Tests for field merging."""

    def test_merge_person_adds_cargo(self):
        existing = {"name": "Juan", "cargo": None}
        new = {"name": "Juan", "cargo": "Ministro"}
        _merge_person_fields(existing, new)
        assert existing["cargo"] == "Ministro"

    def test_merge_person_keeps_existing_cargo(self):
        existing = {"name": "Juan", "cargo": "Director"}
        new = {"name": "Juan", "cargo": "Ministro"}
        _merge_person_fields(existing, new)
        assert existing["cargo"] == "Director"

    def test_merge_org_adds_tipo(self):
        existing = {"name": "Corp", "tipo": None}
        new = {"name": "Corp", "tipo": "representado"}
        _merge_org_fields(existing, new)
        assert existing["tipo"] == "representado"


class TestMergeRecordsInMemory:
    """Tests for in-memory merge logic."""

    def test_merge_single_record(self):
        records = [{
            "pasivo": {"nombre": "Juan Pérez", "cargo": "Ministro", "institucion": "X"},
            "activos": ["Ana García"],
            "representados": "Empresa ABC",
        }]

        result = merge_records_in_memory(records)

        assert isinstance(result, MergeResult)
        assert len(result.persons) == 2
        assert len(result.organisations) == 1
        assert result.persons_new == 2
        assert result.orgs_new == 1
        assert result.duplicates_found == 0

    def test_merge_deduplicates_same_person(self):
        """Same person appearing in multiple records should be merged."""
        records = [
            {
                "pasivo": {"nombre": "Juan Pérez", "cargo": "Ministro", "institucion": "X"},
                "activos": [],
            },
            {
                "pasivo": {"nombre": "Juan Pérez", "cargo": None, "institucion": "Y"},
                "activos": [],
            },
        ]

        result = merge_records_in_memory(records)

        assert len(result.persons) == 1
        assert result.persons[0]["cargo"] == "Ministro"  # Preserved from first
        assert result.duplicates_found == 1

    def test_merge_deduplicates_with_normalization(self):
        """Names that normalize to same value should be deduplicated."""
        records = [
            {
                "pasivo": {"nombre": "JUAN PÉREZ", "cargo": None, "institucion": "X"},
                "activos": [],
            },
            {
                "pasivo": {"nombre": "Juan Perez", "cargo": "Director", "institucion": "Y"},
                "activos": [],
            },
        ]

        result = merge_records_in_memory(records)

        assert len(result.persons) == 1
        # cargo should be added from second record
        assert result.persons[0]["cargo"] == "Director"
        assert result.duplicates_found == 1

    def test_merge_finds_existing_persons(self):
        """Existing persons in DB should be marked with existing_id."""
        existing_persons = {
            "juan perez": "existing-uuid-123",
        }

        records = [{
            "pasivo": {"nombre": "Juan Pérez", "cargo": "Ministro", "institucion": "X"},
            "activos": ["Ana García"],
        }]

        result = merge_records_in_memory(
            records,
            existing_persons=existing_persons
        )

        juan = next(p for p in result.persons if "juan" in p["normalized_name"])
        ana = next(p for p in result.persons if "ana" in p["normalized_name"])

        assert juan["existing_id"] == "existing-uuid-123"
        assert ana["existing_id"] is None
        assert result.persons_existing == 1
        assert result.persons_new == 1

    def test_merge_finds_existing_orgs(self):
        """Existing orgs in DB should be marked with existing_id."""
        existing_orgs = {
            "empresa abc": "existing-org-456",
        }

        records = [{
            "representados": "Empresa ABC",
            "donantes": "Nueva Fundación",
        }]

        result = merge_records_in_memory(
            records,
            existing_orgs=existing_orgs
        )

        empresa = next(o for o in result.organisations if "empresa" in o["normalized_name"])
        fundacion = next(o for o in result.organisations if "fundacion" in o["normalized_name"])

        assert empresa["existing_id"] == "existing-org-456"
        assert fundacion["existing_id"] is None
        assert result.orgs_existing == 1
        assert result.orgs_new == 1

    def test_merge_multiple_records_complex(self):
        """Complex scenario with multiple records and deduplication."""
        existing_persons = {
            "ministro conocido": "person-1",
        }
        existing_orgs = {
            "empresa vieja": "org-1",
        }

        records = [
            {
                "pasivo": {"nombre": "Ministro Conocido", "cargo": "Ministro", "institucion": "X"},
                "activos": ["Lobista A", "Lobista B"],
                "representados": "Empresa Vieja",
            },
            {
                "pasivo": {"nombre": "Nuevo Director", "cargo": "Director", "institucion": "Y"},
                "activos": ["Lobista A"],  # Duplicate lobista
                "representados": "Empresa Nueva",
            },
        ]

        result = merge_records_in_memory(
            records,
            existing_persons=existing_persons,
            existing_orgs=existing_orgs
        )

        # Persons: Ministro Conocido (existing), Lobista A, Lobista B, Nuevo Director
        assert len(result.persons) == 4
        assert result.persons_existing == 1
        assert result.persons_new == 3
        assert result.duplicates_found == 1  # Lobista A duplicated

        # Orgs: Empresa Vieja (existing), Empresa Nueva
        assert len(result.organisations) == 2
        assert result.orgs_existing == 1
        assert result.orgs_new == 1

    def test_merge_empty_records(self):
        result = merge_records_in_memory([])

        assert len(result.persons) == 0
        assert len(result.organisations) == 0
        assert result.duplicates_found == 0

    def test_merge_sets_tenant_code(self):
        records = [{
            "pasivo": {"nombre": "Juan", "cargo": None, "institucion": "X"},
            "representados": "Empresa",
        }]

        result = merge_records_in_memory(records, tenant_code="UY")

        assert result.persons[0]["tenant_code"] == "UY"
        assert result.organisations[0]["tenant_code"] == "UY"


class TestMergeResultMetrics:
    """Tests for MergeResult metrics."""

    def test_merged_count(self):
        records = [
            {
                "pasivo": {"nombre": "A", "cargo": None, "institucion": "X"},
                "activos": ["B", "C"],
                "representados": "Org1",
                "donantes": "Org2",
            },
        ]

        result = merge_records_in_memory(records)

        # 3 persons + 2 orgs = 5
        assert result.merged_count == 5
        assert len(result.persons) == 3
        assert len(result.organisations) == 2
