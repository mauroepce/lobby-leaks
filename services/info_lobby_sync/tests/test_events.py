"""Tests for event extraction module."""

from datetime import date, datetime

import pytest

from ..parser import ParsedAudiencia, ParsedDonativo, ParsedPasivo, ParsedViaje
from ..events import (
    AudienceEvent,
    BaseEvent,
    DonationEvent,
    TravelEvent,
    extract_audience_event,
    extract_donation_event,
    extract_events,
    extract_travel_event,
    _normalize_ref,
    _normalize_ref_list,
    _parse_donantes,
    _parse_financistas,
    _parse_materias,
    _parse_representados,
)


class TestBaseEvent:
    """Tests for BaseEvent dataclass."""

    def test_base_event_defaults(self):
        """BaseEvent should have correct defaults."""
        event = AudienceEvent(
            external_id="test-123",
            date_start=date(2025, 1, 15),
        )

        assert event.external_id == "test-123"
        assert event.event_type == "audience"
        assert event.date_start == date(2025, 1, 15)
        assert event.date_end is None
        assert event.source == "infolobby_sparql"
        assert event.pasivo_ref is None
        assert event.activos_refs == []
        assert event.representados_refs == []

    def test_event_type_is_literal(self):
        """Each event type should have correct event_type."""
        audience = AudienceEvent(external_id="a1", date_start=None)
        travel = TravelEvent(external_id="t1", date_start=None)
        donation = DonationEvent(external_id="d1", date_start=None)

        assert audience.event_type == "audience"
        assert travel.event_type == "travel"
        assert donation.event_type == "donation"


class TestAudienceEvent:
    """Tests for AudienceEvent dataclass."""

    def test_audience_event_fields(self):
        """AudienceEvent should have all specific fields."""
        event = AudienceEvent(
            external_id="aud-123",
            date_start=date(2025, 1, 15),
            pasivo_ref="juan perez",
            activos_refs=["maria garcia"],
            representados_refs=["empresa xyz"],
            lugar="Oficina Central",
            forma="presencial",
            materias=["Medio Ambiente", "Minería"],
            descripcion="Reunión sobre proyecto minero",
            observaciones="Sin observaciones",
        )

        assert event.lugar == "Oficina Central"
        assert event.forma == "presencial"
        assert event.materias == ["Medio Ambiente", "Minería"]
        assert event.descripcion == "Reunión sobre proyecto minero"
        assert event.observaciones == "Sin observaciones"


class TestTravelEvent:
    """Tests for TravelEvent dataclass."""

    def test_travel_event_fields(self):
        """TravelEvent should have all specific fields."""
        event = TravelEvent(
            external_id="via-123",
            date_start=date(2025, 2, 1),
            date_end=date(2025, 2, 5),
            destino="Santiago, Chile",
            motivo="Conferencia internacional",
            costo_total=1500000,
            financiadores_refs=["empresa abc"],
        )

        assert event.destino == "Santiago, Chile"
        assert event.motivo == "Conferencia internacional"
        assert event.costo_total == 1500000
        assert event.financiadores_refs == ["empresa abc"]


class TestDonationEvent:
    """Tests for DonationEvent dataclass."""

    def test_donation_event_fields(self):
        """DonationEvent should have all specific fields."""
        event = DonationEvent(
            external_id="don-123",
            date_start=date(2025, 3, 10),
            tipo_donativo="Regalo",
            descripcion="Libro de arte",
            ocasion="Cumpleaños",
            donantes_refs=["fundacion cultural"],
        )

        assert event.tipo_donativo == "Regalo"
        assert event.descripcion == "Libro de arte"
        assert event.ocasion == "Cumpleaños"
        assert event.donantes_refs == ["fundacion cultural"]


