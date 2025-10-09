"""
Tests for temporal window calculation.

Tests date range calculations for incremental updates.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from services.lobby_collector.ingest import resolve_window
from services.lobby_collector.settings import LobbyCollectorSettings


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

    with patch("services.lobby_collector.ingest.settings", return_value=mock_config):
        yield mock_config


class TestResolveWindow:
    """Test temporal window resolution."""

    def test_default_window(self):
        """Test window calculation with default days (from settings)."""
        now = datetime(2025, 10, 8, 12, 0, 0)

        # With default_since_days=7 from settings
        since, until = resolve_window(now=now)

        assert until == now
        assert since == now - timedelta(days=7)
        assert (until - since).days == 7

    def test_custom_days(self):
        """Test window calculation with custom number of days."""
        now = datetime(2025, 10, 8, 12, 0, 0)

        since, until = resolve_window(now=now, days=3)

        assert until == now
        assert since == now - timedelta(days=3)
        assert (until - since).days == 3

    def test_single_day_window(self):
        """Test window for a single day."""
        now = datetime(2025, 10, 8, 12, 0, 0)

        since, until = resolve_window(now=now, days=1)

        assert until == now
        assert since == now - timedelta(days=1)
        assert (until - since).days == 1

    def test_thirty_day_window(self):
        """Test window for 30 days (typical month)."""
        now = datetime(2025, 10, 8, 12, 0, 0)

        since, until = resolve_window(now=now, days=30)

        assert until == now
        assert since == now - timedelta(days=30)
        assert (until - since).days == 30

    def test_window_preserves_time(self):
        """Test that time component is preserved in window calculation."""
        now = datetime(2025, 10, 8, 14, 30, 45)

        since, until = resolve_window(now=now, days=7)

        assert until.hour == 14
        assert until.minute == 30
        assert until.second == 45

        assert since.hour == 14
        assert since.minute == 30
        assert since.second == 45

    def test_window_across_month_boundary(self):
        """Test window that crosses month boundaries."""
        now = datetime(2025, 10, 5, 12, 0, 0)  # October 5

        since, until = resolve_window(now=now, days=10)

        # Should go back to September 25
        assert until == datetime(2025, 10, 5, 12, 0, 0)
        assert since == datetime(2025, 9, 25, 12, 0, 0)

    def test_window_across_year_boundary(self):
        """Test window that crosses year boundaries."""
        now = datetime(2025, 1, 5, 12, 0, 0)  # January 5, 2025

        since, until = resolve_window(now=now, days=10)

        # Should go back to December 26, 2024
        assert until == datetime(2025, 1, 5, 12, 0, 0)
        assert since == datetime(2024, 12, 26, 12, 0, 0)

    def test_zero_days_window(self):
        """Test window with zero days (edge case)."""
        now = datetime(2025, 10, 8, 12, 0, 0)

        # Even with 0 days, since and until should be different
        # This is handled by the implementation
        # (in practice, settings validation ensures days >= 1)
        since, until = resolve_window(now=now, days=0)

        assert until == now
        assert since == now

    def test_window_consistency(self):
        """Test that multiple calls with same params return same window."""
        now = datetime(2025, 10, 8, 12, 0, 0)

        since1, until1 = resolve_window(now=now, days=7)
        since2, until2 = resolve_window(now=now, days=7)

        assert since1 == since2
        assert until1 == until2


class TestWindowFormatting:
    """Test that windows produce correctly formatted date strings."""

    def test_window_iso_format(self):
        """Test that window dates can be formatted as ISO strings."""
        now = datetime(2025, 10, 8, 12, 0, 0)

        since, until = resolve_window(now=now, days=7)

        # Should be able to format as ISO strings for API
        since_str = since.strftime("%Y-%m-%d")
        until_str = until.strftime("%Y-%m-%d")

        assert since_str == "2025-10-01"
        assert until_str == "2025-10-08"

    def test_window_with_timezone_awareness(self):
        """Test window calculation with timezone-aware datetimes."""
        from datetime import timezone

        now = datetime(2025, 10, 8, 12, 0, 0, tzinfo=timezone.utc)

        since, until = resolve_window(now=now, days=7)

        # Should preserve timezone info
        assert until.tzinfo == timezone.utc
        assert since.tzinfo == timezone.utc

        # Should still be 7 days apart
        assert (until - since).days == 7


class TestEdgeCases:
    """Test edge cases for window calculation."""

    def test_leap_year_february(self):
        """Test window calculation during leap year February."""
        # 2024 is a leap year
        now = datetime(2024, 3, 1, 12, 0, 0)

        since, until = resolve_window(now=now, days=30)

        # Should handle February 29 correctly
        assert until == datetime(2024, 3, 1, 12, 0, 0)
        assert since == datetime(2024, 1, 31, 12, 0, 0)

    def test_daylight_saving_time_transition(self):
        """Test window calculation across DST transitions."""
        # This tests that timedelta works correctly even across DST
        # (Python's datetime handles this automatically)
        now = datetime(2025, 11, 5, 12, 0, 0)  # After DST ends in USA

        since, until = resolve_window(now=now, days=30)

        # Should still be 30 days
        assert (until - since).days == 30

    def test_very_large_window(self):
        """Test window calculation with very large number of days."""
        now = datetime(2025, 10, 8, 12, 0, 0)

        # 365 days (1 year)
        since, until = resolve_window(now=now, days=365)

        assert until == now
        assert since == datetime(2024, 10, 8, 12, 0, 0)  # exactly 365 days ago
        assert (until - since).days == 365
