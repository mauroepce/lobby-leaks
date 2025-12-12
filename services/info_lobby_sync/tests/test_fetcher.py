"""Tests for fetcher module."""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from ..fetcher import (
    SPARQLClient,
    SPARQLFetchError,
    load_query,
    fetch_audiencias,
    fetch_viajes,
    fetch_donativos,
    _extract_bindings,
    QUERIES_DIR,
)


class TestLoadQuery:
    """Tests for query file loading."""

    def test_load_audiencias_query(self):
        query = load_query("audiencias")
        assert "cplt:RegistroAudiencia" in query
        assert "{limit}" in query
        assert "{offset}" in query

    def test_load_viajes_query(self):
        query = load_query("viajes")
        assert "cplt:Viaje" in query

    def test_load_donativos_query(self):
        query = load_query("donativos")
        assert "cplt:Donativo" in query

    def test_load_nonexistent_query(self):
        with pytest.raises(FileNotFoundError):
            load_query("nonexistent")


class TestExtractBindings:
    """Tests for SPARQL result extraction."""

    def test_extract_bindings_normal(self):
        result = {
            "results": {
                "bindings": [
                    {
                        "uri": {"type": "uri", "value": "http://example.com/1"},
                        "name": {"type": "literal", "value": "Test"},
                    },
                    {
                        "uri": {"type": "uri", "value": "http://example.com/2"},
                        "name": {"type": "literal", "value": "Test 2"},
                    },
                ]
            }
        }

        records = _extract_bindings(result)

        assert len(records) == 2
        assert records[0]["uri"] == "http://example.com/1"
        assert records[0]["name"] == "Test"
        assert records[1]["uri"] == "http://example.com/2"

    def test_extract_bindings_empty(self):
        result = {"results": {"bindings": []}}
        records = _extract_bindings(result)
        assert records == []

    def test_extract_bindings_missing_results(self):
        result = {}
        records = _extract_bindings(result)
        assert records == []


class TestSPARQLClient:
    """Tests for SPARQL client."""

    def test_build_url(self):
        client = SPARQLClient(
            endpoint="http://test.com/sparql",
            default_graph="http://test.com/graph"
        )

        url = client._build_url("SELECT * WHERE { ?s ?p ?o }")

        assert "http://test.com/sparql?" in url
        assert "default-graph-uri=" in url
        assert "query=" in url
        assert "format=" in url

    @patch("httpx.Client")
    def test_execute_success(self, mock_client_class):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": {"bindings": [{"a": {"value": "1"}}]}
        }

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = SPARQLClient()
        result = client.execute("SELECT * WHERE { ?s ?p ?o }")

        assert result == {"results": {"bindings": [{"a": {"value": "1"}}]}}

    @patch("httpx.Client")
    def test_execute_403_error(self, mock_client_class):
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = SPARQLClient()

        with pytest.raises(SPARQLFetchError) as exc_info:
            client.execute("SELECT * WHERE { ?s ?p ?o }")

        assert "403" in str(exc_info.value)

    @patch("httpx.Client")
    def test_context_manager(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        with SPARQLClient() as client:
            pass

        mock_client.close.assert_called_once()


class TestFetchFunctions:
    """Tests for fetch functions."""

    @patch("services.info_lobby_sync.fetcher.SPARQLClient")
    def test_fetch_audiencias(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.execute.return_value = {
            "results": {
                "bindings": [
                    {
                        "uri": {"value": "http://example.com/1"},
                        "codigoURI": {"value": "abc123"},
                    }
                ]
            }
        }

        records = fetch_audiencias(client=mock_client, limit=100, offset=0)

        assert len(records) == 1
        assert records[0]["codigoURI"] == "abc123"

    @patch("services.info_lobby_sync.fetcher.SPARQLClient")
    def test_fetch_viajes(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.execute.return_value = {
            "results": {
                "bindings": [
                    {
                        "uri": {"value": "http://example.com/viaje/1"},
                        "codigoURI": {"value": "viaje123"},
                    }
                ]
            }
        }

        records = fetch_viajes(client=mock_client, limit=100, offset=0)

        assert len(records) == 1
        assert records[0]["codigoURI"] == "viaje123"

    @patch("services.info_lobby_sync.fetcher.SPARQLClient")
    def test_fetch_donativos(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.execute.return_value = {
            "results": {
                "bindings": [
                    {
                        "uri": {"value": "http://example.com/donativo/1"},
                        "codigoURI": {"value": "donativo123"},
                    }
                ]
            }
        }

        records = fetch_donativos(client=mock_client, limit=100, offset=0)

        assert len(records) == 1
        assert records[0]["codigoURI"] == "donativo123"
