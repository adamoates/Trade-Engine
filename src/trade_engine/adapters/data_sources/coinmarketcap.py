"""
CoinMarketCap data source adapter.

Provides access to:
- Cryptocurrency prices (15,000+ assets)
- Market cap rankings
- 24h volume data
- Historical OHLCV quotes

Free tier: 10,000 API credits/month (333 calls/day).
API key required (free registration).
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional
from loguru import logger
import requests
import os
import time
from collections import deque

from trade_engine.services.data.types import (
    DataSource,
    DataSourceType,
    AssetType,
    OHLCV,
    Quote
)


class CoinMarketCapSource(DataSource):
    """
    CoinMarketCap API adapter.

    Free tier: 10,000 credits/month, 333 calls/day.
    Get API key: https://coinmarketcap.com/api/
    """

    BASE_URL = "https://pro-api.coinmarketcap.com/v1"
    SANDBOX_URL = "https://sandbox-api.coinmarketcap.com/v1"

    def __init__(self, api_key: Optional[str] = None, sandbox: bool = False, timeout: int = 10,
                 calls_per_minute: int = 30, calls_per_day: int = 333):
        """
        Initialize CoinMarketCap source.

        Args:
            api_key: CoinMarketCap API key (or set COINMARKETCAP_API_KEY env var)
            sandbox: Use sandbox for testing (default: False)
            timeout: Request timeout in seconds
            calls_per_minute: Max API calls per minute (default: 30, free tier safe limit)
            calls_per_day: Max API calls per day (default: 333, free tier limit)
        """
        self.api_key = api_key or os.getenv("COINMARKETCAP_API_KEY")
        if not self.api_key:
            raise ValueError(
                "CoinMarketCap API key required. "
                "Set COINMARKETCAP_API_KEY environment variable or pass api_key parameter. "
                "Get free key at: https://coinmarketcap.com/api/"
            )

        self.sandbox = sandbox
        self.timeout = timeout
        self.base_url = self.SANDBOX_URL if sandbox else self.BASE_URL

        # Rate limiting configuration
        self.calls_per_minute = calls_per_minute
        self.calls_per_day = calls_per_day
        self._minute_calls: deque = deque(maxlen=calls_per_minute)
        self._day_calls: deque = deque(maxlen=calls_per_day)

        self.session = requests.Session()
        self.session.headers.update({
            "X-CMC_PRO_API_KEY": self.api_key,
            "Accept": "application/json"
        })

    def __del__(self):
        """Clean up session on deletion."""
        if hasattr(self, 'session'):
            try:
                self.session.close()
            except Exception:
                pass

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if hasattr(self, 'session'):
            self.session.close()
        return False

    def _check_rate_limit(self) -> None:
        """
        Check and enforce rate limits.
        Raises ValueError if rate limit would be exceeded.
        """
        current_time = time.time()

        # Clean up old minute calls (older than 60 seconds)
        while self._minute_calls and current_time - self._minute_calls[0] > 60:
            self._minute_calls.popleft()

        # Clean up old day calls (older than 24 hours)
        while self._day_calls and current_time - self._day_calls[0] > 86400:
            self._day_calls.popleft()

        # Check minute limit
        if len(self._minute_calls) >= self.calls_per_minute:
            wait_time = 60 - (current_time - self._minute_calls[0])
            logger.warning(
                f"CoinMarketCap minute rate limit reached ({self.calls_per_minute} calls/min). "
                f"Wait {wait_time:.1f}s or reduce request frequency."
            )
            raise ValueError(
                f"Rate limit exceeded: {self.calls_per_minute} calls per minute. "
                f"Retry in {wait_time:.1f} seconds."
            )

        # Check day limit
        if len(self._day_calls) >= self.calls_per_day:
            wait_time = 86400 - (current_time - self._day_calls[0])
            logger.warning(
                f"CoinMarketCap daily rate limit reached ({self.calls_per_day} calls/day). "
                f"Wait {wait_time/3600:.1f}h or upgrade API plan."
            )
            raise ValueError(
                f"Rate limit exceeded: {self.calls_per_day} calls per day. "
                f"Retry in {wait_time/3600:.1f} hours."
            )

        # Record this call
        self._minute_calls.append(current_time)
        self._day_calls.append(current_time)

    @property
    def source_type(self) -> DataSourceType:
        return DataSourceType.COINMARKETCAP

    @property
    def supported_asset_types(self) -> List[AssetType]:
        return [AssetType.CRYPTO]

    def fetch_ohlcv(
        self,
        symbol: str,
        interval: str,
        start: datetime,
        end: datetime,
        limit: Optional[int] = None
    ) -> List[OHLCV]:
        """
        Fetch OHLCV from CoinMarketCap.

        Note: CoinMarketCap free tier has limited historical data access.
        OHLCV endpoint requires higher tier plans.
        This implementation returns empty for now.

        Args:
            symbol: Cryptocurrency symbol (e.g., "BTC", "ETH")
            interval: Not used (CoinMarketCap doesn't provide OHLCV in free tier)
            start: Start time
            end: End time
            limit: Max candles

        Returns:
            Empty list (OHLCV not available in free tier)
        """
        logger.warning(
            "CoinMarketCap OHLCV data requires paid plan. "
            "Use fetch_quote() for current prices."
        )
        return []

    def fetch_quote(self, symbol: str) -> Quote:
        """
        Fetch current quote from CoinMarketCap.

        Args:
            symbol: Cryptocurrency symbol (e.g., "BTC", "ETH")

        Returns:
            Current quote with price and volume

        Raises:
            ValueError: If rate limit exceeded or API error
        """
        try:
            # Check rate limit before making request
            self._check_rate_limit()

            # Use quotes endpoint for latest data
            endpoint = f"{self.base_url}/cryptocurrency/quotes/latest"
            params = {
                "symbol": symbol.upper(),
                "convert": "USD"
            }

            response = self.session.get(
                endpoint,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            # Check for API errors
            if data.get("status", {}).get("error_code") != 0:
                error_msg = data.get("status", {}).get("error_message", "Unknown error")
                raise ValueError(f"CoinMarketCap API error: {error_msg}")

            # Extract quote data
            symbol_data = data["data"][symbol.upper()]
            quote_data = symbol_data["quote"]["USD"]

            quote = Quote(
                symbol=symbol,
                price=float(quote_data["price"]),
                volume_24h=float(quote_data.get("volume_24h", 0)),
                timestamp=int(datetime.now(timezone.utc).timestamp() * 1000),
                source=self.source_type
            )

            return quote

        except Exception as e:
            logger.error(f"CoinMarketCap quote fetch failed for {symbol}: {e}")
            raise

    def normalize_symbol(self, symbol: str, asset_type: AssetType) -> str:
        """
        Normalize symbol to CoinMarketCap format.

        Args:
            symbol: Universal symbol
            asset_type: Must be CRYPTO

        Returns:
            CoinMarketCap symbol (uppercase, no suffixes)

        Examples:
            BTC/USDT → BTC
            btc-usd → BTC
            ethereum → ETH (requires mapping)
        """
        if asset_type != AssetType.CRYPTO:
            raise ValueError("CoinMarketCap only supports cryptocurrencies")

        # Remove common suffixes and separators
        symbol = symbol.replace("/", "").replace("-", "").upper()
        symbol = symbol.replace("USDT", "").replace("USD", "").replace("BUSD", "")

        # CoinMarketCap uses ticker symbols, not names
        # Common mappings (could be expanded)
        symbol_map = {
            "BITCOIN": "BTC",
            "ETHEREUM": "ETH",
            "TETHER": "USDT",
            "BINANCECOIN": "BNB",
            "CARDANO": "ADA",
            "SOLANA": "SOL",
            "RIPPLE": "XRP",
            "POLKADOT": "DOT",
            "DOGECOIN": "DOGE"
        }

        return symbol_map.get(symbol, symbol)

    def validate_connection(self) -> bool:
        """
        Test CoinMarketCap connection.

        Returns:
            True if connection successful
        """
        try:
            # Check rate limit before making request
            self._check_rate_limit()

            # Use key info endpoint to validate
            endpoint = f"{self.base_url}/key/info"

            response = self.session.get(
                endpoint,
                timeout=self.timeout
            )

            if response.status_code != 200:
                return False

            data = response.json()

            # Check if API key is valid
            if data.get("status", {}).get("error_code") == 0:
                return True

            return False

        except Exception as e:
            logger.error(f"CoinMarketCap connection test failed: {e}")
            return False