class TestNormalizeRef:
    """Tests for _normalize_ref function."""

    def test_normalize_ref_basic(self):
        assert _normalize_ref("Juan Pérez") == "juan perez"

    def test_normalize_ref_with_accents(self):
        assert _normalize_ref("José María García") == "jose maria garcia"

    def test_normalize_ref_empty_string(self):
        assert _normalize_ref("") is None

    def test_normalize_ref_none(self):
        assert _normalize_ref(None) is None

    def test_normalize_ref_whitespace_only(self):
        assert _normalize_ref("   ") is None

    def test_normalize_ref_with_punctuation(self):
        assert _normalize_ref("García-Huidobro, Juan") == "garcia huidobro juan"


class TestNormalizeRefList:
    """Tests for _normalize_ref_list function."""

    def test_normalize_list_basic(self):
        names = ["Juan Pérez", "María García"]
        result = _normalize_ref_list(names)
        assert result == ["juan perez", "maria garcia"]

    def test_normalize_list_filters_empty(self):
        names = ["Juan Pérez", "", "María García", "   "]
        result = _normalize_ref_list(names)
        assert result == ["juan perez", "maria garcia"]

    def test_normalize_list_empty_input(self):
        assert _normalize_ref_list([]) == []


class TestParseMaterias:
    """Tests for _parse_materias function."""

    def test_parse_comma_separated(self):
        result = _parse_materias("Medio Ambiente, Minería, Energía")
        assert result == ["Medio Ambiente", "Minería", "Energía"]

    def test_parse_semicolon_separated(self):
        result = _parse_materias("Medio Ambiente; Minería; Energía")
        assert result == ["Medio Ambiente", "Minería", "Energía"]

    def test_parse_newline_separated(self):
        result = _parse_materias("Medio Ambiente\nMinería\nEnergía")
        assert result == ["Medio Ambiente", "Minería", "Energía"]

    def test_parse_empty_string(self):
        assert _parse_materias("") == []

    def test_parse_none(self):
        assert _parse_materias(None) == []

    def test_parse_single_item(self):
        assert _parse_materias("Medio Ambiente") == ["Medio Ambiente"]

    def test_parse_filters_empty_items(self):
        result = _parse_materias("Medio Ambiente, , Minería")
        assert result == ["Medio Ambiente", "Minería"]


class TestParseRepresentados:
    """Tests for _parse_representados function."""

    def test_parse_dash_separated(self):
        result = _parse_representados("Empresa A - Empresa B")
        assert result == ["Empresa A", "Empresa B"]

    def test_parse_comma_separated(self):
        result = _parse_representados("Empresa A, Empresa B")
        assert result == ["Empresa A", "Empresa B"]

    def test_parse_single_name(self):
        result = _parse_representados("Empresa Única")
        assert result == ["Empresa Única"]

    def test_parse_empty(self):
        assert _parse_representados("") == []
        assert _parse_representados(None) == []


class TestParseFinancistas:
    """Tests for _parse_financistas function."""

    def test_parse_dash_separated(self):
        result = _parse_financistas("Organismo A - Organismo B")
        assert result == ["Organismo A", "Organismo B"]

    def test_parse_comma_separated(self):
        result = _parse_financistas("Organismo A, Organismo B")
        assert result == ["Organismo A", "Organismo B"]

    def test_parse_empty(self):
        assert _parse_financistas("") == []
        assert _parse_financistas(None) == []


class TestParseDonantes:
    """Tests for _parse_donantes function."""

    def test_parse_dash_separated(self):
        result = _parse_donantes("Donante A - Donante B")
        assert result == ["Donante A", "Donante B"]

    def test_parse_single(self):
        result = _parse_donantes("Donante Único")
        assert result == ["Donante Único"]

    def test_parse_empty(self):
        assert _parse_donantes("") == []
        assert _parse_donantes(None) == []


