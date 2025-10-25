"""
Binance Futures L2 Order Book Data Feed

Real-time Level 2 order book depth streaming via WebSocket.
Implements DataFeed interface for live trading engine.

Performance Targets:
- Update interval: 100ms
- Processing latency: <5ms per update
- Total system latency: <50ms sustained

CRITICAL: All price/quantity values use Decimal (NON-NEGOTIABLE per CLAUDE.md).
"""

import asyncio
import json
import time
from decimal import Decimal
from typing import Iterator, Dict, List, Tuple, Optional
from collections import OrderedDict
from sortedcontainers import SortedDict
import websockets
from loguru import logger

from mft.core.engine.types import DataFeed, Bar


class BinanceL2Error(Exception):
    """Binance L2 feed errors."""
    pass


class OrderBook:
    """
    Efficient order book implementation using SortedDict.

    Maintains bid/ask levels sorted by price for fast access to top N levels.
    Supports both full snapshots and incremental delta updates.
    """

    def __init__(self, symbol: str):
        """
        Initialize order book.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
        """
        self.symbol = symbol
        self.bids: SortedDict[Decimal, Decimal] = SortedDict()  # price → quantity
        self.asks: SortedDict[Decimal, Decimal] = SortedDict()  # price → quantity
        self.last_update_id = 0
        self.last_update_time = 0.0

    def apply_snapshot(self, data: dict):
        """
        Initialize order book from full snapshot.

        Args:
            data: Snapshot data from Binance depth endpoint
        """
        self.bids.clear()
        self.asks.clear()

        # Parse bids (descending price order)
        for price_str, qty_str in data['bids']:
            price = Decimal(price_str)
            qty = Decimal(qty_str)
            if qty > 0:
                self.bids[price] = qty

        # Parse asks (ascending price order)
        for price_str, qty_str in data['asks']:
            price = Decimal(price_str)
            qty = Decimal(qty_str)
            if qty > 0:
                self.asks[price] = qty

        self.last_update_id = data['lastUpdateId']
        self.last_update_time = time.time()

        logger.debug(
            f"Snapshot applied: {self.symbol} | "
            f"Bids: {len(self.bids)} | Asks: {len(self.asks)} | "
            f"UpdateID: {self.last_update_id}"
        )

    def apply_delta(self, data: dict):
        """
        Apply incremental delta update.

        Args:
            data: Delta update from WebSocket stream
        """
        # Update bids
        for price_str, qty_str in data.get('b', []):
            price = Decimal(price_str)
            qty = Decimal(qty_str)

            if qty == 0:
                # Remove price level
                self.bids.pop(price, None)
            else:
                # Update price level
                self.bids[price] = qty

        # Update asks
        for price_str, qty_str in data.get('a', []):
            price = Decimal(price_str)
            qty = Decimal(qty_str)

            if qty == 0:
                self.asks.pop(price, None)
            else:
                self.asks[price] = qty

        self.last_update_id = data['u']
        self.last_update_time = time.time()

    def get_top_levels(self, depth: int = 5) -> Tuple[List[Tuple[Decimal, Decimal]], List[Tuple[Decimal, Decimal]]]:
        """
        Get top N bid/ask levels.

        Args:
            depth: Number of levels to return

        Returns:
            (bids, asks) where each is list of (price, quantity) tuples
            Bids sorted descending, asks sorted ascending
        """
        # Get top bids (highest prices first)
        bids = list(reversed(self.bids.items()))[:depth]

        # Get top asks (lowest prices first)
        asks = list(self.asks.items())[:depth]

        return bids, asks

    def calculate_imbalance(self, depth: int = 5) -> Decimal:
        """
        Calculate bid/ask volume imbalance ratio.

        Imbalance = sum(bid_qty) / sum(ask_qty) for top N levels

        Args:
            depth: Number of levels to include

        Returns:
            Imbalance ratio (>1 = bullish, <1 = bearish)
        """
        bids, asks = self.get_top_levels(depth)

        if not bids or not asks:
            return Decimal("1.0")  # Neutral if insufficient data

        bid_volume = sum(qty for _, qty in bids)
        ask_volume = sum(qty for _, qty in asks)

        if ask_volume == 0:
            return Decimal("999.0")  # Cap at 999 instead of infinity

        return bid_volume / ask_volume

    def get_mid_price(self) -> Optional[Decimal]:
        """
        Get mid-market price (average of best bid/ask).

        Returns:
            Mid price or None if order book empty
        """
        if not self.bids or not self.asks:
            return None

        best_bid = self.bids.peekitem(-1)[0]  # Highest bid
        best_ask = self.asks.peekitem(0)[0]   # Lowest ask

        return (best_bid + best_ask) / Decimal("2")

    def get_spread_bps(self) -> Optional[Decimal]:
        """
        Get bid-ask spread in basis points.

        Returns:
            Spread in basis points or None if order book empty
        """
        if not self.bids or not self.asks:
            return None

        best_bid = self.bids.peekitem(-1)[0]
        best_ask = self.asks.peekitem(0)[0]
        mid = (best_bid + best_ask) / Decimal("2")

        if mid == 0:
            return None

        spread = best_ask - best_bid
        return (spread / mid) * Decimal("10000")

    def is_valid(self) -> bool:
        """
        Check if order book is valid and not stale.

        Returns:
            True if order book has data and is recent
        """
        if not self.bids or not self.asks:
            return False

        # Check for staleness (>1 second since last update)
        age = time.time() - self.last_update_time
        if age > 1.0:
            logger.warning(f"Stale order book: {self.symbol} | Age: {age:.2f}s")
            return False

        # Check for crossed book (bid >= ask)
        best_bid = self.bids.peekitem(-1)[0]
        best_ask = self.asks.peekitem(0)[0]
        if best_bid >= best_ask:
            logger.error(
                f"Crossed book detected: {self.symbol} | "
                f"Bid: {best_bid} | Ask: {best_ask}"
            )
            return False

        return True


