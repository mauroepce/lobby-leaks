"""
Tests for fallback and graceful degradation functionality.

Tests that the service handles disabled mode and API degradation correctly.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from services.lobby_collector.client import LobbyApiDegraded
from services.lobby_collector.main import main
from services.lobby_collector.settings import LobbyCollectorSettings


pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_settings_disabled():
    """Mock settings with API disabled."""
    mock_config = MagicMock(spec=LobbyCollectorSettings)
    mock_config.enable_lobby_api = False
    mock_config.lobby_api_base_url = "https://www.leylobby.gob.cl/api/v1"
    mock_config.lobby_api_key = "test-key"
    mock_config.page_size = 100
    mock_config.default_since_days = 7
    mock_config.service_name = "lobby-collector"
    return mock_config


@pytest.fixture
def mock_settings_enabled():
    """Mock settings with API enabled."""
    mock_config = MagicMock(spec=LobbyCollectorSettings)
    mock_config.enable_lobby_api = True
    mock_config.lobby_api_base_url = "https://www.leylobby.gob.cl/api/v1"
    mock_config.lobby_api_key = "test-key"
    mock_config.page_size = 100
    mock_config.default_since_days = 7
    mock_config.api_timeout = 30.0
    mock_config.api_max_retries = 3
    mock_config.rate_limit_delay = 0.5
    mock_config.service_name = "lobby-collector"
    return mock_config


class TestDisabledMode:
    """Test behavior when ENABLE_LOBBY_API=false."""

    async def test_main_exits_gracefully_when_disabled(self, mock_settings_disabled):
        """Test that main() exits with code 0 when API is disabled."""
        with patch("services.lobby_collector.main.settings", return_value=mock_settings_disabled):
            with patch("sys.argv", ["main.py", "--days", "7"]):
                exit_code = await main()

        assert exit_code == 0

    async def test_disabled_mode_logs_structured_message(self, mock_settings_disabled, caplog):
        """Test that disabled mode logs correct JSON structure."""
        import json
        import logging

        caplog.set_level(logging.INFO)

        with patch("services.lobby_collector.main.settings", return_value=mock_settings_disabled):
            with patch("sys.argv", ["main.py"]):
                exit_code = await main()

        # Check that structured log was emitted
        assert exit_code == 0
        # Look for the JSON log message
        json_logs = [record.message for record in caplog.records if "{" in record.message and "service" in record.message]
        assert len(json_logs) > 0

        log_data = json.loads(json_logs[0])
        assert log_data["service"] == "lobby-collector"
        assert log_data["mode"] == "disabled"
        assert "timestamp" in log_data

    async def test_test_connection_ignores_disabled_flag(self, mock_settings_disabled):
        """Test that --test-connection runs even when API is disabled."""
        # Add missing attributes to mock
        mock_settings_disabled.api_timeout = 30.0
        mock_settings_disabled.api_max_retries = 3
        mock_settings_disabled.rate_limit_delay = 0.5

        with patch("services.lobby_collector.main.settings", return_value=mock_settings_disabled):
            with patch("services.lobby_collector.client.settings", return_value=mock_settings_disabled):
                with patch("sys.argv", ["main.py", "--test-connection"]):
                    # Mock the HTTP client to return 401
                    with patch("services.lobby_collector.client.httpx.AsyncClient") as mock_client:
                        mock_resp = AsyncMock()
                        mock_resp.status_code = 401
                        mock_resp.text = "Unauthorized"

                        mock_get = AsyncMock(return_value=mock_resp)
                        mock_client.return_value.__aenter__.return_value.get = mock_get

                        exit_code = await main()

        # Should exit 0 even though API returned 401 (degraded mode)
        assert exit_code == 0


class TestDegradedMode:
    """Test behavior when API returns 401/5xx/timeout."""

    async def test_degraded_on_401(self, mock_settings_enabled):
        """Test that 401 triggers degraded mode with exit code 0."""
        import httpx

        with patch("services.lobby_collector.main.settings", return_value=mock_settings_enabled):
            with patch("services.lobby_collector.client.settings", return_value=mock_settings_enabled):
                with patch("sys.argv", ["main.py", "--days", "1"]):
                    # Mock HTTP client to return 401
                    with patch("services.lobby_collector.client.httpx.AsyncClient") as mock_client:
                        mock_resp = AsyncMock()
                        mock_resp.status_code = 401
                        mock_resp.text = "Unauthorized"

                        mock_get = AsyncMock(return_value=mock_resp)
                        mock_client.return_value.__aenter__.return_value.get = mock_get

                        exit_code = await main()

        assert exit_code == 0

    async def test_degraded_on_500(self, mock_settings_enabled):
        """Test that 500 error (after retries) triggers degraded mode."""
        with patch("services.lobby_collector.main.settings", return_value=mock_settings_enabled):
            with patch("services.lobby_collector.client.settings", return_value=mock_settings_enabled):
                with patch("sys.argv", ["main.py", "--days", "1"]):
                    with patch("asyncio.sleep"):  # Speed up retries
                        # Mock HTTP client to return 500
                        with patch("services.lobby_collector.client.httpx.AsyncClient") as mock_client:
                            import httpx

                            # Create mock response that raises HTTPStatusError
                            mock_resp = MagicMock()
                            mock_resp.status_code = 500
                            mock_resp.text = "Internal Server Error"

                            error = httpx.HTTPStatusError("500", request=MagicMock(), response=mock_resp)

                            mock_get = AsyncMock(side_effect=error)
                            mock_resp.raise_for_status = MagicMock(side_effect=error)

                            mock_client.return_value.__aenter__.return_value.get = mock_get

                            exit_code = await main()

        assert exit_code == 0

    async def test_degraded_on_timeout(self, mock_settings_enabled):
        """Test that timeout (after retries) triggers degraded mode."""
        import httpx

        with patch("services.lobby_collector.main.settings", return_value=mock_settings_enabled):
            with patch("services.lobby_collector.client.settings", return_value=mock_settings_enabled):
                with patch("sys.argv", ["main.py", "--days", "1"]):
                    with patch("asyncio.sleep"):  # Speed up retries
                        # Mock HTTP client to timeout
                        with patch("services.lobby_collector.client.httpx.AsyncClient") as mock_client:
                            mock_get = AsyncMock(side_effect=httpx.TimeoutException("Request timeout"))
                            mock_client.return_value.__aenter__.return_value.get = mock_get

                            exit_code = await main()

        assert exit_code == 0

    async def test_degraded_logs_structured_warning(self, mock_settings_enabled, caplog):
        """Test that degraded mode logs structured JSON warning."""
        import json

        with patch("services.lobby_collector.main.settings", return_value=mock_settings_enabled):
            with patch("services.lobby_collector.client.settings", return_value=mock_settings_enabled):
                with patch("sys.argv", ["main.py", "--days", "1"]):
                    # Mock 401 response
                    with patch("services.lobby_collector.client.httpx.AsyncClient") as mock_client:
                        mock_resp = AsyncMock()
                        mock_resp.status_code = 401
                        mock_resp.text = "Unauthorized"

                        mock_get = AsyncMock(return_value=mock_resp)
                        mock_client.return_value.__aenter__.return_value.get = mock_get

                        exit_code = await main()

        assert exit_code == 0

        # Check for structured warning log
        json_logs = [record.message for record in caplog.records if record.levelname == "WARNING" and record.message.startswith("{")]
        assert len(json_logs) > 0

        log_data = json.loads(json_logs[0])
        assert log_data["service"] == "lobby-collector"
        assert log_data["status"] == "degraded"
        assert log_data["reason"] in ["HTTP_401", "timeout", "network_error"]
        assert "timestamp" in log_data
        assert log_data["records_processed"] == 0


class TestLobbyApiDegradedException:
    """Test LobbyApiDegraded exception properties."""

    def test_exception_has_reason(self):
        """Test that exception stores reason."""
        exc = LobbyApiDegraded("HTTP_401", 401)
        assert exc.reason == "HTTP_401"
        assert exc.status_code == 401

    def test_exception_without_status_code(self):
        """Test exception can be created without status code."""
        exc = LobbyApiDegraded("timeout", None)
        assert exc.reason == "timeout"
        assert exc.status_code is None

    def test_exception_message(self):
        """Test exception message format."""
        exc = LobbyApiDegraded("HTTP_500", 500)
        assert str(exc) == "API degraded: HTTP_500"