class TestExtractAudienceEvent:
    """Tests for extract_audience_event function."""

    def test_extract_basic_audience(self):
        """Extract audience with all fields."""
        audiencia = ParsedAudiencia(
            uri="http://example.com/aud/123",
            codigo_uri="AUD-123",
            identificador_temporal=123,
            fecha_evento=datetime(2025, 1, 15, 10, 30, 0),
            fecha_actualizacion=datetime(2025, 1, 16, 8, 0, 0),
            pasivo=ParsedPasivo(
                nombre="Juan Pérez García",
                cargo="Ministro",
                institucion="Ministerio del Interior"
            ),
            activos=["María González", "Pedro López"],
            representados="Empresa ABC - Corporación XYZ",
            materias="Medio Ambiente, Minería",
            descripcion="Reunión de coordinación",
            observaciones="Sin observaciones",
            tipo="presencial",
            checksum="abc123",
        )

        event = extract_audience_event(audiencia)

        assert event.external_id == "AUD-123"
        assert event.event_type == "audience"
        assert event.date_start == date(2025, 1, 15)
        assert event.source == "infolobby_sparql"
        assert event.pasivo_ref == "juan perez garcia"
        assert event.activos_refs == ["maria gonzalez", "pedro lopez"]
        assert event.representados_refs == ["empresa abc", "corporacion xyz"]
        assert event.forma == "presencial"
        assert event.materias == ["Medio Ambiente", "Minería"]
        assert event.descripcion == "Reunión de coordinación"

    def test_extract_audience_without_pasivo(self):
        """Extract audience without pasivo data."""
        audiencia = ParsedAudiencia(
            uri="http://example.com/aud/456",
            codigo_uri="AUD-456",
            identificador_temporal=456,
            fecha_evento=None,
            fecha_actualizacion=None,
            pasivo=None,
            activos=[],
            representados=None,
            materias=None,
            descripcion=None,
            observaciones=None,
            tipo=None,
            checksum="def456",
        )

        event = extract_audience_event(audiencia)

        assert event.external_id == "AUD-456"
        assert event.date_start is None
        assert event.pasivo_ref is None
        assert event.activos_refs == []
        assert event.representados_refs == []
        assert event.materias == []

    def test_extract_audience_date_from_datetime(self):
        """Date should be extracted from datetime correctly."""
        audiencia = ParsedAudiencia(
            uri="http://example.com/aud/789",
            codigo_uri="AUD-789",
            identificador_temporal=789,
            fecha_evento=datetime(2025, 6, 20, 14, 0, 0),
            fecha_actualizacion=None,
            pasivo=None,
            activos=[],
            representados=None,
            materias=None,
            descripcion=None,
            observaciones=None,
            tipo=None,
            checksum="ghi789",
        )

        event = extract_audience_event(audiencia)
        assert event.date_start == date(2025, 6, 20)


class TestExtractTravelEvent:
    """Tests for extract_travel_event function."""

    def test_extract_basic_travel(self):
        """Extract travel with all fields."""
        viaje = ParsedViaje(
            uri="http://example.com/via/123",
            codigo_uri="VIA-123",
            identificador_temporal=123,
            fecha_evento=date(2025, 2, 1),
            fecha_actualizacion=datetime(2025, 2, 10, 8, 0, 0),
            descripcion="Viaje oficial a conferencia",
            razones="Participación en conferencia internacional",
            objetos="Nueva York, Estados Unidos",
            financistas="Organismo Internacional - Fundación ABC",
            costo=2500000,
            checksum="via123",
        )

        event = extract_travel_event(viaje)

        assert event.external_id == "VIA-123"
        assert event.event_type == "travel"
        assert event.date_start == date(2025, 2, 1)
        assert event.destino == "Nueva York, Estados Unidos"
        assert event.motivo == "Participación en conferencia internacional"
        assert event.costo_total == 2500000
        assert event.financiadores_refs == ["organismo internacional", "fundacion abc"]

    def test_extract_travel_minimal(self):
        """Extract travel with minimal data."""
        viaje = ParsedViaje(
            uri="http://example.com/via/456",
            codigo_uri="VIA-456",
            identificador_temporal=456,
            fecha_evento=None,
            fecha_actualizacion=None,
            descripcion=None,
            razones=None,
            objetos=None,
            financistas=None,
            costo=None,
            checksum="via456",
        )

        event = extract_travel_event(viaje)

        assert event.external_id == "VIA-456"
        assert event.date_start is None
        assert event.destino is None
        assert event.motivo is None
        assert event.costo_total is None
        assert event.financiadores_refs == []


