"""
Binance WebSocket data stream for live trading.

Streams real-time kline (candlestick) data from Binance via WebSocket.
Handles reconnection, aggregation, and emits completed candles.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass

import websockets
from loguru import logger


@dataclass
class Candle:
    """Completed candlestick bar."""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    timeframe: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'timeframe': self.timeframe
        }


class BinanceKlineStream:
    """
    WebSocket stream for Binance kline (candlestick) data.

    Streams real-time candles and emits completed bars to a callback.
    Automatically reconnects on disconnection.

    Example:
        async def on_candle(candle: Candle):
            print(f"New candle: {candle.symbol} @ {candle.close}")

        stream = BinanceKlineStream(
            symbols=["BTCUSDT", "ETHUSDT"],
            interval="5m",
            on_candle=on_candle,
            testnet=True
        )
        await stream.start()
    """

    # WebSocket URLs
    TESTNET_WS = "wss://stream.binancefuture.com/ws"
    LIVE_WS = "wss://fstream.binance.com/ws"

    def __init__(
        self,
        symbols: list[str],
        interval: str,
        on_candle: Callable[[Candle], None],
        testnet: bool = True
    ):
        """
        Initialize Binance kline stream.

        Args:
            symbols: List of trading symbols (e.g., ["BTCUSDT", "ETHUSDT"])
            interval: Candle interval (1m, 3m, 5m, 15m, 1h, 4h, 1d)
            on_candle: Callback function called when candle completes
            testnet: Use testnet (True) or live (False)
        """
        self.symbols = [s.upper() for s in symbols]
        self.interval = interval
        self.on_candle = on_candle
        self.testnet = testnet

        self.ws_url = self.TESTNET_WS if testnet else self.LIVE_WS
        self.running = False
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None

        logger.info(
            f"BinanceKlineStream initialized | "
            f"Symbols: {self.symbols} | "
            f"Interval: {interval} | "
            f"Mode: {'TESTNET' if testnet else 'LIVE'}"
        )

    def _build_stream_name(self) -> str:
        """Build stream name for subscription."""
        # Format: btcusdt@kline_5m/ethusdt@kline_5m
        streams = [f"{s.lower()}@kline_{self.interval}" for s in self.symbols]
        return "/".join(streams)

    async def start(self):
        """Start streaming (runs forever with auto-reconnect)."""
        self.running = True

        while self.running:
            try:
                await self._connect_and_stream()
            except Exception as e:
                logger.error(f"Stream error: {e}")
                if self.running:
                    logger.info("Reconnecting in 5 seconds...")
                    await asyncio.sleep(5)
                else:
                    break

    async def stop(self):
        """Stop streaming gracefully."""
        logger.info("Stopping stream...")
        self.running = False

        if self.websocket:
            await self.websocket.close()

        logger.info("Stream stopped")

    async def _connect_and_stream(self):
        """Connect to WebSocket and process messages."""
        stream_name = self._build_stream_name()
        url = f"{self.ws_url}/{stream_name}"

        logger.info(f"Connecting to: {url}")

        async with websockets.connect(url) as websocket:
            self.websocket = websocket
            logger.success("✓ WebSocket connected")

            async for message in websocket:
                if not self.running:
                    break

                try:
                    await self._process_message(message)
                except Exception as e:
                    logger.error(f"Message processing error: {e}")

    async def _process_message(self, message: str):
        """Process incoming WebSocket message."""
        data = json.loads(message)

        # Binance kline message structure:
        # {
        #   "e": "kline",
        #   "E": 1234567890,
        #   "s": "BTCUSDT",
        #   "k": {
        #     "t": 1234560000,  # Kline start time
        #     "T": 1234569999,  # Kline close time
        #     "s": "BTCUSDT",
        #     "i": "5m",
        #     "o": "50000.00",  # Open
        #     "h": "50500.00",  # High
        #     "l": "49800.00",  # Low
        #     "c": "50200.00",  # Close
        #     "v": "100.5",     # Volume
        #     "x": true         # Is candle closed?
        #   }
        # }

        if data.get("e") != "kline":
            return

        kline = data["k"]

        # Only process completed candles
        if not kline.get("x", False):
            return

        # Create Candle object
        candle = Candle(
            symbol=kline["s"],
            timestamp=datetime.fromtimestamp(kline["t"] / 1000, tz=timezone.utc),
            open=float(kline["o"]),
            high=float(kline["h"]),
            low=float(kline["l"]),
            close=float(kline["c"]),
            volume=float(kline["v"]),
            timeframe=kline["i"]
        )

        logger.info(
            f"📊 Candle closed: {candle.symbol} | "
            f"O:{candle.open:.2f} H:{candle.high:.2f} "
            f"L:{candle.low:.2f} C:{candle.close:.2f} "
            f"V:{candle.volume:.4f}"
        )

        # Call user callback
        try:
            if asyncio.iscoroutinefunction(self.on_candle):
                await self.on_candle(candle)
            else:
                self.on_candle(candle)
        except Exception as e:
            logger.exception(f"Callback error: {e}")


# Convenience function for quick testing
async def test_stream():
    """Test the stream with console output."""

    async def print_candle(candle: Candle):
        print(f"\n{candle.symbol} @ {candle.timestamp}")
        print(f"  OHLC: {candle.open:.2f} / {candle.high:.2f} / {candle.low:.2f} / {candle.close:.2f}")
        print(f"  Volume: {candle.volume:.4f}")

    stream = BinanceKlineStream(
        symbols=["BTCUSDT"],
        interval="1m",  # 1-minute for fast testing
        on_candle=print_candle,
        testnet=True
    )

    try:
        await stream.start()
    except KeyboardInterrupt:
        await stream.stop()


if __name__ == "__main__":
    # Test the stream
    asyncio.run(test_stream())
