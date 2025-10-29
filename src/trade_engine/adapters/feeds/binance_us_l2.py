"""
Binance.US Spot L2 Order Book Feed (REST-based polling)

Since Binance.US does NOT have a public WebSocket order book API or testnet,
this implementation uses REST API polling to fetch order book snapshots.

**Trade-offs vs WebSocket:**
- Higher latency: 100-500ms vs 10-50ms (WebSocket)
- Rate limits: 10 requests/second (2400/day per symbol)
- Actual Binance.US data (matches execution venue)
- No testnet available (can only test with dry-run mode)

**Use this when:**
- You need actual Binance.US order book data
- You're trading on Binance.US (not Binance.com)
- You accept higher latency for data accuracy

**Consider Kraken Futures if:**
- You need low latency (<50ms)
- You want a free testnet environment
- You can use futures (long + short)
"""

import asyncio
import time
from decimal import Decimal
from typing import Optional
import requests
from loguru import logger

from trade_engine.adapters.feeds.binance_l2 import OrderBook
from trade_engine.core.constants import BINANCE_REQUEST_TIMEOUT_SECONDS


class BinanceUSL2FeedError(Exception):
    """Binance.US L2 feed errors."""
    pass


class BinanceUSL2Feed:
    """
    Binance.US Spot L2 order book feed (REST-based polling).

    Uses REST API polling to fetch order book snapshots from Binance.US.
    Since Binance.US has no WebSocket L2 API, this is the only way to get
    actual Binance.US order book data.

    **Limitations:**
    - Higher latency than WebSocket (100-500ms vs 10-50ms)
    - Rate limits: 10 requests/second
    - No testnet available

    **Advantages:**
    - Actual Binance.US data (matches execution venue)
    - No WebSocket connection management
    - Simpler implementation

    Usage:
        feed = BinanceUSL2Feed(symbol="BTCUSDT", depth=5, poll_interval_ms=500)
        await feed.start()

        # Get current order book
        imbalance = feed.order_book.calculate_imbalance(depth=5)
    """

    BASE_URL = "https://api.binance.us"

    def __init__(
        self,
        symbol: str,
        depth: int = 5,
        poll_interval_ms: int = 500,
        rate_limit_per_second: int = 10
    ):
        """
        Initialize Binance.US L2 feed.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            depth: Order book depth to fetch (5, 10, 20, 50, 100, 500, 1000, 5000)
            poll_interval_ms: Polling interval in milliseconds (default 500ms)
            rate_limit_per_second: Max requests per second (default 10)
        """
        self.symbol = symbol.upper()
        self.depth = depth
        self.poll_interval_ms = poll_interval_ms
        self.rate_limit_per_second = rate_limit_per_second

        # Order book state
        self.order_book = OrderBook(symbol=self.symbol)

        # Polling state
        self.running = False
        self.last_update_time = 0
        self.request_count = 0
        self.request_window_start = time.time()

        # Performance tracking
        self.fetch_count = 0
        self.total_latency_ms = 0

        logger.info(
            f"BinanceUSL2Feed initialized | "
            f"Symbol: {self.symbol} | "
            f"Depth: {self.depth} | "
            f"Poll interval: {poll_interval_ms}ms | "
            f"Source: Binance.US (REST API)"
        )

        logger.warning(
            "⚠️  Using REST polling (higher latency than WebSocket). "
            "Expected latency: 100-500ms. "
            "Consider Kraken Futures for <50ms latency."
        )

    async def start(self):
        """Start polling order book data."""
        self.running = True
        logger.info("Starting Binance.US L2 feed (REST polling)")

        while self.running:
            try:
                # Check rate limit
                await self._check_rate_limit()

                # Fetch snapshot
                start_time = time.time()
                await self._fetch_snapshot()
                latency_ms = (time.time() - start_time) * 1000

                # Track performance
                self.fetch_count += 1
                self.total_latency_ms += latency_ms

                # Log performance every 60 seconds
                if self.fetch_count % 120 == 0:  # 120 fetches = 1 minute at 500ms
                    avg_latency = self.total_latency_ms / self.fetch_count
                    logger.info(
                        f"L2 Feed Performance | "
                        f"Avg latency: {avg_latency:.2f}ms | "
                        f"Fetches: {self.fetch_count} | "
                        f"Last: {latency_ms:.2f}ms"
                    )

                # Sleep until next poll
                await asyncio.sleep(self.poll_interval_ms / 1000.0)

            except Exception as e:
                logger.error(f"Error fetching order book: {e}")
                await asyncio.sleep(1.0)  # Back off on error

    def stop(self):
        """Stop polling."""
        self.running = False
        logger.info("Binance.US L2 feed stopped")

    async def _check_rate_limit(self):
        """
        Check and enforce rate limits.

        Binance.US rate limits:
        - 10 requests/second per IP
        - 2400 requests/day per symbol
        """
        now = time.time()

        # Reset counter every second
        if now - self.request_window_start >= 1.0:
            self.request_count = 0
            self.request_window_start = now

        # Check if we're at limit
        if self.request_count >= self.rate_limit_per_second:
            sleep_time = 1.0 - (now - self.request_window_start)
            if sleep_time > 0:
                logger.debug(f"Rate limit reached, sleeping {sleep_time:.3f}s")
                await asyncio.sleep(sleep_time)
                self.request_count = 0
                self.request_window_start = time.time()

        self.request_count += 1

    async def _fetch_snapshot(self):
        """
        Fetch order book snapshot from Binance.US.

        Endpoint: GET /api/v3/depth
        Docs: https://github.com/binance-us/binance-official-api-docs/blob/master/rest-api.md#order-book
        """
        url = f"{self.BASE_URL}/api/v3/depth"
        params = {
            "symbol": self.symbol,
            "limit": self._get_api_limit()
        }

        try:
            # Make request (run in executor to avoid blocking)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(
                    url,
                    params=params,
                    timeout=BINANCE_REQUEST_TIMEOUT_SECONDS
                )
            )

            response.raise_for_status()
            data = response.json()

            # Apply snapshot to order book
            self.order_book.apply_snapshot(data)
            self.last_update_time = time.time()

        except requests.exceptions.RequestException as e:
            raise BinanceUSL2FeedError(f"Failed to fetch order book: {e}")

    def _get_api_limit(self) -> int:
        """
        Map depth to valid Binance.US API limit.

        Valid limits: 5, 10, 20, 50, 100, 500, 1000, 5000
        """
        valid_limits = [5, 10, 20, 50, 100, 500, 1000, 5000]

        # Find closest valid limit >= requested depth
        for limit in valid_limits:
            if limit >= self.depth:
                return limit

        return 5000  # Max

    def get_average_latency(self) -> float:
        """Get average fetch latency in milliseconds."""
        if self.fetch_count == 0:
            return 0.0
        return self.total_latency_ms / self.fetch_count


# Async context manager support
class BinanceUSL2FeedContext:
    """
    Context manager for Binance.US L2 feed.

    Usage:
        async with BinanceUSL2FeedContext(symbol="BTCUSDT") as feed:
            imbalance = feed.order_book.calculate_imbalance(depth=5)
    """

    def __init__(self, symbol: str, depth: int = 5, poll_interval_ms: int = 500):
        self.feed = BinanceUSL2Feed(
            symbol=symbol,
            depth=depth,
            poll_interval_ms=poll_interval_ms
        )
        self.task = None

    async def __aenter__(self):
        """Start feed."""
        self.task = asyncio.create_task(self.feed.start())

        # Wait for first snapshot
        for _ in range(10):  # Wait up to 5 seconds
            if self.feed.last_update_time > 0:
                break
            await asyncio.sleep(0.5)

        if self.feed.last_update_time == 0:
            raise BinanceUSL2FeedError("Failed to fetch initial order book snapshot")

        return self.feed

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Stop feed."""
        self.feed.stop()
        if self.task:
            await self.task
