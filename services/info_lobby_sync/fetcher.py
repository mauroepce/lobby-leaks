"""
SPARQL fetcher for InfoLobby endpoint.

Uses httpx with proper headers to bypass Fortinet WAF.
"""

import logging
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import httpx

from .settings import settings

logger = logging.getLogger(__name__)

# Directory containing SPARQL query files
QUERIES_DIR = Path(__file__).parent / "queries"

# Required headers for InfoLobby endpoint (bypasses Fortinet WAF)
INFOLOBBY_HEADERS = {
    "Accept": "application/sparql-results+json",
    "Referer": "http://datos.infolobby.cl/sparql",
    "User-Agent": "LobbyLeaks/1.0 (https://github.com/lobbyleaks)",
}


class SPARQLFetchError(Exception):
    """Raised when SPARQL fetch fails."""
    pass


class SPARQLClient:
    """
    SPARQL client for InfoLobby endpoint.

    Handles connection, retries, and query execution with proper headers.
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        default_graph: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ):
        """
        Initialize SPARQL client.

        Args:
            endpoint: SPARQL endpoint URL (default from settings)
            default_graph: Default graph URI (default from settings)
            timeout: HTTP timeout in seconds (default from settings)
            max_retries: Max retry attempts (default from settings)
        """
        config = settings()
        self.endpoint = endpoint or config.infolobby_sparql_endpoint
        self.default_graph = default_graph or config.infolobby_default_graph
        self.timeout = timeout or config.http_timeout
        self.max_retries = max_retries or config.http_max_retries

        self._client = httpx.Client(
            timeout=self.timeout,
            headers=INFOLOBBY_HEADERS,
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._client.close()

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def _build_url(self, query: str) -> str:
        """Build full URL with query parameters."""
        params = {
            "default-graph-uri": self.default_graph,
            "query": query,
            "format": "application/sparql-results+json",
            "timeout": "0",
            "debug": "on",
        }
        query_string = urllib.parse.urlencode(params)
        return f"{self.endpoint}?{query_string}"

    def execute(self, query: str) -> Dict[str, Any]:
        """
        Execute a SPARQL query and return JSON results.

        Args:
            query: SPARQL query string

        Returns:
            JSON response as dictionary

        Raises:
            SPARQLFetchError: When query execution fails after retries
        """
        url = self._build_url(query)
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(
                    f"Executing SPARQL query (attempt {attempt + 1}/{self.max_retries + 1})"
                )

                response = self._client.get(url)

                if response.status_code == 200:
                    return response.json()

                # Handle specific error codes
                if response.status_code == 403:
                    raise SPARQLFetchError(
                        f"Access denied (403). Check Referer header. Response: {response.text[:200]}"
                    )

                if response.status_code >= 500:
                    last_error = f"Server error {response.status_code}: {response.text[:200]}"
                    logger.warning(f"SPARQL server error, retrying: {last_error}")
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue

                # Non-retryable error
                raise SPARQLFetchError(
                    f"SPARQL query failed with status {response.status_code}: {response.text[:500]}"
                )

            except httpx.TimeoutException as e:
                last_error = f"Timeout: {e}"
                logger.warning(f"SPARQL timeout, retrying: {last_error}")
                time.sleep(2 ** attempt)
                continue

            except httpx.RequestError as e:
                last_error = f"Request error: {e}"
                logger.warning(f"SPARQL request error, retrying: {last_error}")
                time.sleep(2 ** attempt)
                continue

        raise SPARQLFetchError(f"Max retries exceeded. Last error: {last_error}")


def load_query(name: str) -> str:
    """
    Load a SPARQL query from file.

    Args:
        name: Query name (without .sparql extension)

    Returns:
        Query string with {limit} and {offset} placeholders

    Raises:
        FileNotFoundError: If query file doesn't exist
    """
    query_file = QUERIES_DIR / f"{name}.sparql"
    if not query_file.exists():
        raise FileNotFoundError(f"Query file not found: {query_file}")

    return query_file.read_text()


def fetch_audiencias(
    client: Optional[SPARQLClient] = None,
    limit: int = 1000,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    Fetch audiencias from InfoLobby.

    Args:
        client: SPARQL client (creates new if None)
        limit: Max records per query
        offset: Starting offset

    Returns:
        List of audiencia records as dictionaries
    """
    query_template = load_query("audiencias")
    query = query_template.format(limit=limit, offset=offset)

    close_client = False
    if client is None:
        client = SPARQLClient()
        close_client = True

    try:
        result = client.execute(query)
        return _extract_bindings(result)
    finally:
        if close_client:
            client.close()


