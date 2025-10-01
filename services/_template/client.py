"""
HTTPX client with retries and exponential backoff + jitter.

Handles transient errors (5xx, timeouts) with configurable retry strategy.
"""

import asyncio
import random
import time
from typing import Any, Dict, Optional

import httpx
import structlog

logger = structlog.get_logger(__name__)

# Retryable status codes (5xx server errors)
RETRYABLE_STATUS_CODES = {500, 502, 503, 504}

# Retryable exceptions (connection and timeout errors)
RETRYABLE_EXCEPTIONS = (
    httpx.ConnectTimeout,
    httpx.ConnectError,
    httpx.ReadTimeout,
)


class RetryableHTTPError(Exception):
    """Raised when max retries are exceeded."""
    pass


def calculate_backoff_delay(attempt: int, base_delay: float = 0.5, max_delay: float = 60.0) -> float:
    """
    Calculate exponential backoff delay with jitter.

    Args:
        attempt: Current retry attempt (0-based)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds

    Returns:
        Delay in seconds with jitter applied
    """
    # Exponential backoff: base_delay * (2 ^ attempt)
    delay = base_delay * (2 ** attempt)
    delay = min(delay, max_delay)

    # Add jitter (0-20% of delay)
    jitter = random.uniform(0, 0.2 * delay)
    return delay + jitter


class HTTPClient:
    """
    HTTP client with automatic retries and exponential backoff.

    Features:
    - Retries on 5xx status codes and connection/timeout errors
    - Exponential backoff with jitter
    - Structured logging of retry attempts
    - Configurable timeouts and retry limits
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 60.0,
        timeout: float = 30.0,
        **client_kwargs
    ):
        """
        Initialize HTTP client.

        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay for exponential backoff (seconds)
            max_delay: Maximum delay between retries (seconds)
            timeout: Request timeout in seconds
            **client_kwargs: Additional arguments for httpx.Client
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

        # Set up httpx client with timeout
        client_kwargs.setdefault("timeout", timeout)
        self._client = httpx.Client(**client_kwargs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._client.close()

    def close(self):
        """Close the underlying HTTP client."""
        self._client.close()

    def _is_retryable_error(self, response: Optional[httpx.Response] = None,
                           exception: Optional[Exception] = None) -> bool:
        """Check if an error is retryable."""
        if exception:
            return isinstance(exception, RETRYABLE_EXCEPTIONS)

        if response:
            return response.status_code in RETRYABLE_STATUS_CODES

        return False

    def _make_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Make HTTP request with retry logic."""
        last_exception = None
        last_response = None

        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(
                    "Making HTTP request",
                    method=method,
                    url=url,
                    attempt=attempt + 1,
                    max_attempts=self.max_retries + 1
                )

                response = self._client.request(method, url, **kwargs)

                # Check if we should retry based on status code
                if self._is_retryable_error(response=response):
                    last_response = response

                    if attempt < self.max_retries:
                        delay = calculate_backoff_delay(attempt, self.base_delay, self.max_delay)
                        logger.warning(
                            "HTTP request failed, retrying",
                            method=method,
                            url=url,
                            status_code=response.status_code,
                            attempt=attempt + 1,
                            retry_after=delay
                        )
                        time.sleep(delay)
                        continue
                    # If we reach here, we've exhausted retries for a retryable response
                    # This will be handled by the "Max retries exceeded" logic below
                    break

                # Success or non-retryable error
                if response.status_code >= 400:
                    logger.error(
                        "HTTP request failed",
                        method=method,
                        url=url,
                        status_code=response.status_code,
                        response_text=response.text[:500]
                    )

                return response

            except Exception as exc:
                last_exception = exc

                if self._is_retryable_error(exception=exc):
                    if attempt < self.max_retries:
                        delay = calculate_backoff_delay(attempt, self.base_delay, self.max_delay)
                        logger.warning(
                            "HTTP request failed with exception, retrying",
                            method=method,
                            url=url,
                            exception=str(exc),
                            attempt=attempt + 1,
                            retry_after=delay
                        )
                        time.sleep(delay)
                        continue
                    # If we reach here, we've exhausted retries for a retryable exception
                    # This will be handled by the "Max retries exceeded" logic below
                else:
                    # Non-retryable exception, re-raise immediately
                    logger.error(
                        "HTTP request failed with non-retryable exception",
                        method=method,
                        url=url,
                        exception=str(exc)
                    )
                    raise

        # Max retries exceeded
        if last_exception:
            logger.error(
                "Max retries exceeded, last exception",
                method=method,
                url=url,
                max_retries=self.max_retries,
                exception=str(last_exception)
            )
            raise RetryableHTTPError(f"Max retries exceeded: {last_exception}") from last_exception

        if last_response:
            logger.error(
                "Max retries exceeded, last response",
                method=method,
                url=url,
                max_retries=self.max_retries,
                status_code=last_response.status_code
            )
            raise RetryableHTTPError(f"Max retries exceeded: HTTP {last_response.status_code}")

        # Should never reach here
        raise RetryableHTTPError("Max retries exceeded")

    def get_json(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make GET request and return JSON response.

        Args:
            url: Request URL
            headers: Optional request headers
            params: Optional query parameters

        Returns:
            JSON response as dictionary

        Raises:
            RetryableHTTPError: When max retries are exceeded
            httpx.HTTPStatusError: For non-retryable HTTP errors
            ValueError: When response is not valid JSON
        """
        response = self._make_request("GET", url, headers=headers, params=params)

        # Raise for non-retryable HTTP errors (4xx)
        if 400 <= response.status_code < 500:
            response.raise_for_status()

        try:
            return response.json()
        except ValueError as exc:
            logger.error(
                "Failed to parse JSON response",
                url=url,
                status_code=response.status_code,
                response_text=response.text[:500]
            )
            raise ValueError(f"Invalid JSON response: {exc}") from exc

    def get(self, url: str, **kwargs) -> httpx.Response:
        """Make GET request."""
        return self._make_request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> httpx.Response:
        """Make POST request."""
        return self._make_request("POST", url, **kwargs)

    def put(self, url: str, **kwargs) -> httpx.Response:
        """Make PUT request."""
        return self._make_request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs) -> httpx.Response:
        """Make DELETE request."""
        return self._make_request("DELETE", url, **kwargs)


# Convenience function for quick JSON API calls
def get_json(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    **client_kwargs
) -> Dict[str, Any]:
    """
    Convenience function to make a GET request and return JSON.

    Args:
        url: Request URL
        headers: Optional request headers
        params: Optional query parameters
        **client_kwargs: Additional arguments for HTTPClient

    Returns:
        JSON response as dictionary
    """
    with HTTPClient(**client_kwargs) as client:
        return client.get_json(url, headers=headers, params=params)