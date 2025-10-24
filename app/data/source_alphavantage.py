"""
Alpha Vantage data source adapter.

Provides access to:
- Stocks (NYSE, NASDAQ, global markets)
- Forex pairs (150+ currencies)
- Cryptocurrency prices
- Technical indicators
- Fundamental data

Free tier: 25 API calls/day, 5 calls/minute.
API key required (free registration).
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional
from loguru import logger
import requests
import os

from app.data.types import (
    DataSource,
    DataSourceType,
    AssetType,
    OHLCV,
    Quote
)


class AlphaVantageSource(DataSource):
    """
    Alpha Vantage API adapter.

    Free tier limitations:
    - 25 API calls per day
    - 5 API calls per minute
    - Requires free API key from https://www.alphavantage.co/support/#api-key
    """

    BASE_URL = "https://www.alphavantage.co/query"

    # Interval mapping: internal → Alpha Vantage
    INTERVAL_MAP = {
        "1m": "1min",
        "5m": "5min",
        "15m": "15min",
        "30m": "30min",
        "1h": "60min",
        "1d": "daily",
        "1w": "weekly",
        "1mo": "monthly"
    }

    def __init__(self, api_key: Optional[str] = None, timeout: int = 30):
        """
        Initialize Alpha Vantage source.

        Args:
            api_key: Alpha Vantage API key (or set ALPHAVANTAGE_API_KEY env var)
            timeout: Request timeout in seconds (default: 30, API can be slow)
        """
        self.api_key = api_key or os.getenv("ALPHAVANTAGE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Alpha Vantage API key required. "
                "Set ALPHAVANTAGE_API_KEY environment variable or pass api_key parameter. "
                "Get free key at: https://www.alphavantage.co/support/#api-key"
            )

        self.timeout = timeout
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
                pass

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
        return DataSourceType.ALPHA_VANTAGE

    @property
    def supported_asset_types(self) -> List[AssetType]:
        return [
            AssetType.STOCK,
            AssetType.ETF,
            AssetType.FOREX,
            AssetType.CRYPTO
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
        Fetch OHLCV from Alpha Vantage.

        Args:
            symbol: Ticker symbol (e.g., "AAPL", "BTCUSD" for crypto)
            interval: Candle interval (1m, 5m, 15m, 30m, 1h, 1d, 1w, 1mo)
            start: Start time (UTC) - Note: Alpha Vantage returns recent data only
            end: End time (UTC)
            limit: Max candles (optional, but Alpha Vantage returns fixed amounts)

        Returns:
            List of OHLCV candles

        Note: Alpha Vantage free tier returns:
        - Intraday (1m-1h): Last 100 data points
        - Daily: Full history or last 100 days (compact vs full)
        """
        # Map interval
        av_interval = self.INTERVAL_MAP.get(interval)
        if not av_interval:
            raise ValueError(
                f"Unsupported interval: {interval}. "
                f"Supported: {list(self.INTERVAL_MAP.keys())}"
            )

        try:
            # Determine function based on interval
            if av_interval in ["1min", "5min", "15min", "30min", "60min"]:
                function = "TIME_SERIES_INTRADAY"
                time_series_key = f"Time Series ({av_interval})"
            elif av_interval == "daily":
                function = "TIME_SERIES_DAILY"
                time_series_key = "Time Series (Daily)"
            elif av_interval == "weekly":
                function = "TIME_SERIES_WEEKLY"
                time_series_key = "Weekly Time Series"
            else:  # monthly
                function = "TIME_SERIES_MONTHLY"
                time_series_key = "Monthly Time Series"

            # Build request params
            params = {
                "function": function,
                "symbol": symbol.upper(),
                "apikey": self.api_key,
                "outputsize": "full",  # Get more history (up to 20 years for daily)
                "datatype": "json"
            }

            # Add interval for intraday
            if function == "TIME_SERIES_INTRADAY":
                params["interval"] = av_interval

            response = self.session.get(
                self.BASE_URL,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            # Check for API error messages
            if "Error Message" in data:
                raise ValueError(f"Alpha Vantage API error: {data['Error Message']}")
            if "Note" in data:
                logger.warning(f"Alpha Vantage rate limit: {data['Note']}")
                return []
            if time_series_key not in data:
                logger.warning(f"No time series data for {symbol} from Alpha Vantage")
                return []

            # Parse time series data
            time_series = data[time_series_key]
            candles = []

            for timestamp_str, ohlcv_data in time_series.items():
                # Parse timestamp
                try:
                    if " " in timestamp_str:  # Intraday format: "2021-01-01 16:00:00"
                        dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                    else:  # Daily format: "2021-01-01"
                        dt = datetime.strptime(timestamp_str, "%Y-%m-%d")

                    # Make timezone-aware (Alpha Vantage uses US/Eastern, convert to UTC)
                    dt = dt.replace(tzinfo=timezone.utc)
                    timestamp_ms = int(dt.timestamp() * 1000)

                    # Filter by date range
                    if dt < start or dt > end:
                        continue

                    candles.append(OHLCV(
                        timestamp=timestamp_ms,
                        open=float(ohlcv_data["1. open"]),
                        high=float(ohlcv_data["2. high"]),
                        low=float(ohlcv_data["3. low"]),
                        close=float(ohlcv_data["4. close"]),
                        volume=float(ohlcv_data["5. volume"]),
                        source=DataSourceType.ALPHA_VANTAGE,
                        symbol=symbol
                    ))

                except (KeyError, ValueError) as e:
                    logger.warning(f"Failed to parse OHLCV data point: {e}")
                    continue

            # Sort by timestamp (Alpha Vantage returns newest first)
            candles.sort(key=lambda c: c.timestamp)

            # Apply limit if specified
            if limit and len(candles) > limit:
                candles = candles[-limit:]  # Keep most recent

            logger.debug(
                f"Fetched {len(candles)} candles for {symbol} from Alpha Vantage"
            )
            return candles

        except Exception as e:
            logger.error(f"Alpha Vantage fetch failed for {symbol}: {e}")
            raise

    def fetch_quote(self, symbol: str) -> Quote:
        """
        Fetch current quote from Alpha Vantage.

        Args:
            symbol: Ticker symbol (e.g., "AAPL")

        Returns:
            Current quote
        """
        try:
            # Use GLOBAL_QUOTE endpoint for real-time quotes
            params = {
                "function": "GLOBAL_QUOTE",
                "symbol": symbol.upper(),
                "apikey": self.api_key,
                "datatype": "json"
            }

            response = self.session.get(
                self.BASE_URL,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            # Check for errors
            if "Error Message" in data:
                raise ValueError(f"Alpha Vantage API error: {data['Error Message']}")
            if "Note" in data:
                raise ValueError(f"Alpha Vantage rate limit: {data['Note']}")
            if "Global Quote" not in data:
                raise ValueError(f"No quote data for {symbol}")

            quote_data = data["Global Quote"]
            if not quote_data:
                raise ValueError(f"Empty quote data for {symbol}")

            quote = Quote(
                symbol=symbol,
                price=float(quote_data["05. price"]),
                volume_24h=float(quote_data.get("06. volume", 0)),
                timestamp=int(datetime.now(timezone.utc).timestamp() * 1000),
                source=DataSourceType.ALPHA_VANTAGE
            )

            return quote

        except Exception as e:
            logger.error(f"Alpha Vantage quote fetch failed for {symbol}: {e}")
            raise

    def normalize_symbol(self, symbol: str, asset_type: AssetType) -> str:
        """
        Normalize symbol to Alpha Vantage format.

        Args:
            symbol: Universal symbol
            asset_type: Asset type

        Returns:
            Alpha Vantage symbol

        Examples:
            AAPL → AAPL (stocks unchanged)
            BTC/USD → BTCUSD (crypto pairs)
            EUR/USD → EURUSD (forex pairs)
        """
        # Remove slashes and hyphens, convert to uppercase
        symbol = symbol.replace("/", "").replace("-", "").upper()

        # Crypto: Alpha Vantage uses format like "BTCUSD"
        if asset_type == AssetType.CRYPTO:
            # If already has USD/USDT, keep as-is (just remove /)
            if "USD" in symbol:
                return symbol.replace("USDT", "USD")  # Convert USDT to USD
            else:
                # Add USD suffix
                return f"{symbol}USD"

        # Forex: Keep as-is (already in EURUSD format after slash removal)
        # Stocks/ETF: Keep as-is
        return symbol

    def validate_connection(self) -> bool:
        """
        Test Alpha Vantage connection.

        Returns:
            True if connection successful
        """
        try:
            # Try to fetch a quote for SPY (always available)
            params = {
                "function": "GLOBAL_QUOTE",
                "symbol": "SPY",
                "apikey": self.api_key,
                "datatype": "json"
            }

            response = self.session.get(
                self.BASE_URL,
                params=params,
                timeout=self.timeout
            )

            if response.status_code != 200:
                return False

            data = response.json()

            # Check for valid response
            if "Error Message" in data:
                return False
            if "Note" in data:  # Rate limit hit
                logger.warning("Alpha Vantage rate limit reached")
                return False
            if "Global Quote" in data and data["Global Quote"]:
                return True

            return False

        except Exception as e:
            logger.error(f"Alpha Vantage connection test failed: {e}")
            return False