class TestExtractDonationEvent:
    """Tests for extract_donation_event function."""

    def test_extract_basic_donation(self):
        """Extract donation with all fields."""
        donativo = ParsedDonativo(
            uri="http://example.com/don/123",
            codigo_uri="DON-123",
            identificador_temporal=123,
            fecha_evento=date(2025, 3, 10),
            fecha_actualizacion=datetime(2025, 3, 11, 8, 0, 0),
            descripcion="Libro de arte chileno",
            ocasion="Día del patrimonio",
            donantes="Fundación Cultural - Museo Nacional",
            checksum="don123",
        )

        event = extract_donation_event(donativo)

        assert event.external_id == "DON-123"
        assert event.event_type == "donation"
        assert event.date_start == date(2025, 3, 10)
        assert event.descripcion == "Libro de arte chileno"
        assert event.ocasion == "Día del patrimonio"
        assert event.donantes_refs == ["fundacion cultural", "museo nacional"]

    def test_extract_donation_minimal(self):
        """Extract donation with minimal data."""
        donativo = ParsedDonativo(
            uri="http://example.com/don/456",
            codigo_uri="DON-456",
            identificador_temporal=456,
            fecha_evento=None,
            fecha_actualizacion=None,
            descripcion=None,
            ocasion=None,
            donantes=None,
            checksum="don456",
        )

        event = extract_donation_event(donativo)

        assert event.external_id == "DON-456"
        assert event.date_start is None
        assert event.descripcion is None
        assert event.ocasion is None
        assert event.donantes_refs == []


class TestExtractEvents:
    """Tests for extract_events function."""

    def test_extract_all_types(self):
        """Extract events from all record types."""
        audiencias = [
            ParsedAudiencia(
                uri="http://aud/1", codigo_uri="AUD-1",
                identificador_temporal=1, fecha_evento=datetime(2025, 1, 1),
                fecha_actualizacion=None, pasivo=None, activos=[],
                representados=None, materias=None, descripcion=None,
                observaciones=None, tipo=None, checksum="a1",
            ),
            ParsedAudiencia(
                uri="http://aud/2", codigo_uri="AUD-2",
                identificador_temporal=2, fecha_evento=datetime(2025, 1, 2),
                fecha_actualizacion=None, pasivo=None, activos=[],
                representados=None, materias=None, descripcion=None,
                observaciones=None, tipo=None, checksum="a2",
            ),
        ]

        viajes = [
            ParsedViaje(
                uri="http://via/1", codigo_uri="VIA-1",
                identificador_temporal=1, fecha_evento=date(2025, 2, 1),
                fecha_actualizacion=None, descripcion=None, razones=None,
                objetos=None, financistas=None, costo=None, checksum="v1",
            ),
        ]

        donativos = [
            ParsedDonativo(
                uri="http://don/1", codigo_uri="DON-1",
                identificador_temporal=1, fecha_evento=date(2025, 3, 1),
                fecha_actualizacion=None, descripcion=None, ocasion=None,
                donantes=None, checksum="d1",
            ),
        ]

        events = extract_events(
            audiencias=audiencias,
            viajes=viajes,
            donativos=donativos,
        )

        assert len(events) == 4

        audience_events = [e for e in events if e.event_type == "audience"]
        travel_events = [e for e in events if e.event_type == "travel"]
        donation_events = [e for e in events if e.event_type == "donation"]

        assert len(audience_events) == 2
        assert len(travel_events) == 1
        assert len(donation_events) == 1

    def test_extract_only_audiencias(self):
        """Extract events with only audiencias."""
        audiencias = [
            ParsedAudiencia(
                uri="http://aud/1", codigo_uri="AUD-1",
                identificador_temporal=1, fecha_evento=None,
                fecha_actualizacion=None, pasivo=None, activos=[],
                representados=None, materias=None, descripcion=None,
                observaciones=None, tipo=None, checksum="a1",
            ),
        ]

        events = extract_events(audiencias=audiencias)

        assert len(events) == 1
        assert events[0].event_type == "audience"

    def test_extract_empty_lists(self):
        """Extract events with empty lists."""
        events = extract_events(
            audiencias=[],
            viajes=[],
            donativos=[],
        )
        assert events == []

    def test_extract_none_inputs(self):
        """Extract events with None inputs."""
        events = extract_events()
        assert events == []

        events = extract_events(audiencias=None, viajes=None, donativos=None)
        assert events == []

    def test_extract_preserves_order(self):
        """Events should be in order: audiencias, viajes, donativos."""
        audiencias = [
            ParsedAudiencia(
                uri="http://aud/1", codigo_uri="AUD-1",
                identificador_temporal=1, fecha_evento=None,
                fecha_actualizacion=None, pasivo=None, activos=[],
                representados=None, materias=None, descripcion=None,
                observaciones=None, tipo=None, checksum="a1",
            ),
        ]

        viajes = [
            ParsedViaje(
                uri="http://via/1", codigo_uri="VIA-1",
                identificador_temporal=1, fecha_evento=None,
                fecha_actualizacion=None, descripcion=None, razones=None,
                objetos=None, financistas=None, costo=None, checksum="v1",
            ),
        ]

        donativos = [
            ParsedDonativo(
                uri="http://don/1", codigo_uri="DON-1",
                identificador_temporal=1, fecha_evento=None,
                fecha_actualizacion=None, descripcion=None, ocasion=None,
                donantes=None, checksum="d1",
            ),
        ]

        events = extract_events(
            audiencias=audiencias,
            viajes=viajes,
            donativos=donativos,
        )

        assert events[0].external_id == "AUD-1"
        assert events[1].external_id == "VIA-1"
        assert events[2].external_id == "DON-1"


