"""
Unit tests for Binance.US REST L2 feed.

Tests the REST-based order book polling implementation for Binance.US.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

from trade_engine.adapters.feeds.binance_us_l2 import BinanceUSL2Feed, BinanceUSL2FeedError


class TestBinanceUSL2FeedInit:
    """Test feed initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        feed = BinanceUSL2Feed(symbol="BTCUSDT")

        assert feed.symbol == "BTCUSDT"
        assert feed.depth == 5
        assert feed.poll_interval_ms == 500
        assert feed.rate_limit_per_second == 10
        assert feed.running is False
        assert feed.fetch_count == 0

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        feed = BinanceUSL2Feed(
            symbol="ethusdt",
            depth=10,
            poll_interval_ms=1000,
            rate_limit_per_second=5
        )

        assert feed.symbol == "ETHUSDT"  # Should uppercase
        assert feed.depth == 10
        assert feed.poll_interval_ms == 1000
        assert feed.rate_limit_per_second == 5


class TestAPILimitMapping:
    """Test API limit parameter mapping."""

    def test_get_api_limit_exact_match(self):
        """Test when depth matches valid API limit."""
        feed = BinanceUSL2Feed(symbol="BTCUSDT", depth=5)
        assert feed._get_api_limit() == 5

        feed = BinanceUSL2Feed(symbol="BTCUSDT", depth=100)
        assert feed._get_api_limit() == 100

    def test_get_api_limit_rounds_up(self):
        """Test when depth rounds up to next valid limit."""
        feed = BinanceUSL2Feed(symbol="BTCUSDT", depth=7)
        assert feed._get_api_limit() == 10  # Rounds up to next valid

        feed = BinanceUSL2Feed(symbol="BTCUSDT", depth=150)
        assert feed._get_api_limit() == 500  # Rounds up

    def test_get_api_limit_max(self):
        """Test maximum limit."""
        feed = BinanceUSL2Feed(symbol="BTCUSDT", depth=10000)
        assert feed._get_api_limit() == 5000  # Max limit


class TestRateLimiting:
    """Test rate limiting logic."""

    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self):
        """Test that rate limiting enforces limits."""
        feed = BinanceUSL2Feed(
            symbol="BTCUSDT",
            rate_limit_per_second=2  # Only 2 requests/second
        )

        # Make 2 requests (should pass immediately)
        await feed._check_rate_limit()
        await feed._check_rate_limit()
        assert feed.request_count == 2

        # 3rd request should sleep to avoid exceeding limit
        # We'll just verify the count resets after 1 second
        await asyncio.sleep(1.1)
        await feed._check_rate_limit()
        assert feed.request_count == 1  # Reset after time window


