"""
Tests for pagination functionality.

Tests that the client correctly handles multi-page responses
and API authentication.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from services.lobby_collector.client import fetch_page, LobbyAPIAuthError, LobbyAPIRateLimitError
from services.lobby_collector.ingest import fetch_since
from services.lobby_collector.settings import LobbyCollectorSettings


pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def mock_settings():
    """Mock settings to avoid needing LOBBY_API_KEY in environment."""
    mock_config = MagicMock(spec=LobbyCollectorSettings)
    mock_config.lobby_api_base_url = "https://api.test.com/v1"
    mock_config.lobby_api_key = "test-api-key"
    mock_config.page_size = 100
    mock_config.default_since_days = 7
    mock_config.api_timeout = 30.0
    mock_config.api_max_retries = 3
    mock_config.rate_limit_delay = 0.5
    mock_config.service_name = "lobby-collector"

    with patch("services.lobby_collector.client.settings", return_value=mock_config):
        with patch("services.lobby_collector.ingest.settings", return_value=mock_config):
            yield mock_config


class TestPagination:
    """Test pagination handling."""

    async def test_fetch_single_page(self):
        """Test fetching a single page of data."""
        mock_response = {
            "data": [
                {"id": 1, "sujeto_pasivo": "Ministerio A"},
                {"id": 2, "sujeto_pasivo": "Ministerio B"}
            ],
            "has_more": False,
            "total": 2
        }

        with patch("services.lobby_collector.client.httpx.AsyncClient") as mock_client:
            # Create mock response
            mock_resp = AsyncMock()
            mock_resp.status_code = 200
            mock_resp.json = AsyncMock(return_value=mock_response)
            mock_resp.raise_for_status = lambda: None

            # Mock the get method to return our mock response
            mock_get = AsyncMock(return_value=mock_resp)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            result = await fetch_page("/audiencias", {"page": 1})

            assert result == mock_response
            assert len(result["data"]) == 2

    async def test_fetch_multiple_pages(self):
        """Test fetching multiple pages automatically."""
        # Simulate 3 pages of data
        mock_responses = [
            {
                "data": [{"id": 1}, {"id": 2}],
                "has_more": True,
                "total": 5
            },
            {
                "data": [{"id": 3}, {"id": 4}],
                "has_more": True,
                "total": 5
            },
            {
                "data": [{"id": 5}],
                "has_more": False,
                "total": 5
            }
        ]

        with patch("services.lobby_collector.client.httpx.AsyncClient") as mock_client:
            # Create mock responses
            mock_resps = []
            for mock_data in mock_responses:
                mock_resp = AsyncMock()
                mock_resp.status_code = 200
                mock_resp.json = AsyncMock(return_value=mock_data)
                mock_resp.raise_for_status = lambda: None
                mock_resps.append(mock_resp)

            # Mock the get method to return different responses for each call
            mock_get = AsyncMock(side_effect=mock_resps)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            # Collect all records from iterator
            records = []
            async for record in fetch_since(datetime(2025, 1, 1)):
                records.append(record)

            # Should have fetched all 5 records across 3 pages
            assert len(records) == 5
            assert records[0]["id"] == 1
            assert records[4]["id"] == 5

            # Should have made 3 requests (one per page)
            assert mock_get.call_count == 3

    async def test_empty_page(self):
        """Test handling of empty pages."""
        mock_response = {
            "data": [],
            "has_more": False,
            "total": 0
        }

        with patch("services.lobby_collector.client.httpx.AsyncClient") as mock_client:
            mock_resp = AsyncMock()
            mock_resp.status_code = 200
            mock_resp.json = AsyncMock(return_value=mock_response)
            mock_resp.raise_for_status = lambda: None

            mock_get = AsyncMock(return_value=mock_resp)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            records = []
            async for record in fetch_since(datetime(2025, 1, 1)):
                records.append(record)

            assert len(records) == 0


class TestAuthentication:
    """Test API authentication."""

    async def test_api_key_header_included(self):
        """Test that API key is included in request headers."""
        with patch("services.lobby_collector.client.httpx.AsyncClient") as mock_client:
            mock_resp = AsyncMock()
            mock_resp.status_code = 200
            mock_resp.json = AsyncMock(return_value={"data": [], "has_more": False})
            mock_resp.raise_for_status = lambda: None

            mock_get = AsyncMock(return_value=mock_resp)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            await fetch_page("/audiencias", {"page": 1})

            # Verify Authorization header was included
            call_args = mock_get.call_args
            headers = call_args.kwargs.get("headers", {})
            assert "Authorization" in headers
            assert headers["Authorization"].startswith("Bearer ")

    async def test_authentication_error_401(self):
        """Test handling of 401 authentication error."""
        with patch("services.lobby_collector.client.httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 401
            mock_response.text = "Unauthorized"

            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            with pytest.raises(LobbyAPIAuthError) as exc_info:
                await fetch_page("/audiencias", {"page": 1})

            assert "401" in str(exc_info.value)

    async def test_authentication_error_403(self):
        """Test handling of 403 forbidden error."""
        with patch("services.lobby_collector.client.httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 403
            mock_response.text = "Forbidden"

            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            with pytest.raises(LobbyAPIAuthError) as exc_info:
                await fetch_page("/audiencias", {"page": 1})

            assert "403" in str(exc_info.value)


class TestRateLimiting:
    """Test rate limiting handling."""

    async def test_rate_limit_error_429(self):
        """Test handling of 429 rate limit error."""
        with patch("services.lobby_collector.client.httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 429
            mock_response.headers = {"Retry-After": "60"}
            mock_response.text = "Rate limit exceeded"

            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            with pytest.raises(LobbyAPIRateLimitError) as exc_info:
                await fetch_page("/audiencias", {"page": 1})

            assert "60" in str(exc_info.value)


class TestRetries:
    """Test retry logic for failed requests."""

    async def test_retry_on_network_error(self):
        """Test that network errors trigger retries."""
        import httpx

        with patch("services.lobby_collector.client.httpx.AsyncClient") as mock_client:
            # Create successful response
            success_resp = AsyncMock()
            success_resp.status_code = 200
            success_resp.json = AsyncMock(return_value={"data": [], "has_more": False})
            success_resp.raise_for_status = lambda: None

            # First two calls fail, third succeeds
            mock_get = AsyncMock()
            mock_get.side_effect = [
                httpx.NetworkError("Connection failed"),
                httpx.NetworkError("Connection failed"),
                success_resp
            ]
            mock_client.return_value.__aenter__.return_value.get = mock_get

            # Should eventually succeed after retries
            with patch("asyncio.sleep"):  # Mock sleep to speed up test
                result = await fetch_page("/audiencias", {"page": 1})

            assert result == {"data": [], "has_more": False}
            assert mock_get.call_count == 3  # 1 initial + 2 retries

    async def test_retry_exhaustion(self):
        """Test that max retries are exhausted on persistent failures."""
        import httpx

        with patch("services.lobby_collector.client.httpx.AsyncClient") as mock_client:
            # All calls fail
            mock_get = AsyncMock(side_effect=httpx.NetworkError("Connection failed"))
            mock_client.return_value.__aenter__.return_value.get = mock_get

            with patch("asyncio.sleep"):  # Mock sleep to speed up test
                with pytest.raises(httpx.NetworkError):
                    await fetch_page("/audiencias", {"page": 1})

            # Should have tried: 1 initial + 3 retries = 4 total
            assert mock_get.call_count == 4