def fetch_viajes(
    client: Optional[SPARQLClient] = None,
    limit: int = 1000,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    Fetch viajes from InfoLobby.

    Args:
        client: SPARQL client (creates new if None)
        limit: Max records per query
        offset: Starting offset

    Returns:
        List of viaje records as dictionaries
    """
    query_template = load_query("viajes")
    query = query_template.format(limit=limit, offset=offset)

    close_client = False
    if client is None:
        client = SPARQLClient()
        close_client = True

    try:
        result = client.execute(query)
        return _extract_bindings(result)
    finally:
        if close_client:
            client.close()


def fetch_donativos(
    client: Optional[SPARQLClient] = None,
    limit: int = 1000,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    Fetch donativos from InfoLobby.

    Args:
        client: SPARQL client (creates new if None)
        limit: Max records per query
        offset: Starting offset

    Returns:
        List of donativo records as dictionaries
    """
    query_template = load_query("donativos")
    query = query_template.format(limit=limit, offset=offset)

    close_client = False
    if client is None:
        client = SPARQLClient()
        close_client = True

    try:
        result = client.execute(query)
        return _extract_bindings(result)
    finally:
        if close_client:
            client.close()


def fetch_all(
    kind: str,
    batch_size: int = 1000,
    max_records: Optional[int] = None,
) -> Iterator[Dict[str, Any]]:
    """
    Fetch all records of a given type, handling pagination.

    Args:
        kind: Record type ('audiencias', 'viajes', 'donativos')
        batch_size: Records per batch
        max_records: Maximum total records (None = unlimited)

    Yields:
        Individual records as dictionaries
    """
    fetch_fn = {
        "audiencias": fetch_audiencias,
        "viajes": fetch_viajes,
        "donativos": fetch_donativos,
    }.get(kind)

    if fetch_fn is None:
        raise ValueError(f"Unknown kind: {kind}. Must be one of: audiencias, viajes, donativos")

    offset = 0
    total_fetched = 0

    with SPARQLClient() as client:
        while True:
            logger.info(f"Fetching {kind} batch: offset={offset}, limit={batch_size}")

            records = fetch_fn(client=client, limit=batch_size, offset=offset)

            if not records:
                logger.info(f"No more {kind} records at offset {offset}")
                break

            for record in records:
                yield record
                total_fetched += 1

                if max_records and total_fetched >= max_records:
                    logger.info(f"Reached max_records limit: {max_records}")
                    return

            if len(records) < batch_size:
                logger.info(f"Last batch for {kind}: got {len(records)} < {batch_size}")
                break

            offset += batch_size

    logger.info(f"Finished fetching {kind}: total={total_fetched}")


def _extract_bindings(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract bindings from SPARQL JSON result.

    Converts from SPARQL result format:
        {"s": {"type": "uri", "value": "..."}, "p": {"type": "literal", "value": "..."}}

    To simple dict:
        {"s": "...", "p": "..."}
    """
    bindings = result.get("results", {}).get("bindings", [])

    records = []
    for binding in bindings:
        record = {}
        for key, val in binding.items():
            record[key] = val.get("value")
        records.append(record)

    return records
