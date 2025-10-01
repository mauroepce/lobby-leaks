"""
Tests for HTTP client with retries and backoff.
"""

import pytest
from unittest.mock import Mock, patch
import httpx

from services._template.client import (
    HTTPClient,
    RetryableHTTPError,
    calculate_backoff_delay,
    get_json,
    RETRYABLE_STATUS_CODES,
    RETRYABLE_EXCEPTIONS,
)


class TestBackoffCalculation:
    """Test exponential backoff calculation."""

    def test_basic_backoff(self):
        """Test basic exponential backoff."""
        # First attempt (attempt=0)
        delay = calculate_backoff_delay(0, base_delay=1.0)
        assert 1.0 <= delay <= 1.2  # 1.0 + jitter (0-20%)

        # Second attempt (attempt=1)
        delay = calculate_backoff_delay(1, base_delay=1.0)
        assert 2.0 <= delay <= 2.4  # 2.0 + jitter

        # Third attempt (attempt=2)
        delay = calculate_backoff_delay(2, base_delay=1.0)
        assert 4.0 <= delay <= 4.8  # 4.0 + jitter

    def test_max_delay_respected(self):
        """Test that max delay is respected."""
        delay = calculate_backoff_delay(10, base_delay=1.0, max_delay=5.0)
        assert delay <= 6.0  # max_delay + max jitter (20%)

    def test_jitter_range(self):
        """Test jitter is within expected range."""
        delays = [calculate_backoff_delay(0, base_delay=10.0) for _ in range(100)]
        min_delay = min(delays)
        max_delay = max(delays)

        # Should be between 10.0 and 12.0 (10.0 + 20% jitter)
        assert min_delay >= 10.0
        assert max_delay <= 12.0
        assert min_delay < max_delay  # Should have some variation


class TestHTTPClient:
    """Test HTTP client functionality."""

    @patch('httpx.Client')
    def test_successful_request(self, mock_client_class):
        """Test successful HTTP request."""
        # Setup mock
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Test
        with HTTPClient() as client:
            result = client.get_json("https://example.com/api")

        # Verify
        assert result == {"success": True}
        mock_client.request.assert_called_once()

    @patch('httpx.Client')
    @patch('time.sleep')  # Mock sleep to speed up tests
    def test_retry_on_server_error(self, mock_sleep, mock_client_class):
        """Test retry behavior on 5xx errors."""
        # Setup mock
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Test
        with HTTPClient(max_retries=2) as client:
            with pytest.raises(RetryableHTTPError):
                client.get_json("https://example.com/api")

        # Verify retries happened (initial + 2 retries = 3 calls)
        assert mock_client.request.call_count == 3
        assert mock_sleep.call_count == 2  # Sleep between retries

    @patch('httpx.Client')
    def test_no_retry_on_client_error(self, mock_client_class):
        """Test no retry on 4xx errors."""
        # Setup mock
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=Mock(), response=mock_response
        )
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Test
        with HTTPClient(max_retries=2) as client:
            with pytest.raises(httpx.HTTPStatusError):
                client.get_json("https://example.com/api")

        # Verify no retries (only 1 call)
        assert mock_client.request.call_count == 1

    @patch('httpx.Client')
    @patch('time.sleep')  # Mock sleep to speed up tests
    def test_retry_on_timeout(self, mock_sleep, mock_client_class):
        """Test retry behavior on timeout errors."""
        # Setup mock
        mock_client = Mock()
        mock_client.request.side_effect = httpx.ConnectTimeout("Timeout")
        mock_client_class.return_value = mock_client

        # Test
        with HTTPClient(max_retries=2) as client:
            with pytest.raises(RetryableHTTPError):
                client.get("https://example.com/api")

        # Verify retries happened
        assert mock_client.request.call_count == 3
        assert mock_sleep.call_count == 2  # Sleep between retries

    @patch('httpx.Client')
    def test_eventual_success_after_retries(self, mock_client_class):
        """Test eventual success after some failures."""
        # Setup mock to fail twice, then succeed
        mock_client = Mock()
        responses = [
            Mock(status_code=500),  # First call fails
            Mock(status_code=502),  # Second call fails
            Mock(status_code=200, json=lambda: {"success": True})  # Third succeeds
        ]
        mock_client.request.side_effect = responses
        mock_client_class.return_value = mock_client

        # Test
        with HTTPClient(max_retries=3) as client:
            result = client.get_json("https://example.com/api")

        # Verify
        assert result == {"success": True}
        assert mock_client.request.call_count == 3

    def test_retryable_status_codes(self):
        """Test that correct status codes are considered retryable."""
        client = HTTPClient()

        for code in RETRYABLE_STATUS_CODES:
            response = Mock(status_code=code)
            assert client._is_retryable_error(response=response) is True

        # Test non-retryable codes
        for code in [200, 400, 404]:
            response = Mock(status_code=code)
            assert client._is_retryable_error(response=response) is False

    def test_retryable_exceptions(self):
        """Test that correct exceptions are considered retryable."""
        client = HTTPClient()

        for exc_class in RETRYABLE_EXCEPTIONS:
            exc = exc_class("Test error")
            assert client._is_retryable_error(exception=exc) is True

        # Test non-retryable exception
        exc = ValueError("Not retryable")
        assert client._is_retryable_error(exception=exc) is False

    @patch('httpx.Client')
    def test_invalid_json_response(self, mock_client_class):
        """Test handling of invalid JSON response."""
        # Setup mock
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "Invalid JSON content"
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Test
        with HTTPClient() as client:
            with pytest.raises(ValueError, match="Invalid JSON response"):
                client.get_json("https://example.com/api")


class TestConvenienceFunction:
    """Test the convenience get_json function."""

    @patch('services._template.client.HTTPClient')
    def test_get_json_convenience(self, mock_client_class):
        """Test get_json convenience function."""
        # Setup mock
        mock_client = Mock()
        mock_client.get_json.return_value = {"data": "test"}
        mock_client_class.return_value.__enter__.return_value = mock_client

        # Test
        result = get_json("https://example.com/api", headers={"Auth": "token"})

        # Verify
        assert result == {"data": "test"}
        mock_client_class.assert_called_once()
        mock_client.get_json.assert_called_once_with(
            "https://example.com/api", headers={"Auth": "token"}, params=None
        )


class TestHTTPClientConfiguration:
    """Test HTTP client configuration options."""

    @patch('httpx.Client')
    def test_custom_timeout(self, mock_client_class):
        """Test custom timeout configuration."""
        HTTPClient(timeout=60.0)
        mock_client_class.assert_called_once_with(timeout=60.0)

    @patch('httpx.Client')
    def test_custom_retry_settings(self, mock_client_class):
        """Test custom retry configuration."""
        client = HTTPClient(max_retries=5, base_delay=1.0, max_delay=30.0)
        assert client.max_retries == 5
        assert client.base_delay == 1.0
        assert client.max_delay == 30.0

    @patch('httpx.Client')
    def test_additional_client_kwargs(self, mock_client_class):
        """Test passing additional kwargs to httpx.Client."""
        HTTPClient(
            headers={"User-Agent": "test"},
            follow_redirects=True
        )
        mock_client_class.assert_called_once_with(
            timeout=30.0,  # Default timeout
            headers={"User-Agent": "test"},
            follow_redirects=True
        )