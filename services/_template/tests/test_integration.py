"""
Integration tests for the service template.

These tests verify that the components work together correctly
without mocking, using real configuration and CLI interfaces.
"""

import subprocess
import sys
import os
from pathlib import Path
import pytest

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class TestConfigurationIntegration:
    """Test that configuration loading works with real .env file."""

    def test_settings_load_from_env(self):
        """Test that settings correctly load from the .env file."""
        # Import here to ensure clean state
        from services._template.settings import get_settings

        # Clear cache to ensure fresh load
        get_settings.cache_clear()

        settings = get_settings()

        # Verify required settings are loaded
        assert settings.api_key is not None
        assert settings.api_key != ""
        assert settings.environment in ["development", "staging", "production"]
        assert settings.log_level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    def test_settings_validation_works(self):
        """Test that pydantic validation is working."""
        from services._template.settings import Settings
        from pydantic import ValidationError

        # Test that invalid environment raises error
        with pytest.raises(ValidationError):
            Settings(
                api_key="test",
                environment="invalid_env"  # Should fail validation
            )

    def test_settings_helper_methods(self):
        """Test that settings helper methods work correctly."""
        from services._template.settings import get_settings

        settings = get_settings()

        # Test helper methods
        assert isinstance(settings.is_development(), bool)
        assert isinstance(settings.is_production(), bool)

        # Test API headers generation
        headers = settings.get_api_headers()
        assert "Authorization" in headers
        assert "User-Agent" in headers
        assert settings.api_key in headers["Authorization"]


class TestCLIIntegration:
    """Test CLI interface with real subprocess calls."""

    def test_cli_help_command(self):
        """Test that CLI help command works."""
        result = subprocess.run(
            [sys.executable, "-m", "services._template.main", "--help"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert "LobbyLeaks Service Template" in result.stdout
        assert "--since" in result.stdout
        assert "--log-level" in result.stdout

    def test_cli_version_command(self):
        """Test that CLI version command works."""
        result = subprocess.run(
            [sys.executable, "-m", "services._template.main", "--version"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert "LobbyLeaks Service Template" in result.stdout

    def test_cli_missing_required_args(self):
        """Test that CLI fails appropriately when missing required arguments."""
        result = subprocess.run(
            [sys.executable, "-m", "services._template.main"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )

        # Should fail because --since is required
        assert result.returncode != 0
        assert "required" in result.stderr.lower() or "the following arguments are required" in result.stderr

    def test_cli_invalid_date_format(self):
        """Test that CLI handles invalid date format gracefully."""
        result = subprocess.run(
            [sys.executable, "-m", "services._template.main", "--since", "invalid-date"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30  # Prevent hanging
        )

        # Should fail or handle gracefully
        assert result.returncode != 0

    def test_cli_log_level_override(self):
        """Test that CLI log level override works."""
        # This test runs briefly and exits with error (no real API)
        # but we can verify the log level is accepted
        result = subprocess.run(
            [
                sys.executable, "-m", "services._template.main",
                "--since", "2025-01-01",
                "--log-level", "DEBUG"
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=10  # Short timeout since we expect it to fail
        )

        # Should start but fail due to API call (exit code 1)
        # The important thing is it doesn't crash on invalid args
        assert result.returncode in [0, 1]  # 0 = success, 1 = expected failure


class TestLoggingIntegration:
    """Test that logging configuration works correctly."""

    def test_logging_import_works(self):
        """Test that logging can be imported without circular import issues."""
        # This should not raise any import errors
        from services._template.log_config import get_logger, configure_logging

        logger = get_logger(__name__)
        assert logger is not None

    def test_logging_configuration(self):
        """Test that logging configuration can be set up."""
        from services._template.log_config import configure_logging

        # Should not raise any exceptions
        configure_logging(log_level="INFO", log_format="json")
        configure_logging(log_level="DEBUG", log_format="text")

    def test_structured_logging_functions(self):
        """Test that structured logging helper functions work."""
        from services._template.log_config import (
            get_logger,
            log_api_call,
            log_database_operation,
            log_processing_batch
        )

        logger = get_logger(__name__)

        # These should not raise exceptions
        log_api_call(logger, "GET", "https://example.com", status_code=200, duration_ms=150.5)
        log_database_operation(logger, "SELECT", table="users", duration_ms=25.0, rows_affected=10)
        log_processing_batch(logger, "test_batch", items_processed=100, items_failed=0, duration_ms=5000.0)


class TestHTTPClientIntegration:
    """Test HTTP client with real configuration."""

    def test_http_client_initialization(self):
        """Test that HTTP client can be initialized with real settings."""
        from services._template.client import HTTPClient
        from services._template.settings import get_settings

        settings = get_settings()

        # Should initialize without errors
        client = HTTPClient(
            max_retries=settings.api_max_retries,
            timeout=settings.api_timeout
        )

        assert client.max_retries == settings.api_max_retries
        assert client._client.timeout.read == settings.api_timeout

        client.close()

    def test_backoff_calculation(self):
        """Test that backoff calculation works correctly."""
        from services._template.client import calculate_backoff_delay

        # Test basic functionality
        delay1 = calculate_backoff_delay(0)
        delay2 = calculate_backoff_delay(1)
        delay3 = calculate_backoff_delay(2)

        # Should increase exponentially (with jitter, so approximate)
        assert delay1 < delay2 < delay3
        assert delay1 >= 0.5  # Base delay
        assert delay3 <= 5.0  # With jitter should be reasonable


class TestEndToEndWorkflow:
    """Test complete workflow without external dependencies."""

    def test_full_import_chain(self):
        """Test that all modules can be imported together without conflicts."""
        # Import in order that main.py would use them
        from services._template import __version__
        from services._template.settings import settings
        from services._template.log_config import get_logger
        from services._template.client import HTTPClient
        from services._template.main import parse_date, validate_record

        # Verify basic functionality
        assert __version__ is not None
        config = settings()
        assert config.api_key is not None

        logger = get_logger(__name__)
        assert logger is not None

        client = HTTPClient()
        client.close()

        # Test utility functions
        date_obj = parse_date("2025-01-01")
        assert date_obj.year == 2025

        valid_record = {"id": "test", "timestamp": "2025-01-01T00:00:00Z"}
        assert validate_record(valid_record) is True

    def test_service_template_as_package(self):
        """Test that the template can be imported as a package."""
        import services._template

        # Should have version
        assert hasattr(services._template, '__version__')
        assert services._template.__version__ is not None


class TestEnvironmentVariables:
    """Test environment variable handling."""

    def test_required_env_vars_present(self):
        """Test that required environment variables are present in .env."""
        env_file = PROJECT_ROOT / ".env"
        assert env_file.exists(), ".env file should exist"

        # Read .env file
        env_content = env_file.read_text()

        # Should contain API_KEY (even if empty for template)
        assert "API_KEY=" in env_content

    def test_env_example_is_template(self):
        """Test that .env.example is properly formatted as a template."""
        env_example_file = PROJECT_ROOT / ".env.example"
        assert env_example_file.exists(), ".env.example file should exist"

        content = env_example_file.read_text()

        # Should have empty values or comments for template
        lines = content.split('\n')
        api_key_lines = [line for line in lines if line.startswith('API_KEY=')]

        # Should have API_KEY declaration
        assert len(api_key_lines) > 0

        # Should be empty (template style)
        api_key_line = api_key_lines[0]
        assert api_key_line == "API_KEY=" or api_key_line.startswith("# API_KEY")


# Mark integration tests
pytestmark = pytest.mark.integration