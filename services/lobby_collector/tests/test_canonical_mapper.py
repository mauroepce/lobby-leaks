"""
Tests for canonical entity mapping from staging rows.
"""

import pytest
from datetime import datetime
from services.lobby_collector.canonical_mapper import (
    map_staging_row,
    EntityBundle,
    _infer_org_tipo,
)


class TestEntityBundle:
    """Test EntityBundle helper class."""

    def test_add_person(self):
        """Test adding a person to the bundle."""
        bundle = EntityBundle()
        person_id = bundle.add_person(
            tenant_code="CL",
            nombres="Juan",
            apellidos="Pérez",
            cargo="Senador",
            rut="123456785",
        )

        assert len(bundle.persons) == 1
        person = bundle.persons[0]
        assert person["id"] == person_id
        assert person["tenantCode"] == "CL"
        assert person["nombres"] == "Juan"
        assert person["apellidos"] == "Pérez"
        assert person["nombresCompletos"] == "Juan Pérez"
        assert person["normalizedName"] == "juan pérez"
        assert person["cargo"] == "Senador"
        assert person["rut"] == "123456785"

    def test_add_organisation(self):
        """Test adding an organisation to the bundle."""
        bundle = EntityBundle()
        org_id = bundle.add_organisation(
            tenant_code="CL",
            name="Ministerio de Hacienda",
            tipo="ministerio",
        )

        assert len(bundle.organisations) == 1
        org = bundle.organisations[0]
        assert org["id"] == org_id
        assert org["tenantCode"] == "CL"
        assert org["name"] == "Ministerio de Hacienda"
        assert org["normalizedName"] == "ministerio de hacienda"
        assert org["tipo"] == "ministerio"

    def test_add_event(self):
        """Test adding an event to the bundle."""
        bundle = EntityBundle()
        fecha = datetime(2023, 5, 15, 10, 30)
        event_id = bundle.add_event(
            tenant_code="CL",
            external_id="AUD-2023-001",
            kind="audiencia",
            fecha=fecha,
            descripcion="Reunión sobre presupuesto",
        )

        assert len(bundle.events) == 1
        event = bundle.events[0]
        assert event["id"] == event_id
        assert event["tenantCode"] == "CL"
        assert event["externalId"] == "AUD-2023-001"
        assert event["kind"] == "audiencia"
        assert event["fecha"] == fecha
        assert event["descripcion"] == "Reunión sobre presupuesto"

    def test_add_edge_person_to_org(self):
        """Test adding an edge from person to organisation."""
        bundle = EntityBundle()
        person_id = bundle.add_person("CL", "Juan", "Pérez")
        org_id = bundle.add_organisation("CL", "Ministerio")
        event_id = bundle.add_event("CL", "E-001", "audiencia")

        bundle.add_edge(
            tenant_code="CL",
            event_id=event_id,
            label="MEETS",
            from_person_id=person_id,
            to_org_id=org_id,
        )

        assert len(bundle.edges) == 1
        edge = bundle.edges[0]
        assert edge["tenantCode"] == "CL"
        assert edge["eventId"] == event_id
        assert edge["label"] == "MEETS"
        assert edge["fromPersonId"] == person_id
        assert edge["toOrgId"] == org_id
        assert edge["fromOrgId"] is None
        assert edge["toPersonId"] is None

    def test_add_edge_org_to_person(self):
        """Test adding an edge from organisation to person."""
        bundle = EntityBundle()
        person_id = bundle.add_person("CL", "Juan", "Pérez")
        org_id = bundle.add_organisation("CL", "Empresa S.A.")
        event_id = bundle.add_event("CL", "D-001", "donativo")

        bundle.add_edge(
            tenant_code="CL",
            event_id=event_id,
            label="CONTRIBUTES",
            from_org_id=org_id,
            to_person_id=person_id,
            metadata={"monto": "1000000"},
        )

        assert len(bundle.edges) == 1
        edge = bundle.edges[0]
        assert edge["fromOrgId"] == org_id
        assert edge["toPersonId"] == person_id
        assert edge["metadata"]["monto"] == "1000000"

    def test_add_edge_validation_no_from(self):
        """Test that edge validation requires exactly one 'from' entity."""
        bundle = EntityBundle()
        event_id = bundle.add_event("CL", "E-001", "audiencia")
        person_id = bundle.add_person("CL", "Juan", "Pérez")

        with pytest.raises(ValueError, match="exactly one from and one to"):
            bundle.add_edge(
                tenant_code="CL",
                event_id=event_id,
                label="MEETS",
                to_person_id=person_id,
            )

    def test_add_edge_validation_no_to(self):
        """Test that edge validation requires exactly one 'to' entity."""
        bundle = EntityBundle()
        event_id = bundle.add_event("CL", "E-001", "audiencia")
        person_id = bundle.add_person("CL", "Juan", "Pérez")

        with pytest.raises(ValueError, match="exactly one from and one to"):
            bundle.add_edge(
                tenant_code="CL",
                event_id=event_id,
                label="MEETS",
                from_person_id=person_id,
            )


