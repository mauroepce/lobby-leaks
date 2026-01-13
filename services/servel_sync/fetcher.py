"""
Fetcher for SERVEL campaign financing datasets.

Loads data from:
- Local file paths (CSV, Excel)
- Remote URLs (with retries and timeout handling)

This module handles data acquisition only. Parsing is done in parser.py.
"""

import logging
from io import BytesIO
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from urllib.parse import urlparse

import httpx
import pandas as pd

from .settings import get_settings

logger = logging.getLogger(__name__)


class FetchError(Exception):
    """Error during data fetch operation."""
    pass


class UnsupportedFormatError(FetchError):
    """File format not supported."""
    pass


def _detect_format(path_or_url: str) -> str:
    """
    Detect file format from path or URL.

    Returns: "csv" or "xlsx"
    Raises: UnsupportedFormatError if format cannot be determined
    """
    # Extract filename from URL or path
    parsed = urlparse(path_or_url)
    if parsed.scheme in ("http", "https"):
        filename = Path(parsed.path).name
    else:
        filename = Path(path_or_url).name

    lower_name = filename.lower()

    if lower_name.endswith(".csv"):
        return "csv"
    elif lower_name.endswith(".xlsx") or lower_name.endswith(".xls"):
        return "xlsx"
    else:
        raise UnsupportedFormatError(
            f"Unsupported file format: {filename}. Expected .csv or .xlsx"
        )


def _read_csv(
    source: Union[str, BytesIO],
    encoding: str = "utf-8",
) -> pd.DataFrame:
    """
    Read CSV file into DataFrame.

    Tries multiple encodings if the primary one fails.
    """
    encodings_to_try = [encoding, "latin-1", "cp1252", "iso-8859-1"]

    for enc in encodings_to_try:
        try:
            if isinstance(source, BytesIO):
                source.seek(0)
            return pd.read_csv(source, encoding=enc, dtype=str)
        except UnicodeDecodeError:
            continue
        except Exception as e:
            # Other errors should be raised
            raise FetchError(f"Error reading CSV: {e}") from e

    raise FetchError(
        f"Could not decode CSV with any of: {encodings_to_try}"
    )


def _read_excel(source: Union[str, BytesIO]) -> pd.DataFrame:
    """Read Excel file into DataFrame."""
    try:
        return pd.read_excel(source, dtype=str)
    except Exception as e:
        raise FetchError(f"Error reading Excel file: {e}") from e


def fetch_from_file(
    file_path: str,
    encoding: str = "utf-8",
) -> List[Dict[str, Any]]:
    """
    Fetch SERVEL data from a local file.

    Args:
        file_path: Path to CSV or Excel file
        encoding: Character encoding for CSV files (default UTF-8)

    Returns:
        List of dictionaries, one per row

    Raises:
        FetchError: If file cannot be read
        UnsupportedFormatError: If file format is not supported
        FileNotFoundError: If file does not exist

    Example:
        >>> records = fetch_from_file("data/servel/donations_2021.csv")
        >>> print(f"Loaded {len(records)} records")
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    file_format = _detect_format(file_path)
    logger.info(f"Loading {file_format.upper()} file: {file_path}")

    if file_format == "csv":
        df = _read_csv(str(path), encoding=encoding)
    else:
        df = _read_excel(str(path))

    # Convert to list of dicts, replacing NaN with None
    records = df.where(pd.notna(df), None).to_dict(orient="records")

    logger.info(f"Loaded {len(records)} records from {file_path}")
    return records


def fetch_from_url(
    url: str,
    timeout: Optional[float] = None,
    max_retries: Optional[int] = None,
    encoding: str = "utf-8",
) -> List[Dict[str, Any]]:
    """
    Fetch SERVEL data from a remote URL.

    Args:
        url: URL to CSV or Excel file
        timeout: Request timeout in seconds (default from settings)
        max_retries: Maximum retry attempts (default from settings)
        encoding: Character encoding for CSV files

    Returns:
        List of dictionaries, one per row

    Raises:
        FetchError: If download fails or file cannot be read
        UnsupportedFormatError: If file format is not supported

    Example:
        >>> records = fetch_from_url(
        ...     "https://example.com/servel/donations.csv"
        ... )
        >>> print(f"Downloaded {len(records)} records")
    """
    settings = get_settings()
    timeout = timeout or settings.http_timeout
    max_retries = max_retries if max_retries is not None else settings.http_max_retries

    file_format = _detect_format(url)
    logger.info(f"Downloading {file_format.upper()} from: {url}")

    # Download with retries
    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.get(url)
                response.raise_for_status()

                content = BytesIO(response.content)

                if file_format == "csv":
                    df = _read_csv(content, encoding=encoding)
                else:
                    df = _read_excel(content)

                records = df.where(pd.notna(df), None).to_dict(orient="records")

                logger.info(f"Downloaded {len(records)} records from {url}")
                return records

        except httpx.HTTPStatusError as e:
            last_error = FetchError(
                f"HTTP error {e.response.status_code}: {e.response.text}"
            )
            logger.warning(
                f"HTTP error on attempt {attempt + 1}/{max_retries + 1}: {e}"
            )
        except httpx.RequestError as e:
            last_error = FetchError(f"Request error: {e}")
            logger.warning(
                f"Request error on attempt {attempt + 1}/{max_retries + 1}: {e}"
            )
        except FetchError:
            raise
        except Exception as e:
            last_error = FetchError(f"Unexpected error: {e}")
            logger.warning(
                f"Unexpected error on attempt {attempt + 1}/{max_retries + 1}: {e}"
            )

    raise last_error or FetchError("Download failed after all retries")


def fetch(
    source: str,
    encoding: str = "utf-8",
    timeout: Optional[float] = None,
    max_retries: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch SERVEL data from file path or URL (auto-detect).

    Args:
        source: File path or URL to CSV/Excel file
        encoding: Character encoding for CSV files
        timeout: Request timeout for URLs (seconds)
        max_retries: Maximum retry attempts for URLs

    Returns:
        List of dictionaries, one per row

    Example:
        >>> # From local file
        >>> records = fetch("data/servel/donations.csv")
        >>>
        >>> # From URL
        >>> records = fetch("https://example.com/donations.xlsx")
    """
    parsed = urlparse(source)

    if parsed.scheme in ("http", "https"):
        return fetch_from_url(
            source,
            timeout=timeout,
            max_retries=max_retries,
            encoding=encoding,
        )
    else:
        return fetch_from_file(source, encoding=encoding)
