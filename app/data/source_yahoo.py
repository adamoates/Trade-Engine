"""
Yahoo Finance data source adapter.

Provides access to:
- Stocks (NYSE, NASDAQ, etc.)
- ETFs
- Indices (^GSPC, ^DJI, etc.)
- Crypto (BTC-USD, ETH-USD)
- Forex pairs

Free, no API key required.
"""

from datetime import datetime
from typing import List, Optional
from loguru import logger

try:
    import yfinance as yf
except ImportError:
    yf = None
    logger.warning("yfinance not installed. Install with: pip install yfinance")

from app.data.types import (
    DataSource,
    DataSourceType,
    AssetType,
    OHLCV,
    Quote
)


class YahooFinanceSource(DataSource):
    """
    Yahoo Finance data adapter.

    Uses yfinance library for easy access to Yahoo Finance API.
    """

    # Interval mapping: internal → yfinance
    INTERVAL_MAP = {
        "1m": "1m",
        "2m": "2m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "1d": "1d",
        "1wk": "1wk",
        "1mo": "1mo"
    }

    def __init__(self):
        """Initialize Yahoo Finance source."""
        if yf is None:
            raise ImportError(
                "yfinance library required. Install with: pip install yfinance"
            )

    @property
    def source_type(self) -> DataSourceType:
        return DataSourceType.YAHOO_FINANCE

    @property
    def supported_asset_types(self) -> List[AssetType]:
        return [
            AssetType.STOCK,
            AssetType.ETF,
            AssetType.INDEX,
            AssetType.CRYPTO,
            AssetType.FOREX
        ]

    def fetch_ohlcv(
        self,
        symbol: str,
        interval: str,
        start: datetime,
        end: datetime,
        limit: Optional[int] = None
    ) -> List[OHLCV]:
        """
        Fetch OHLCV from Yahoo Finance.

        Args:
            symbol: Ticker symbol (e.g., "AAPL", "BTC-USD", "^GSPC")
            interval: Candle interval
            start: Start time (UTC)
            end: End time (UTC)
            limit: Max candles (ignored - Yahoo returns all data in range)

        Returns:
            List of OHLCV candles
        """
        # Map interval
        yf_interval = self.INTERVAL_MAP.get(interval)
        if not yf_interval:
            raise ValueError(
                f"Unsupported interval: {interval}. "
                f"Supported: {list(self.INTERVAL_MAP.keys())}"
            )

        try:
            # Fetch data
            ticker = yf.Ticker(symbol)
            df = ticker.history(
                start=start,
                end=end,
                interval=yf_interval,
                actions=False  # Don't include dividends/splits
            )

            if df.empty:
                logger.warning(f"No data returned for {symbol} from Yahoo Finance")
                return []

            # Convert to OHLCV list
            candles = []
            for timestamp, row in df.iterrows():
                # Yahoo returns timezone-aware timestamps
                ts_ms = int(timestamp.timestamp() * 1000)

                candles.append(OHLCV(
                    timestamp=ts_ms,
                    open=float(row['Open']),
                    high=float(row['High']),
                    low=float(row['Low']),
                    close=float(row['Close']),
                    volume=float(row['Volume']),
                    source=DataSourceType.YAHOO_FINANCE,
                    symbol=symbol
                ))

            logger.debug(
                f"Fetched {len(candles)} candles for {symbol} from Yahoo Finance"
            )
            return candles

        except Exception as e:
            logger.error(f"Yahoo Finance fetch failed for {symbol}: {e}")
            raise

    def fetch_quote(self, symbol: str) -> Quote:
        """
        Fetch current quote from Yahoo Finance.

        Args:
            symbol: Ticker symbol

        Returns:
            Current quote
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            # Get current price (multiple fallbacks)
            price = (
                info.get('currentPrice') or
                info.get('regularMarketPrice') or
                info.get('previousClose')
            )

            if price is None:
                raise ValueError(f"No price data available for {symbol}")

            quote = Quote(
                symbol=symbol,
                price=float(price),
                bid=info.get('bid'),
                ask=info.get('ask'),
                volume_24h=info.get('volume'),
                timestamp=int(datetime.utcnow().timestamp() * 1000),
                source=DataSourceType.YAHOO_FINANCE
            )

            return quote

        except Exception as e:
            logger.error(f"Yahoo Finance quote fetch failed for {symbol}: {e}")
            raise

    def normalize_symbol(self, symbol: str, asset_type: AssetType) -> str:
        """
        Normalize symbol to Yahoo Finance format.

        Args:
            symbol: Universal symbol (e.g., "BTC/USDT", "BTC-USD", "AAPL")
            asset_type: Asset type hint

        Returns:
            Yahoo Finance symbol

        Examples:
            BTC/USDT → BTC-USD
            BTC/USD → BTC-USD
            AAPL → AAPL
            S&P 500 → ^GSPC
        """
        # Remove slashes
        symbol = symbol.replace("/", "-").upper()

        # Crypto: Yahoo uses -USD suffix
        if asset_type == AssetType.CRYPTO:
            if not symbol.endswith("-USD"):
                # Remove USDT suffix if present, replace with USD
                symbol = symbol.replace("USDT", "").replace("BUSD", "")
                if not symbol.endswith("-USD"):
                    symbol = f"{symbol}-USD"

        # Indices: Yahoo uses ^ prefix
        elif asset_type == AssetType.INDEX:
            if not symbol.startswith("^"):
                # Common index mappings
                index_map = {
                    "SPX": "^GSPC",
                    "SP500": "^GSPC",
                    "DJI": "^DJI",
                    "DOW": "^DJI",
                    "NASDAQ": "^IXIC",
                    "RUT": "^RUT"
                }
                symbol = index_map.get(symbol, f"^{symbol}")

        return symbol

    def validate_connection(self) -> bool:
        """
        Test Yahoo Finance connection.

        Returns:
            True if connection successful
        """
        try:
            # Try to fetch SPY (always available)
            ticker = yf.Ticker("SPY")
            info = ticker.info
            return 'currentPrice' in info or 'regularMarketPrice' in info
        except Exception as e:
            logger.error(f"Yahoo Finance connection test failed: {e}")
            return False
