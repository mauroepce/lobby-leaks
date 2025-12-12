"""Tests for parser module."""

import pytest
from datetime import date, datetime

from ..parser import (
    parse_date,
    parse_datetime,
    parse_int,
    normalize_rut,
    parse_pasivo,
    parse_activos,
    compute_checksum,
    parse_audiencia,
    parse_viaje,
    parse_donativo,
    ParsedPasivo,
)


class TestParseDatetime:
    """Tests for date/datetime parsing."""

    def test_parse_datetime_with_milliseconds(self):
        result = parse_datetime("2025-04-03T11:16:16.82")
        assert result == datetime(2025, 4, 3, 11, 16, 16, 820000)

    def test_parse_datetime_without_milliseconds(self):
        result = parse_datetime("2025-04-03T11:16:16")
        assert result == datetime(2025, 4, 3, 11, 16, 16)

    def test_parse_datetime_date_only(self):
        result = parse_datetime("2025-04-03")
        assert result == datetime(2025, 4, 3, 0, 0, 0)

    def test_parse_datetime_none(self):
        assert parse_datetime(None) is None

    def test_parse_datetime_invalid(self):
        assert parse_datetime("invalid") is None

    def test_parse_date_full_datetime(self):
        result = parse_date("2025-04-03T11:16:16.82")
        assert result == date(2025, 4, 3)

    def test_parse_date_date_only(self):
        result = parse_date("2025-04-03")
        assert result == date(2025, 4, 3)


class TestParseInt:
    """Tests for integer parsing."""

    def test_parse_int_valid(self):
        assert parse_int("12345") == 12345

    def test_parse_int_zero(self):
        assert parse_int("0") == 0

    def test_parse_int_none(self):
        assert parse_int(None) is None

    def test_parse_int_invalid(self):
        assert parse_int("not a number") is None


class TestNormalizeRut:
    """Tests for RUT normalization."""

    def test_normalize_rut_with_dots(self):
        assert normalize_rut("12.345.678-9") == "12345678-9"

    def test_normalize_rut_without_dots(self):
        assert normalize_rut("12345678-9") == "12345678-9"

    def test_normalize_rut_without_dash(self):
        assert normalize_rut("123456789") == "12345678-9"

    def test_normalize_rut_lowercase_k(self):
        assert normalize_rut("12.345.678-k") == "12345678-K"

    def test_normalize_rut_invalid(self):
        assert normalize_rut("invalid") is None


class TestParsePasivo:
    """Tests for datosPasivos parsing."""

    def test_parse_pasivo_full(self):
        result = parse_pasivo("Carolina Tohá Morales: Ministro: SUBSECRETARÍA DEL INTERIOR")
        assert result == ParsedPasivo(
            nombre="Carolina Tohá Morales",
            cargo="Ministro",
            institucion="SUBSECRETARÍA DEL INTERIOR"
        )

    def test_parse_pasivo_fallback(self):
        result = parse_pasivo("Solo un nombre")
        assert result == ParsedPasivo(
            nombre="Solo un nombre",
            cargo="",
            institucion=""
        )

    def test_parse_pasivo_none(self):
        assert parse_pasivo(None) is None

    def test_parse_pasivo_empty(self):
        assert parse_pasivo("") is None


class TestParseActivos:
    """Tests for datosActivos parsing."""

    def test_parse_activos_multiple(self):
        result = parse_activos("Antonio Minte - Fernando Meneses - María Landea")
        assert result == ["Antonio Minte", "Fernando Meneses", "María Landea"]

    def test_parse_activos_single(self):
        result = parse_activos("Juan Pérez")
        assert result == ["Juan Pérez"]

    def test_parse_activos_none(self):
        assert parse_activos(None) == []

    def test_parse_activos_empty(self):
        assert parse_activos("") == []


class TestComputeChecksum:
    """Tests for checksum computation."""

    def test_checksum_deterministic(self):
        record = {"a": "1", "b": "2"}
        checksum1 = compute_checksum(record)
        checksum2 = compute_checksum(record)
        assert checksum1 == checksum2

    def test_checksum_different_for_different_records(self):
        record1 = {"a": "1"}
        record2 = {"a": "2"}
        assert compute_checksum(record1) != compute_checksum(record2)

    def test_checksum_order_independent(self):
        record1 = {"a": "1", "b": "2"}
        record2 = {"b": "2", "a": "1"}
        assert compute_checksum(record1) == compute_checksum(record2)


class TestParseAudiencia:
    """Tests for audiencia parsing."""

    def test_parse_audiencia_full(self):
        record = {
            "uri": "http://datos.infolobby.cl/infolobby/registroaudiencia/ab0017839281",
            "codigoURI": "ab0017839281",
            "identificadorTemporal": "1249287",
            "fechaEvento": "2025-02-19T16:30:00",
            "fechaActualizacion": "2025-04-03T11:16:16.82",
            "datosPasivos": "Carolina Tohá: Ministro: Interior",
            "datosActivos": "Juan Pérez - María García",
            "datosRepresentados": "Corporación XYZ",
            "datosMaterias": "Legislación",
            "descripcion": "Gabinete del ministro",
            "observaciones": "Tema importante",
            "esDeTipo": "Presencial",
        }

        result = parse_audiencia(record)

        assert result.uri == record["uri"]
        assert result.codigo_uri == "ab0017839281"
        assert result.identificador_temporal == 1249287
        assert result.fecha_evento == datetime(2025, 2, 19, 16, 30, 0)
        assert result.pasivo.nombre == "Carolina Tohá"
        assert result.activos == ["Juan Pérez", "María García"]
        assert result.representados == "Corporación XYZ"
        assert result.checksum is not None

    def test_parse_audiencia_minimal(self):
        record = {
            "uri": "http://example.com/1",
            "codigoURI": "abc123",
        }

        result = parse_audiencia(record)

        assert result.uri == "http://example.com/1"
        assert result.codigo_uri == "abc123"
        assert result.identificador_temporal is None
        assert result.fecha_evento is None
        assert result.pasivo is None
        assert result.activos == []


class TestParseViaje:
    """Tests for viaje parsing."""

    def test_parse_viaje_full(self):
        record = {
            "uri": "http://datos.infolobby.cl/infolobby/viaje/ab0017004012",
            "codigoURI": "ab0017004012",
            "identificadorTemporal": "889253",
            "fechaEvento": "2025-02-14",
            "fechaActualizacion": "2025-04-03T11:08:35.45",
            "descripcion": "Región del Maule",
            "datosRazones": "Visita oficial",
            "datosObjetos": "Inauguración",
            "datosFinancistas": "Gobierno",
            "costo": "150000",
        }

        result = parse_viaje(record)

        assert result.codigo_uri == "ab0017004012"
        assert result.fecha_evento == date(2025, 2, 14)
        assert result.costo == 150000
        assert result.financistas == "Gobierno"


class TestParseDonativo:
    """Tests for donativo parsing."""

    def test_parse_donativo_full(self):
        record = {
            "uri": "http://datos.infolobby.cl/infolobby/donativo/ab001627833",
            "codigoURI": "ab001627833",
            "identificadorTemporal": "107101",
            "fechaEvento": "2025-06-19",
            "fechaActualizacion": "2025-07-07T16:47:41.81",
            "descripcion": "Libro de historia",
            "ocasion": "Difusión cultural",
            "datosDonantes": "Editorial ABC",
        }

        result = parse_donativo(record)

        assert result.codigo_uri == "ab001627833"
        assert result.fecha_evento == date(2025, 6, 19)
        assert result.donantes == "Editorial ABC"
        assert result.ocasion == "Difusión cultural"
