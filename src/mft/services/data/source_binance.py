"""
Binance data source adapter.

Provides access to:
- Cryptocurrency spot prices (BTC, ETH, etc.)
- Cryptocurrency futures prices
- Historical OHLCV data
- Real-time quotes

Free public API (no authentication required for market data).
Rate limit: 1200 requests/minute.
"""

from datetime import datetime, timezone
from typing import List, Optional
from loguru import logger
import requests

from app.data.types import (
    DataSource,
    DataSourceType,
    AssetType,
    OHLCV,
    Quote
)


class BinanceDataSource(DataSource):
    """
    Binance market data adapter.

    Uses public API endpoints (no authentication required).
    Supports both Spot and Futures markets.
    """

    SPOT_BASE = "https://api.binance.com"
    FUTURES_BASE = "https://fapi.binance.com"

    # Interval mapping: internal → Binance
    INTERVAL_MAP = {
        "1m": "1m",
        "3m": "3m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "2h": "2h",
        "4h": "4h",
        "6h": "6h",
        "8h": "8h",
        "12h": "12h",
        "1d": "1d",
        "3d": "3d",
        "1w": "1w",
        "1mo": "1M"
    }

    def __init__(self, market: str = "spot", timeout: int = 10):
        """
        Initialize Binance data source.

        Args:
            market: "spot" or "futures" (default: "spot")
            timeout: Request timeout in seconds (default: 10)
        """
        if market not in ["spot", "futures"]:
            raise ValueError(f"Invalid market: {market}. Use 'spot' or 'futures'")

        self.market = market
        self.timeout = timeout
        self.base_url = self.SPOT_BASE if market == "spot" else self.FUTURES_BASE
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "MFT-DataAggregator/1.0"
        })

    def __del__(self):
        """Clean up session on deletion to prevent resource leak."""
        if hasattr(self, 'session'):
            try:
                self.session.close()
            except Exception:
                pass  # Ignore errors during cleanup

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close session."""
        if hasattr(self, 'session'):
            self.session.close()
        return False

    @property
    def source_type(self) -> DataSourceType:
        return DataSourceType.BINANCE

    @property
    def supported_asset_types(self) -> List[AssetType]:
        return [AssetType.CRYPTO]  # Only crypto

    def fetch_ohlcv(
        self,
        symbol: str,
        interval: str,
        start: datetime,
        end: datetime,
        limit: Optional[int] = None
    ) -> List[OHLCV]:
        """
        Fetch OHLCV from Binance.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT", "ETHUSDT")
            interval: Candle interval (1m, 5m, 1h, 1d, etc.)
            start: Start time (UTC)
            end: End time (UTC)
            limit: Max candles (optional, max 1500 per request)

        Returns:
            List of OHLCV candles
        """
        # Map interval
        binance_interval = self.INTERVAL_MAP.get(interval)
        if not binance_interval:
            raise ValueError(
                f"Unsupported interval: {interval}. "
                f"Supported: {list(self.INTERVAL_MAP.keys())}"
            )

        try:
            # Convert timestamps to milliseconds
            start_ms = int(start.timestamp() * 1000)
            end_ms = int(end.timestamp() * 1000)

            # Build request params
            endpoint = "/api/v3/klines" if self.market == "spot" else "/fapi/v1/klines"
            params = {
                "symbol": symbol.upper().replace("/", ""),  # BTCUSDT format
                "interval": binance_interval,
                "startTime": start_ms,
                "endTime": end_ms,
                "limit": min(limit, 1500) if limit else 1500  # Binance max is 1500
            }

            response = self.session.get(
                f"{self.base_url}{endpoint}",
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            if not data:
                logger.warning(f"No data returned for {symbol} from Binance")
                return []

            # Convert to OHLCV list
            # Binance klines format: [timestamp, open, high, low, close, volume, ...]
            candles = []
            for kline in data:
                candles.append(OHLCV(
                    timestamp=int(kline[0]),  # Open time in ms
                    open=float(kline[1]),
                    high=float(kline[2]),
                    low=float(kline[3]),
                    close=float(kline[4]),
                    volume=float(kline[5]),
                    source=DataSourceType.BINANCE,
                    symbol=symbol
                ))

            logger.debug(
                f"Fetched {len(candles)} candles for {symbol} from Binance {self.market}"
            )
            return candles

        except Exception as e:
            logger.error(f"Binance fetch failed for {symbol}: {e}")
            raise

    def fetch_quote(self, symbol: str) -> Quote:
        """
        Fetch current quote from Binance.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")

        Returns:
            Current quote
        """
        try:
            # Use 24hr ticker endpoint for comprehensive data
            endpoint = "/api/v3/ticker/24hr" if self.market == "spot" else "/fapi/v1/ticker/24hr"
            params = {
                "symbol": symbol.upper().replace("/", "")
            }

            response = self.session.get(
                f"{self.base_url}{endpoint}",
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            # Get bid/ask from order book (separate call)
            book_endpoint = "/api/v3/ticker/bookTicker" if self.market == "spot" else "/fapi/v1/ticker/bookTicker"
            book_response = self.session.get(
                f"{self.base_url}{book_endpoint}",
                params=params,
                timeout=self.timeout
            )
            book_data = book_response.json() if book_response.status_code == 200 else {}

            quote = Quote(
                symbol=symbol,
                price=float(data["lastPrice"]),
                bid=float(book_data.get("bidPrice", 0)) if book_data else None,
                ask=float(book_data.get("askPrice", 0)) if book_data else None,
                volume_24h=float(data.get("volume", 0)),
                timestamp=int(datetime.now(timezone.utc).timestamp() * 1000),
                source=DataSourceType.BINANCE
            )

            return quote

        except Exception as e:
            logger.error(f"Binance quote fetch failed for {symbol}: {e}")
            raise

    def normalize_symbol(self, symbol: str, asset_type: AssetType) -> str:
        """
        Normalize symbol to Binance format.

        Args:
            symbol: Universal symbol (e.g., "BTC/USDT", "BTC", "BTCUSDT")
            asset_type: Must be CRYPTO

        Returns:
            Binance symbol (e.g., "BTCUSDT")

        Examples:
            BTC/USDT → BTCUSDT
            BTC → BTCUSDT (adds USDT)
            BTCUSD → BTCUSDT (converts USD to USDT)
            ETHBTC → ETHBTC (preserves BTC pairs)
        """
        if asset_type != AssetType.CRYPTO:
            raise ValueError("Binance only supports cryptocurrencies")

        # Remove slashes and hyphens, convert to uppercase
        symbol = symbol.replace("/", "").replace("-", "").upper()

        # Convert USD to USDT (but not USDT, BUSD, USDC)
        if symbol.endswith("USD") and not symbol.endswith(("USDT", "BUSD", "USDC")):
            symbol = symbol[:-3] + "USDT"

        # Add USDT suffix if symbol has no quote currency
        # Common quote currencies: USDT, BUSD, USDC, BTC, ETH, BNB
        # But only if symbol is longer than just the base (e.g., "BTC" alone needs USDT)
        has_quote = False
        for quote in ["USDT", "BUSD", "USDC"]:
            if symbol.endswith(quote):
                has_quote = True
                break
        # For BTC, ETH, BNB quote pairs, symbol must be longer than the quote
        for quote in ["BTC", "ETH", "BNB"]:
            if symbol.endswith(quote) and len(symbol) > len(quote):
                has_quote = True
                break

        if not has_quote:
            symbol = f"{symbol}USDT"

        return symbol

    def validate_connection(self) -> bool:
        """
        Test Binance connection.

        Returns:
            True if connection successful
        """
        try:
            # Ping endpoint
            endpoint = "/api/v3/ping" if self.market == "spot" else "/fapi/v1/ping"
            response = self.session.get(
                f"{self.base_url}{endpoint}",
                timeout=self.timeout
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Binance connection test failed: {e}")
            return False