class TestMapAudiencia:
    """Test mapping audiencia events."""

    def test_map_audiencia_basic(self):
        """Test basic audiencia mapping: Person MEETS Org."""
        row = {
            "tenantCode": "CL",
            "externalId": "AUD-2023-001",
            "kind": "audiencia",
            "nombres": "Juan Carlos",
            "apellidos": "Pérez García",
            "cargo": "Senador",
            "institucion": "Ministerio de Hacienda",
            "fecha": datetime(2023, 5, 15),
        }
        raw_data = {
            "nombres": "Juan Carlos",
            "apellidos": "Pérez García",
            "cargo": "Senador",
            "sujeto_pasivo": "Ministerio de Hacienda",
            "rut": "12.345.678-5",
        }

        bundle = map_staging_row(row, raw_data)

        # Verify entities
        assert len(bundle.persons) == 1
        assert len(bundle.organisations) == 1
        assert len(bundle.events) == 1
        assert len(bundle.edges) == 1

        # Verify person
        person = bundle.persons[0]
        assert person["nombres"] == "Juan Carlos"
        assert person["apellidos"] == "Pérez García"
        assert person["cargo"] == "Senador"
        assert person["rut"] == "123456785"  # Normalized

        # Verify organisation
        org = bundle.organisations[0]
        assert org["name"] == "Ministerio de Hacienda"
        assert org["tipo"] == "ministerio"

        # Verify event
        event = bundle.events[0]
        assert event["externalId"] == "AUD-2023-001"
        assert event["kind"] == "audiencia"

        # Verify edge: Person MEETS Org
        edge = bundle.edges[0]
        assert edge["label"] == "MEETS"
        assert edge["fromPersonId"] == person["id"]
        assert edge["toOrgId"] == org["id"]
        assert edge["metadata"]["cargo"] == "Senador"


class TestMapViaje:
    """Test mapping viaje events."""

    def test_map_viaje_basic(self):
        """Test basic viaje mapping: Person TRAVELS_TO Org."""
        row = {
            "tenantCode": "CL",
            "externalId": "VIA-2023-001",
            "kind": "viaje",
            "nombres": "María",
            "apellidos": "González",
            "cargo": "Diputada",
            "institucion": "ONU",
            "destino": "Nueva York, Estados Unidos",
            "fecha": datetime(2023, 6, 1),
        }
        raw_data = {
            "nombres": "María",
            "apellidos": "González",
            "cargo": "Diputada",
            "institucion_destino": "ONU",
            "destino": "Nueva York, Estados Unidos",
        }

        bundle = map_staging_row(row, raw_data)

        # Verify entities
        assert len(bundle.persons) == 1
        assert len(bundle.organisations) == 1
        assert len(bundle.events) == 1
        assert len(bundle.edges) == 1

        # Verify person
        person = bundle.persons[0]
        assert person["nombres"] == "María"
        assert person["apellidos"] == "González"

        # Verify organisation (destination)
        org = bundle.organisations[0]
        assert org["name"] == "ONU"
        assert org["tipo"] == "destino"

        # Verify edge: Person TRAVELS_TO Org
        edge = bundle.edges[0]
        assert edge["label"] == "TRAVELS_TO"
        assert edge["fromPersonId"] == person["id"]
        assert edge["toOrgId"] == org["id"]
        assert edge["metadata"]["destino"] == "Nueva York, Estados Unidos"