class TestEdgeCases:
    """Edge case tests."""

    def test_unicode_normalization(self):
        """Names with unicode characters should normalize correctly."""
        audiencia = ParsedAudiencia(
            uri="http://aud/unicode",
            codigo_uri="AUD-UNICODE",
            identificador_temporal=1,
            fecha_evento=None,
            fecha_actualizacion=None,
            pasivo=ParsedPasivo(
                nombre="José María Ñuñez",
                cargo="Director",
                institucion="Ministerio"
            ),
            activos=["André García-Huidobro"],
            representados=None,
            materias=None,
            descripcion=None,
            observaciones=None,
            tipo=None,
            checksum="unicode",
        )

        event = extract_audience_event(audiencia)

        assert event.pasivo_ref == "jose maria nunez"
        assert event.activos_refs == ["andre garcia huidobro"]

    def test_source_field_is_constant(self):
        """All events should have source = infolobby_sparql."""
        audiencia = ParsedAudiencia(
            uri="http://aud/1", codigo_uri="AUD-1",
            identificador_temporal=1, fecha_evento=None,
            fecha_actualizacion=None, pasivo=None, activos=[],
            representados=None, materias=None, descripcion=None,
            observaciones=None, tipo=None, checksum="a1",
        )
        viaje = ParsedViaje(
            uri="http://via/1", codigo_uri="VIA-1",
            identificador_temporal=1, fecha_evento=None,
            fecha_actualizacion=None, descripcion=None, razones=None,
            objetos=None, financistas=None, costo=None, checksum="v1",
        )
        donativo = ParsedDonativo(
            uri="http://don/1", codigo_uri="DON-1",
            identificador_temporal=1, fecha_evento=None,
            fecha_actualizacion=None, descripcion=None, ocasion=None,
            donantes=None, checksum="d1",
        )

        aud_event = extract_audience_event(audiencia)
        tra_event = extract_travel_event(viaje)
        don_event = extract_donation_event(donativo)

        assert aud_event.source == "infolobby_sparql"
        assert tra_event.source == "infolobby_sparql"
        assert don_event.source == "infolobby_sparql"
