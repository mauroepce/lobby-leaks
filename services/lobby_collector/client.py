"""
HTTP client for Ley de Lobby API.

Handles authentication, retries, rate limiting, and error handling.
"""

import asyncio
import logging
from typing import Any
from datetime import datetime

import httpx

from .settings import settings


logger = logging.getLogger(__name__)


class LobbyAPIError(Exception):
    """Base exception for Lobby API errors."""
    pass


class LobbyAPIAuthError(LobbyAPIError):
    """Authentication error (401/403)."""
    pass


class LobbyAPIRateLimitError(LobbyAPIError):
    """Rate limit exceeded (429)."""
    pass


async def fetch_page(
    endpoint: str,
    params: dict[str, Any] | None = None,
    *,
    retry_count: int = 0
) -> dict[str, Any]:
    """
    Fetch a single page from the Lobby API with authentication and retries.

    Args:
        endpoint: API endpoint path (e.g., "/audiencias")
        params: Query parameters (page, since, until, etc.)
        retry_count: Current retry attempt (internal use)

    Returns:
        JSON response from API

    Raises:
        LobbyAPIAuthError: Authentication failed
        LobbyAPIRateLimitError: Rate limit exceeded
        LobbyAPIError: Other API errors
        httpx.HTTPError: Network/connection errors

    Example:
        >>> result = await fetch_page("/audiencias", {"page": 1, "since": "2025-01-01"})
        >>> print(result["data"])
        [{"id": 123, "sujeto_pasivo": "..."}, ...]
    """
    config = settings()
    params = params or {}

    # Build full URL
    url = f"{config.lobby_api_base_url.rstrip('/')}/{endpoint.lstrip('/')}"

    # Prepare headers with authentication
    headers = {
        "Api-Key": config.lobby_api_key,
        "Accept": "application/json",
        "User-Agent": f"{config.service_name}/{config.service_name}"
    }

    # Rate limiting delay
    if retry_count > 0 or config.rate_limit_delay > 0:
        await asyncio.sleep(config.rate_limit_delay)

    logger.debug(
        f"Fetching page: url={url}, params={params}, retry={retry_count}"
    )

    try:
        async with httpx.AsyncClient(timeout=config.api_timeout) as client:
            response = await client.get(url, params=params, headers=headers)

            # Handle authentication errors
            if response.status_code in (401, 403):
                raise LobbyAPIAuthError(
                    f"Authentication failed: {response.status_code} - {response.text}"
                )

            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                raise LobbyAPIRateLimitError(
                    f"Rate limit exceeded. Retry after {retry_after} seconds"
                )

            # Raise for other errors
            response.raise_for_status()

            return await response.json()

    except (httpx.TimeoutException, httpx.NetworkError) as e:
        # Retry on network/timeout errors
        if retry_count < config.api_max_retries:
            logger.warning(
                f"Request failed, retrying: error={str(e)}, retry={retry_count + 1}/{config.api_max_retries}"
            )
            # Exponential backoff: 1s, 2s, 4s, ...
            await asyncio.sleep(2 ** retry_count)
            return await fetch_page(endpoint, params, retry_count=retry_count + 1)
        else:
            logger.error(
                f"Max retries exceeded: error={str(e)}, max_retries={config.api_max_retries}"
            )
            raise

    except httpx.HTTPStatusError as e:
        # Retry on server errors (5xx)
        if e.response.status_code >= 500 and retry_count < config.api_max_retries:
            logger.warning(
                f"Server error, retrying: status_code={e.response.status_code}, retry={retry_count + 1}"
            )
            await asyncio.sleep(2 ** retry_count)
            return await fetch_page(endpoint, params, retry_count=retry_count + 1)
        else:
            raise LobbyAPIError(f"HTTP {e.response.status_code}: {e.response.text}")


async def test_connection() -> bool:
    """
    Test connection to the Lobby API.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        # Try to fetch first page with minimal params
        result = await fetch_page("/audiencias", {"page": 1, "page_size": 1})
        logger.info(f"Connection test successful: has_data={bool(result.get('data'))}")
        return True
    except Exception as e:
        logger.error(f"Connection test failed: error={str(e)}, error_type={type(e).__name__}")
        return False