class TestMapDonativo:
    """Test mapping donativo events."""

    def test_map_donativo_basic(self):
        """Test basic donativo mapping: Org CONTRIBUTES Person."""
        row = {
            "tenantCode": "CL",
            "externalId": "DON-2023-001",
            "kind": "donativo",
            "nombres": "Pedro",
            "apellidos": "López",
            "cargo": "Candidato",
            "institucion": "Empresa Minera S.A.",
            "monto": 5000000,
            "fecha": datetime(2023, 4, 10),
        }
        raw_data = {
            "nombres": "Pedro",
            "apellidos": "López",
            "cargo": "Candidato",
            "institucion_donante": "Empresa Minera S.A.",
            "monto": 5000000,
        }

        bundle = map_staging_row(row, raw_data)

        # Verify entities
        assert len(bundle.persons) == 1
        assert len(bundle.organisations) == 1
        assert len(bundle.events) == 1
        assert len(bundle.edges) == 1

        # Verify person (recipient)
        person = bundle.persons[0]
        assert person["nombres"] == "Pedro"
        assert person["apellidos"] == "López"

        # Verify organisation (donor)
        org = bundle.organisations[0]
        assert org["name"] == "Empresa Minera S.A."
        assert org["tipo"] == "empresa"

        # Verify edge: Org CONTRIBUTES Person
        edge = bundle.edges[0]
        assert edge["label"] == "CONTRIBUTES"
        assert edge["fromOrgId"] == org["id"]
        assert edge["toPersonId"] == person["id"]
        assert edge["metadata"]["monto"] == "5000000"


class TestInferOrgTipo:
    """Test organisation type inference."""

    def test_infer_ministerio(self):
        """Test inferring ministerio type."""
        assert _infer_org_tipo("Ministerio de Hacienda") == "ministerio"
        assert _infer_org_tipo("Ministerio del Interior") == "ministerio"

    def test_infer_subsecretaria(self):
        """Test inferring subsecretaria type."""
        assert _infer_org_tipo("Subsecretaría de Transportes") == "subsecretaria"

    def test_infer_legislativo(self):
        """Test inferring legislative institutions."""
        assert _infer_org_tipo("Cámara de Diputados") == "legislativo"
        assert _infer_org_tipo("Senado") == "legislativo"

    def test_infer_judicial(self):
        """Test inferring judicial institutions."""
        assert _infer_org_tipo("Corte Suprema") == "judicial"
        assert _infer_org_tipo("Tribunal Constitucional") == "judicial"

    def test_infer_partido(self):
        """Test inferring political parties."""
        assert _infer_org_tipo("Partido Demócrata Cristiano") == "partido"

    def test_infer_empresa(self):
        """Test inferring companies."""
        assert _infer_org_tipo("Minera Los Pelambres S.A.") == "empresa"
        assert _infer_org_tipo("Banco Santander") == "empresa"

    def test_infer_ong(self):
        """Test inferring NGOs."""
        assert _infer_org_tipo("Fundación Chile") == "ong"
        assert _infer_org_tipo("ONG Greenpeace") == "ong"

    def test_infer_otro(self):
        """Test default type for unknown organisations."""
        assert _infer_org_tipo("Universidad de Chile") == "otro"