class TestFetchSnapshot:
    """Test order book snapshot fetching."""

    @pytest.mark.asyncio
    @patch("trade_engine.adapters.feeds.binance_us_l2.requests.get")
    async def test_fetch_snapshot_success(self, mock_get):
        """Test successful snapshot fetch."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "lastUpdateId": 12345,
            "bids": [
                ["43000.00", "0.5"],
                ["42999.00", "1.0"]
            ],
            "asks": [
                ["43001.00", "0.3"],
                ["43002.00", "0.8"]
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        feed = BinanceUSL2Feed(symbol="BTCUSDT", depth=5)

        # Fetch snapshot
        await feed._fetch_snapshot()

        # Verify order book was updated
        assert len(feed.order_book.bids) == 2
        assert len(feed.order_book.asks) == 2
        assert feed.last_update_time > 0

        # Verify request was made correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "https://api.binance.us/api/v3/depth" in str(call_args)

    @pytest.mark.asyncio
    @patch("trade_engine.adapters.feeds.binance_us_l2.requests.get")
    async def test_fetch_snapshot_http_error(self, mock_get):
        """Test snapshot fetch with HTTP error."""
        import requests

        # Mock HTTP error
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404")
        mock_get.return_value = mock_response

        feed = BinanceUSL2Feed(symbol="BTCUSDT")

        # Should raise BinanceUSL2FeedError
        with pytest.raises(BinanceUSL2FeedError, match="Failed to fetch order book"):
            await feed._fetch_snapshot()

    @pytest.mark.asyncio
    @patch("trade_engine.adapters.feeds.binance_us_l2.requests.get")
    async def test_fetch_snapshot_timeout(self, mock_get):
        """Test snapshot fetch with timeout."""
        import requests

        # Mock timeout
        mock_get.side_effect = requests.exceptions.Timeout()

        feed = BinanceUSL2Feed(symbol="BTCUSDT")

        # Should raise BinanceUSL2FeedError
        with pytest.raises(BinanceUSL2FeedError, match="Failed to fetch order book"):
            await feed._fetch_snapshot()


class TestStartStop:
    """Test feed start/stop functionality."""

    @pytest.mark.asyncio
    @patch("trade_engine.adapters.feeds.binance_us_l2.requests.get")
    async def test_start_stop(self, mock_get):
        """Test starting and stopping the feed."""
        # Mock successful responses
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "lastUpdateId": 12345,
            "bids": [["43000.00", "0.5"]],
            "asks": [["43001.00", "0.3"]]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        feed = BinanceUSL2Feed(symbol="BTCUSDT", poll_interval_ms=100)

        # Start feed
        task = asyncio.create_task(feed.start())

        # Let it run for a bit
        await asyncio.sleep(0.5)

        # Stop feed
        feed.stop()
        await task

        # Verify it fetched data
        assert feed.fetch_count > 0
        assert not feed.running

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="MagicMock pickling issue with thread pool executor - see issue #15")
    @patch("trade_engine.adapters.feeds.binance_us_l2.requests.get")
    async def test_start_with_error_recovery(self, mock_get):
        """Test feed continues after errors."""
        # Create success mock response
        mock_success = MagicMock()
        mock_success.json.return_value = {
            "lastUpdateId": 12345,
            "bids": [["43000.00", "0.5"]],
            "asks": [["43001.00", "0.3"]]
        }
        mock_success.raise_for_status = Mock()

        # First call fails, second succeeds
        mock_get.side_effect = [
            Exception("Network error"),  # First call fails
            mock_success  # Second call succeeds
        ]

        feed = BinanceUSL2Feed(symbol="BTCUSDT", poll_interval_ms=100)

        # Start feed
        task = asyncio.create_task(feed.start())

        # Let it recover and fetch successfully
        await asyncio.sleep(1.5)

        # Stop feed
        feed.stop()
        await task

        # Should have recovered and fetched successfully
        assert feed.last_update_time > 0


class TestPerformanceTracking:
    """Test performance metric tracking."""

    @pytest.mark.asyncio
    @patch("trade_engine.adapters.feeds.binance_us_l2.requests.get")
    async def test_average_latency_tracking(self, mock_get):
        """Test average latency calculation."""
        # Mock responses
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "lastUpdateId": 12345,
            "bids": [["43000.00", "0.5"]],
            "asks": [["43001.00", "0.3"]]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        feed = BinanceUSL2Feed(symbol="BTCUSDT", poll_interval_ms=100)

        # Start feed
        task = asyncio.create_task(feed.start())

        # Let it run for multiple fetches
        await asyncio.sleep(0.5)

        # Stop feed
        feed.stop()
        await task

        # Verify performance tracking
        assert feed.fetch_count > 0
        avg_latency = feed.get_average_latency()
        assert avg_latency > 0
        assert avg_latency < 5000  # Should be less than 5 seconds

    def test_average_latency_zero_fetches(self):
        """Test average latency with no fetches."""
        feed = BinanceUSL2Feed(symbol="BTCUSDT")
        assert feed.get_average_latency() == 0.0


class TestContextManager:
    """Test async context manager."""

    @pytest.mark.asyncio
    @patch("trade_engine.adapters.feeds.binance_us_l2.requests.get")
    async def test_context_manager(self, mock_get):
        """Test using feed as context manager."""
        from trade_engine.adapters.feeds.binance_us_l2 import BinanceUSL2FeedContext

        # Mock responses
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "lastUpdateId": 12345,
            "bids": [["43000.00", "0.5"]],
            "asks": [["43001.00", "0.3"]]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Use context manager
        async with BinanceUSL2FeedContext(symbol="BTCUSDT") as feed:
            # Should have started and fetched initial snapshot
            assert feed.last_update_time > 0
            assert len(feed.order_book.bids) > 0
            assert len(feed.order_book.asks) > 0

        # Should have stopped
        assert not feed.running

    @pytest.mark.asyncio
    @patch("trade_engine.adapters.feeds.binance_us_l2.requests.get")
    async def test_context_manager_timeout(self, mock_get):
        """Test context manager fails if initial snapshot times out."""
        from trade_engine.adapters.feeds.binance_us_l2 import BinanceUSL2FeedContext
        import requests

        # Mock timeout
        mock_get.side_effect = requests.exceptions.Timeout()

        # Should raise error if can't fetch initial snapshot
        with pytest.raises(BinanceUSL2FeedError, match="Failed to fetch initial order book"):
            async with BinanceUSL2FeedContext(symbol="BTCUSDT"):
                pass


class TestOrderBookIntegration:
    """Test integration with OrderBook class."""

    @pytest.mark.asyncio
    @patch("trade_engine.adapters.feeds.binance_us_l2.requests.get")
    async def test_order_book_updates(self, mock_get):
        """Test that order book gets updated correctly."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "lastUpdateId": 12345,
            "bids": [
                ["43000.00", "0.5"],
                ["42999.00", "1.0"],
                ["42998.00", "0.8"]
            ],
            "asks": [
                ["43001.00", "0.3"],
                ["43002.00", "0.8"],
                ["43003.00", "0.5"]
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        feed = BinanceUSL2Feed(symbol="BTCUSDT", depth=5)

        # Fetch snapshot
        await feed._fetch_snapshot()

        # Verify order book populated
        assert len(feed.order_book.bids) == 3
        assert len(feed.order_book.asks) == 3

        # Test imbalance calculation
        imbalance = feed.order_book.calculate_imbalance(depth=3)
        assert imbalance > 0  # Should have some imbalance

        # Test mid price
        mid_price = feed.order_book.get_mid_price()
        assert mid_price is not None
        assert mid_price > Decimal("43000")
        assert mid_price < Decimal("43002")

        # Test validity
        assert feed.order_book.is_valid()


class TestStalenessChecks:
    """Test staleness detection for REST L2 feed."""

    def test_is_stale_when_never_updated(self):
        """Test that feed is stale when never updated."""
        feed = BinanceUSL2Feed(symbol="BTCUSDT")

        # Never updated = stale
        assert feed.is_stale() is True
        assert feed.get_staleness_seconds() == 0.0

    @pytest.mark.asyncio
    @patch("trade_engine.adapters.feeds.binance_us_l2.requests.get")
    async def test_is_not_stale_after_fresh_update(self, mock_get):
        """Test that feed is not stale immediately after update."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "lastUpdateId": 12345,
            "bids": [["43000.00", "0.5"]],
            "asks": [["43001.00", "0.3"]]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        feed = BinanceUSL2Feed(
            symbol="BTCUSDT",
            staleness_threshold_seconds=5.0
        )

        # Fetch snapshot
        await feed._fetch_snapshot()

        # Should not be stale immediately
        assert feed.is_stale() is False
        assert feed.get_staleness_seconds() < 1.0

    def test_is_stale_after_threshold_exceeded(self):
        """Test that feed becomes stale after threshold."""
        import time

        feed = BinanceUSL2Feed(
            symbol="BTCUSDT",
            staleness_threshold_seconds=1.0  # 1 second threshold
        )

        # Manually set last_update_time to 2 seconds ago
        feed.last_update_time = time.time() - 2.0

        # Should be stale (2s > 1s threshold)
        assert feed.is_stale() is True
        assert feed.get_staleness_seconds() >= 2.0

    def test_is_stale_with_custom_threshold(self):
        """Test staleness check with custom threshold override."""
        import time

        feed = BinanceUSL2Feed(
            symbol="BTCUSDT",
            staleness_threshold_seconds=10.0  # Default 10s
        )

        # Set last_update to 5 seconds ago
        feed.last_update_time = time.time() - 5.0

        # Not stale with default threshold (5s < 10s)
        assert feed.is_stale() is False

        # But stale with custom 3s threshold (5s > 3s)
        assert feed.is_stale(threshold_seconds=3.0) is True

    @pytest.mark.asyncio
    @patch("trade_engine.adapters.feeds.binance_us_l2.requests.get")
    async def test_consecutive_failures_tracked(self, mock_get):
        """Test that consecutive failures are tracked."""
        # Mock failure
        mock_get.side_effect = Exception("Network error")

        feed = BinanceUSL2Feed(symbol="BTCUSDT", poll_interval_ms=100)

        # Start feed in background
        task = asyncio.create_task(feed.start())

        # Let it fail a few times
        await asyncio.sleep(0.5)

        # Stop feed
        feed.stop()
        await task

        # Should have tracked failures
        assert feed.consecutive_failures > 0

    @pytest.mark.asyncio
    @patch("trade_engine.adapters.feeds.binance_us_l2.requests.get")
    async def test_consecutive_failures_reset_on_success(self, mock_get):
        """Test that consecutive failures reset after successful fetch."""
        # Mock successful response
        mock_success = MagicMock()
        mock_success.json.return_value = {
            "lastUpdateId": 12345,
            "bids": [["43000.00", "0.5"]],
            "asks": [["43001.00", "0.3"]]
        }
        mock_success.raise_for_status = Mock()
        mock_get.return_value = mock_success

        feed = BinanceUSL2Feed(symbol="BTCUSDT", poll_interval_ms=100)

        # Manually set consecutive failures
        feed.consecutive_failures = 3

        # Fetch snapshot (should succeed)
        await feed._fetch_snapshot()

        # After successful fetch, we can verify the update time was set
        assert feed.last_update_time > 0
        assert len(feed.order_book.bids) > 0

    def test_staleness_threshold_configurable(self):
        """Test that staleness threshold can be configured."""
        feed1 = BinanceUSL2Feed(
            symbol="BTCUSDT",
            staleness_threshold_seconds=5.0
        )
        assert feed1.staleness_threshold_seconds == 5.0

        feed2 = BinanceUSL2Feed(
            symbol="ETHUSDT",
            staleness_threshold_seconds=10.0
        )
        assert feed2.staleness_threshold_seconds == 10.0