class BinanceFuturesL2Feed(DataFeed):
    """
    Binance Futures L2 order book feed via WebSocket.

    Subscribes to depth@100ms stream for real-time order book updates.
    Maintains order book state and yields bars/signals.

    Usage:
        feed = BinanceFuturesL2Feed(symbol="BTCUSDT", depth=5)
        for bar in feed.candles():
            # Process bar with order book snapshot
            pass
    """

    WS_BASE_LIVE = "wss://fstream.binance.com/ws"
    REST_BASE_LIVE = "https://fapi.binance.com"
    WS_BASE_TESTNET = "wss://stream.binancefuture.com/ws"
    REST_BASE_TESTNET = "https://testnet.binancefuture.com"

    def __init__(
        self,
        symbol: str,
        depth: int = 5,
        update_interval_ms: int = 100,
        testnet: bool = True
    ):
        """
        Initialize L2 feed.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            depth: Order book depth to track
            update_interval_ms: Update interval (100ms recommended)
            testnet: If True, use testnet (default)
        """
        self.symbol = symbol.upper()
        self.depth = depth
        self.update_interval_ms = update_interval_ms
        self.testnet = testnet

        # Select endpoints
        if testnet:
            self.ws_base = self.WS_BASE_TESTNET
            self.rest_base = self.REST_BASE_TESTNET
        else:
            self.ws_base = self.WS_BASE_LIVE
            self.rest_base = self.REST_BASE_LIVE

        self.order_book = OrderBook(self.symbol)
        self.ws_connection: Optional[websockets.WebSocketClientProtocol] = None
        self.running = False

        logger.info(
            f"BinanceFuturesL2Feed initialized | "
            f"Symbol: {self.symbol} | "
            f"Depth: {self.depth} | "
            f"Interval: {update_interval_ms}ms"
        )

    async def _fetch_snapshot(self):
        """
        Fetch initial order book snapshot via REST API.

        This is required before processing WebSocket deltas.
        """
        import requests

        url = f"{self.rest_base}/fapi/v1/depth"
        params = {"symbol": self.symbol, "limit": 1000}

        try:
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            self.order_book.apply_snapshot(data)
            logger.info(f"Snapshot fetched: {self.symbol}")

        except Exception as e:
            raise BinanceL2Error(f"Failed to fetch snapshot: {e}")

    async def _connect_websocket(self):
        """
        Connect to Binance Futures WebSocket depth stream.

        Stream format: {symbol}@depth@{interval}
        Example: btcusdt@depth@100ms
        """
        stream_name = f"{self.symbol.lower()}@depth@{self.update_interval_ms}ms"
        ws_url = f"{self.ws_base}/{stream_name}"

        logger.info(f"Connecting to WebSocket: {ws_url}")

        try:
            self.ws_connection = await websockets.connect(
                ws_url,
                ping_interval=20,
                ping_timeout=10
            )
            logger.info(f"WebSocket connected: {self.symbol}")

        except Exception as e:
            raise BinanceL2Error(f"WebSocket connection failed: {e}")

    async def _process_ws_messages(self):
        """
        Process incoming WebSocket messages.

        Applies delta updates to order book state.
        """
        if not self.ws_connection:
            raise BinanceL2Error("WebSocket not connected")

        async for message in self.ws_connection:
            try:
                data = json.loads(message)

                # Binance depth stream format:
                # {
                #   "e": "depthUpdate",
                #   "E": event_time,
                #   "s": "BTCUSDT",
                #   "U": first_update_id,
                #   "u": last_update_id,
                #   "b": [[price, qty], ...],  # bids
                #   "a": [[price, qty], ...]   # asks
                # }

                if data.get('e') == 'depthUpdate':
                    self.order_book.apply_delta(data)

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse WebSocket message: {e}")
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")

    def candles(self) -> Iterator[Bar]:
        """
        Yield validated bars from L2 feed.

        NOTE: This is a compatibility method for the DataFeed interface.
        For L2 trading, you should use the order_book directly.

        This generates "bars" with OHLCV derived from mid-price,
        but the real value is in the order book imbalance signals.

        Yields:
            Bar objects with mid-price as OHLC and imbalance metadata
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Initialize: fetch snapshot and connect WebSocket
            loop.run_until_complete(self._fetch_snapshot())
            loop.run_until_complete(self._connect_websocket())

            # Start processing messages in background
            self.running = True
            message_task = loop.create_task(self._process_ws_messages())

            # Yield bars at regular intervals
            last_bar_time = time.time()
            bar_interval_seconds = 1.0  # 1 second bars

            while self.running:
                loop.run_until_complete(asyncio.sleep(0.01))  # 10ms sleep

                now = time.time()
                if now - last_bar_time >= bar_interval_seconds:
                    # Generate bar from current order book state
                    if self.order_book.is_valid():
                        mid_price = self.order_book.get_mid_price()

                        if mid_price:
                            # Create bar (mid-price as OHLC for simplicity)
                            bar = Bar(
                                timestamp=int(now * 1000),
                                open=mid_price,
                                high=mid_price,
                                low=mid_price,
                                close=mid_price,
                                volume=Decimal("0"),  # Not applicable for L2
                                gap_flag=False,
                                zero_vol_flag=False
                            )

                            yield bar
                            last_bar_time = now
                    else:
                        logger.warning(f"Invalid order book, skipping bar generation")

        except KeyboardInterrupt:
            logger.info("L2 feed stopped by user")
        except Exception as e:
            logger.error(f"L2 feed error: {e}")
            raise
        finally:
            self.running = False
            if self.ws_connection:
                loop.run_until_complete(self.ws_connection.close())
            loop.close()

    def get_imbalance(self) -> Decimal:
        """
        Get current order book imbalance ratio.

        This is the primary signal for L2 trading strategy.

        Returns:
            Imbalance ratio (>3.0 = strong buy, <0.33 = strong sell)
        """
        return self.order_book.calculate_imbalance(self.depth)

    def get_order_book_snapshot(self) -> Dict:
        """
        Get current order book snapshot for logging/analysis.

        Returns:
            Dict with bids, asks, mid_price, spread, imbalance
        """
        bids, asks = self.order_book.get_top_levels(self.depth)

        return {
            "symbol": self.symbol,
            "timestamp": int(self.order_book.last_update_time * 1000),
            "bids": [[str(p), str(q)] for p, q in bids],
            "asks": [[str(p), str(q)] for p, q in asks],
            "mid_price": str(self.order_book.get_mid_price() or "0"),
            "spread_bps": str(self.order_book.get_spread_bps() or "0"),
            "imbalance": str(self.get_imbalance()),
            "is_valid": self.order_book.is_valid()
        }
