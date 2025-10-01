"""
Tests for main CLI module.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import date
import asyncio

from services._template.main import (
    parse_date,
    ingest_since,
    create_parser,
    main,
    validate_record,
    process_records,
)


class TestDateParsing:
    """Test date parsing functionality."""

    def test_valid_date_parsing(self):
        """Test parsing valid date strings."""
        result = parse_date("2025-01-01")
        assert result == date(2025, 1, 1)

        result = parse_date("2024-12-31")
        assert result == date(2024, 12, 31)

    def test_invalid_date_format(self):
        """Test handling of invalid date formats."""
        with pytest.raises(ValueError, match="Invalid date format"):
            parse_date("01-01-2025")

        with pytest.raises(ValueError, match="Invalid date format"):
            parse_date("2025/01/01")

        with pytest.raises(ValueError, match="Invalid date format"):
            parse_date("invalid-date")

    def test_invalid_date_values(self):
        """Test handling of invalid date values."""
        with pytest.raises(ValueError, match="Invalid date format"):
            parse_date("2025-13-01")  # Invalid month

        with pytest.raises(ValueError, match="Invalid date format"):
            parse_date("2025-01-32")  # Invalid day


class TestRecordValidation:
    """Test record validation functionality."""

    def test_valid_record(self):
        """Test validation of valid records."""
        record = {"id": "123", "timestamp": "2025-01-01T00:00:00Z", "data": "test"}
        assert validate_record(record) is True

    def test_missing_required_fields(self):
        """Test validation fails for missing required fields."""
        # Missing 'id'
        record = {"timestamp": "2025-01-01T00:00:00Z"}
        assert validate_record(record) is False

        # Missing 'timestamp'
        record = {"id": "123"}
        assert validate_record(record) is False

        # Missing both
        record = {"data": "test"}
        assert validate_record(record) is False

    def test_empty_record(self):
        """Test validation fails for empty record."""
        assert validate_record({}) is False


class TestRecordProcessing:
    """Test record processing functionality."""

    def test_process_valid_records(self):
        """Test processing of valid records."""
        records = [
            {"id": "1", "timestamp": "2025-01-01T00:00:00Z"},
            {"id": "2", "timestamp": "2025-01-01T01:00:00Z"},
            {"id": "3", "timestamp": "2025-01-01T02:00:00Z"},
        ]

        processed, failed = process_records(records)
        assert processed == 3
        assert failed == 0

    def test_process_invalid_records(self):
        """Test processing of invalid records."""
        records = [
            {"id": "1"},  # Missing timestamp
            {"timestamp": "2025-01-01T00:00:00Z"},  # Missing id
            {},  # Empty record
        ]

        processed, failed = process_records(records)
        assert processed == 0
        assert failed == 3

    def test_process_mixed_records(self):
        """Test processing of mixed valid/invalid records."""
        records = [
            {"id": "1", "timestamp": "2025-01-01T00:00:00Z"},  # Valid
            {"id": "2"},  # Invalid - missing timestamp
            {"id": "3", "timestamp": "2025-01-01T02:00:00Z"},  # Valid
        ]

        processed, failed = process_records(records)
        assert processed == 2
        assert failed == 1

    def test_process_empty_list(self):
        """Test processing of empty record list."""
        processed, failed = process_records([])
        assert processed == 0
        assert failed == 0


class TestCLIParser:
    """Test command line argument parsing."""

    def test_parser_required_arguments(self):
        """Test parser with required arguments."""
        parser = create_parser()

        # Valid arguments
        args = parser.parse_args(["--since", "2025-01-01"])
        assert args.since == "2025-01-01"

        # Missing required argument should raise SystemExit
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_parser_optional_arguments(self):
        """Test parser with optional arguments."""
        parser = create_parser()

        args = parser.parse_args([
            "--since", "2025-01-01",
            "--log-level", "DEBUG",
            "--log-format", "text"
        ])

        assert args.since == "2025-01-01"
        assert args.log_level == "DEBUG"
        assert args.log_format == "text"

    def test_parser_invalid_log_level(self):
        """Test parser with invalid log level."""
        parser = create_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(["--since", "2025-01-01", "--log-level", "INVALID"])

    def test_parser_version(self):
        """Test version argument."""
        parser = create_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(["--version"])


class TestMainIngestion:
    """Test main ingestion functionality."""

    @patch('services._template.main.fetch_data_since')
    @patch('services._template.main.process_records')
    async def test_successful_ingestion(self, mock_process, mock_fetch):
        """Test successful data ingestion."""
        # Setup mocks
        mock_fetch.return_value = {
            "records": [
                {"id": "1", "timestamp": "2025-01-01T00:00:00Z"},
                {"id": "2", "timestamp": "2025-01-01T01:00:00Z"}
            ]
        }
        mock_process.return_value = (2, 0)  # 2 processed, 0 failed

        # Test
        result = await ingest_since("2025-01-01")

        # Verify
        assert result is True
        mock_fetch.assert_called_once()
        mock_process.assert_called_once()

    @patch('services._template.main.fetch_data_since')
    async def test_ingestion_no_records(self, mock_fetch):
        """Test ingestion when no records are found."""
        # Setup mock
        mock_fetch.return_value = {"records": []}

        # Test
        result = await ingest_since("2025-01-01")

        # Verify
        assert result is True
        mock_fetch.assert_called_once()

    @patch('services._template.main.fetch_data_since')
    @patch('services._template.main.process_records')
    async def test_ingestion_with_failures(self, mock_process, mock_fetch):
        """Test ingestion with processing failures."""
        # Setup mocks
        mock_fetch.return_value = {
            "records": [
                {"id": "1", "timestamp": "2025-01-01T00:00:00Z"},
                {"id": "2"},  # Invalid record
            ]
        }
        mock_process.return_value = (1, 1)  # 1 processed, 1 failed

        # Test
        result = await ingest_since("2025-01-01")

        # Verify
        assert result is False  # Should return False due to failures
        mock_fetch.assert_called_once()
        mock_process.assert_called_once()

    @patch('services._template.main.fetch_data_since')
    async def test_ingestion_fetch_error(self, mock_fetch):
        """Test ingestion when data fetching fails."""
        # Setup mock to raise exception
        mock_fetch.side_effect = Exception("API Error")

        # Test
        result = await ingest_since("2025-01-01")

        # Verify
        assert result is False
        mock_fetch.assert_called_once()

    async def test_invalid_date_format(self):
        """Test ingestion with invalid date format."""
        result = await ingest_since("invalid-date")
        assert result is False


class TestMainFunction:
    """Test main CLI entry point."""

    @patch('services._template.main.ingest_since')
    @patch('sys.argv', ['main.py', '--since', '2025-01-01'])
    async def test_main_success(self, mock_ingest):
        """Test successful main execution."""
        mock_ingest.return_value = True

        result = await main()

        assert result == 0
        mock_ingest.assert_called_once_with("2025-01-01")

    @patch('services._template.main.ingest_since')
    @patch('sys.argv', ['main.py', '--since', '2025-01-01'])
    async def test_main_failure(self, mock_ingest):
        """Test main execution with ingestion failure."""
        mock_ingest.return_value = False

        result = await main()

        assert result == 1
        mock_ingest.assert_called_once_with("2025-01-01")

    @patch('services._template.main.ingest_since')
    @patch('sys.argv', ['main.py', '--since', '2025-01-01'])
    async def test_main_exception(self, mock_ingest):
        """Test main execution with unexpected exception."""
        mock_ingest.side_effect = Exception("Unexpected error")

        result = await main()

        assert result == 1
        mock_ingest.assert_called_once_with("2025-01-01")

    @patch('services._template.main.ingest_since')
    @patch('sys.argv', ['main.py', '--since', '2025-01-01'])
    async def test_main_keyboard_interrupt(self, mock_ingest):
        """Test main execution with keyboard interrupt."""
        mock_ingest.side_effect = KeyboardInterrupt()

        result = await main()

        assert result == 1
        mock_ingest.assert_called_once_with("2025-01-01")


class TestIntegration:
    """Integration tests combining multiple components."""

    @patch('services._template.client.HTTPClient')
    @patch('services._template.main.settings')
    async def test_end_to_end_success(self, mock_settings, mock_client_class):
        """Test end-to-end successful ingestion."""
        # Setup settings mock
        mock_config = Mock()
        mock_config.api_base_url = "https://api.example.com"
        mock_config.api_max_retries = 3
        mock_config.api_timeout = 30.0
        mock_config.get_api_headers.return_value = {"Authorization": "Bearer token"}
        mock_settings.return_value = mock_config

        # Setup HTTP client mock
        mock_client = Mock()
        mock_client.get_json.return_value = {
            "records": [
                {"id": "1", "timestamp": "2025-01-01T00:00:00Z"},
                {"id": "2", "timestamp": "2025-01-01T01:00:00Z"}
            ]
        }
        mock_client_class.return_value.__enter__.return_value = mock_client

        # Test
        result = await ingest_since("2025-01-01")

        # Verify
        assert result is True
        mock_client.get_json.assert_called_once()

    @patch('services._template.client.HTTPClient')
    @patch('services._template.main.settings')
    async def test_end_to_end_http_error(self, mock_settings, mock_client_class):
        """Test end-to-end with HTTP error."""
        # Setup settings mock
        mock_config = Mock()
        mock_config.api_base_url = "https://api.example.com"
        mock_config.api_max_retries = 3
        mock_config.api_timeout = 30.0
        mock_config.get_api_headers.return_value = {"Authorization": "Bearer token"}
        mock_settings.return_value = mock_config

        # Setup HTTP client mock to raise exception
        mock_client = Mock()
        mock_client.get_json.side_effect = Exception("HTTP Error")
        mock_client_class.return_value.__enter__.return_value = mock_client

        # Test
        result = await ingest_since("2025-01-01")

        # Verify
        assert result is False
        mock_client.get_json.assert_called_once()