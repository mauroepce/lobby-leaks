"""Tests for SERVEL fetcher module."""

import pytest
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO

import pandas as pd

from ..fetcher import (
    fetch,
    fetch_from_file,
    fetch_from_url,
    FetchError,
    UnsupportedFormatError,
    _detect_format,
    _read_csv,
    _read_excel,
)


class TestDetectFormat:
    """Tests for format detection."""

    def test_detect_csv(self):
        assert _detect_format("data/donations.csv") == "csv"
        assert _detect_format("path/to/FILE.CSV") == "csv"

    def test_detect_xlsx(self):
        assert _detect_format("data/donations.xlsx") == "xlsx"
        assert _detect_format("data/donations.xls") == "xlsx"

    def test_detect_from_url(self):
        assert _detect_format("https://example.com/data.csv") == "csv"
        assert _detect_format("https://example.com/path/file.xlsx") == "xlsx"

    def test_unsupported_format(self):
        with pytest.raises(UnsupportedFormatError):
            _detect_format("data/file.json")

        with pytest.raises(UnsupportedFormatError):
            _detect_format("data/file.txt")


class TestReadCsv:
    """Tests for CSV reading."""

    def test_read_utf8_csv(self):
        """Should read UTF-8 CSV correctly."""
        csv_content = "nombre,monto\nJuan Pérez,1000\nMaría García,2000"

        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(csv_content)
            f.flush()

            df = _read_csv(f.name)

            assert len(df) == 2
            assert df.iloc[0]["nombre"] == "Juan Pérez"
            assert df.iloc[1]["monto"] == "2000"

    def test_read_latin1_csv(self):
        """Should handle Latin-1 encoding."""
        csv_content = "nombre,monto\nJuan Pérez,1000"

        with NamedTemporaryFile(mode="wb", suffix=".csv", delete=False) as f:
            f.write(csv_content.encode("latin-1"))
            f.flush()

            # Should try UTF-8 first, fail, then try Latin-1
            df = _read_csv(f.name, encoding="utf-8")

            assert len(df) == 1
            assert "Juan" in df.iloc[0]["nombre"]

    def test_read_csv_from_bytesio(self):
        """Should read from BytesIO."""
        csv_content = b"col1,col2\nval1,val2"
        buffer = BytesIO(csv_content)

        df = _read_csv(buffer)

        assert len(df) == 1
        assert df.iloc[0]["col1"] == "val1"


class TestFetchFromFile:
    """Tests for fetch_from_file function."""

    def test_fetch_csv_file(self):
        """Should fetch records from CSV file."""
        csv_content = "NOMBRE_DONANTE,MONTO,AÑO\nJuan,1000,2021\nMaría,2000,2021"

        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(csv_content)
            f.flush()

            records = fetch_from_file(f.name)

            assert len(records) == 2
            assert records[0]["NOMBRE_DONANTE"] == "Juan"
            assert records[0]["MONTO"] == "1000"
            assert records[1]["NOMBRE_DONANTE"] == "María"

    def test_fetch_xlsx_file(self):
        """Should fetch records from Excel file."""
        df = pd.DataFrame({
            "NOMBRE_DONANTE": ["Juan", "María"],
            "MONTO": ["1000", "2000"],
        })

        with NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            df.to_excel(f.name, index=False)

            records = fetch_from_file(f.name)

            assert len(records) == 2
            assert records[0]["NOMBRE_DONANTE"] == "Juan"

    def test_fetch_nonexistent_file(self):
        """Should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            fetch_from_file("/nonexistent/path/file.csv")

    def test_fetch_unsupported_format(self):
        """Should raise UnsupportedFormatError."""
        with NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(b'{}')
            f.flush()

            with pytest.raises(UnsupportedFormatError):
                fetch_from_file(f.name)

    def test_fetch_handles_none_values(self):
        """Should convert NaN to None."""
        csv_content = "col1,col2\nval1,\n,val2"

        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            f.flush()

            records = fetch_from_file(f.name)

            assert len(records) == 2
            assert records[0]["col2"] is None
            assert records[1]["col1"] is None


class TestFetchFromUrl:
    """Tests for fetch_from_url function."""

    def test_fetch_csv_from_url(self):
        """Should fetch CSV from URL."""
        csv_content = b"col1,col2\nval1,val2"

        mock_response = MagicMock()
        mock_response.content = csv_content
        mock_response.raise_for_status = Mock()

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response

            records = fetch_from_url("https://example.com/data.csv")

            assert len(records) == 1
            assert records[0]["col1"] == "val1"

    def test_fetch_xlsx_from_url(self):
        """Should fetch Excel from URL."""
        df = pd.DataFrame({"col1": ["val1"], "col2": ["val2"]})
        buffer = BytesIO()
        df.to_excel(buffer, index=False)
        xlsx_content = buffer.getvalue()

        mock_response = MagicMock()
        mock_response.content = xlsx_content
        mock_response.raise_for_status = Mock()

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response

            records = fetch_from_url("https://example.com/data.xlsx")

            assert len(records) == 1
            assert records[0]["col1"] == "val1"

    def test_fetch_retries_on_error(self):
        """Should retry on HTTP errors."""
        import httpx

        csv_content = b"col1\nval1"

        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 500
        mock_response_fail.text = "Server Error"
        mock_response_fail.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response_fail
        )

        mock_response_ok = MagicMock()
        mock_response_ok.content = csv_content
        mock_response_ok.raise_for_status = Mock()

        call_count = [0]
        def mock_get(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                return mock_response_fail
            return mock_response_ok

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.side_effect = mock_get

            records = fetch_from_url("https://example.com/data.csv", max_retries=3)

            assert len(records) == 1
            assert call_count[0] == 3

    def test_fetch_fails_after_retries(self):
        """Should raise error after all retries exhausted."""
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server Error"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response
        )

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response

            with pytest.raises(FetchError) as exc_info:
                fetch_from_url("https://example.com/data.csv", max_retries=2)

            assert "500" in str(exc_info.value)


class TestFetchAutoDetect:
    """Tests for fetch function (auto-detect source type)."""

    def test_fetch_detects_file(self):
        """Should detect local file path."""
        csv_content = "col1\nval1"

        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            f.flush()

            records = fetch(f.name)

            assert len(records) == 1

    def test_fetch_detects_url(self):
        """Should detect URL."""
        csv_content = b"col1\nval1"

        mock_response = MagicMock()
        mock_response.content = csv_content
        mock_response.raise_for_status = Mock()

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response

            records = fetch("https://example.com/data.csv")

            assert len(records) == 1

    def test_fetch_detects_http(self):
        """Should detect http:// URL."""
        csv_content = b"col1\nval1"

        mock_response = MagicMock()
        mock_response.content = csv_content
        mock_response.raise_for_status = Mock()

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response

            records = fetch("http://example.com/data.csv")

            assert len(records) == 1
