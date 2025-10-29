"""
CoinGecko data source adapter.

Provides access to:
- Cryptocurrency prices
- Market cap data
- Historical OHLCV
- 24h volume

Free API (rate limited: 10-50 calls/minute depending on plan).
No API key required for public endpoints.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional
from loguru import logger
import requests

from trade_engine.services.data.types import (
    DataSource,
    DataSourceType,
    AssetType,
    OHLCV,
    Quote
)


class CoinGeckoSource(DataSource):
    """
    CoinGecko API adapter.

    Free tier: 10-50 calls/minute
    """

    BASE_URL = "https://api.coingecko.com/api/v3"

    # Interval mapping for OHLCV
    INTERVAL_MAP = {
        "1d": "daily",
        "1h": "hourly"  # CoinGecko only supports daily and hourly for free tier
    }

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize CoinGecko source.

        Args:
            api_key: Optional API key for higher rate limits (Pro/Enterprise)
        """
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "MFT-DataAggregator/1.0"
        })

        if api_key:
            self.session.headers.update({"x-cg-pro-api-key": api_key})

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
        return DataSourceType.COINGECKO

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
        Fetch OHLCV from CoinGecko.

        Note: CoinGecko free tier only supports daily and hourly data.
        For minute-level data, use Binance or other sources.

        Args:
            symbol: Coin ID (e.g., "bitcoin", "ethereum")
            interval: "1d" or "1h"
            start: Start time
            end: End time
            limit: Max candles (optional)

        Returns:
            List of OHLCV candles
        """
        if interval not in self.INTERVAL_MAP:
            raise ValueError(
                f"CoinGecko only supports intervals: {list(self.INTERVAL_MAP.keys())}"
            )

        try:
            # CoinGecko uses coin IDs, not symbols
            coin_id = self._symbol_to_coin_id(symbol)

            # Calculate days range
            days = (end - start).days
            if days < 1:
                days = 1

            # Fetch market chart data
            endpoint = f"{self.BASE_URL}/coins/{coin_id}/market_chart"
            params = {
                "vs_currency": "usd",
                "days": days,
                "interval": self.INTERVAL_MAP[interval]
            }

            response = self.session.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Convert to OHLCV (CoinGecko returns price, market_cap, volume)
            candles = []
            prices = data.get("prices", [])
            volumes = data.get("total_volumes", [])

            # CoinGecko doesn't provide OHLC, only closing prices
            # We'll create synthetic OHLC where O=H=L=C (suboptimal but better than nothing)
            for i, (ts, price) in enumerate(prices):
                volume = volumes[i][1] if i < len(volumes) else 0

                candles.append(OHLCV(
                    timestamp=int(ts),
                    open=price,
                    high=price,
                    low=price,
                    close=price,
                    volume=volume,
                    source=DataSourceType.COINGECKO,
                    symbol=coin_id
                ))

            logger.debug(f"Fetched {len(candles)} candles for {coin_id} from CoinGecko")
            return candles[:limit] if limit else candles

        except Exception as e:
            logger.error(f"CoinGecko fetch failed for {symbol}: {e}")
            raise

    def fetch_quote(self, symbol: str) -> Quote:
        """
        Fetch current quote from CoinGecko.

        Args:
            symbol: Coin ID or symbol

        Returns:
            Current quote
        """
        try:
            coin_id = self._symbol_to_coin_id(symbol)

            endpoint = f"{self.BASE_URL}/simple/price"
            params = {
                "ids": coin_id,
                "vs_currencies": "usd",
                "include_24hr_vol": "true",
                "include_last_updated_at": "true"
            }

            response = self.session.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if coin_id not in data:
                raise ValueError(f"No data for {coin_id}")

            coin_data = data[coin_id]

            quote = Quote(
                symbol=coin_id,
                price=float(coin_data["usd"]),
                volume_24h=coin_data.get("usd_24h_vol"),
                timestamp=coin_data.get("last_updated_at", int(datetime.now(timezone.utc).timestamp())) * 1000,
                source=DataSourceType.COINGECKO
            )

            return quote

        except Exception as e:
            logger.error(f"CoinGecko quote fetch failed for {symbol}: {e}")
            raise

    def normalize_symbol(self, symbol: str, asset_type: AssetType) -> str:
        """
        Normalize symbol to CoinGecko coin ID.

        Args:
            symbol: Symbol (e.g., "BTC", "BTCUSDT", "ETH")
            asset_type: Must be CRYPTO

        Returns:
            CoinGecko coin ID (e.g., "bitcoin", "ethereum")
        """
        if asset_type != AssetType.CRYPTO:
            raise ValueError("CoinGecko only supports cryptocurrencies")

        return self._symbol_to_coin_id(symbol)

    def _symbol_to_coin_id(self, symbol: str) -> str:
        """
        Convert trading symbol to CoinGecko coin ID.

        Args:
            symbol: Trading symbol (e.g., "BTC", "BTCUSDT", "ETH-USD")

        Returns:
            CoinGecko coin ID (e.g., "bitcoin", "ethereum")
        """
        # Remove common suffixes
        symbol = symbol.replace("USDT", "").replace("USD", "").replace("-", "").replace("/", "").upper()

        # Common mappings
        symbol_map = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "USDT": "tether",
            "BNB": "binancecoin",
            "SOL": "solana",
            "XRP": "ripple",
            "ADA": "cardano",
            "DOGE": "dogecoin",
            "DOT": "polkadot",
            "MATIC": "matic-network",
            "AVAX": "avalanche-2",
            "UNI": "uniswap",
            "LINK": "chainlink"
        }

        coin_id = symbol_map.get(symbol)
        if not coin_id:
            # Try lowercase as coin ID (works for many coins)
            coin_id = symbol.lower()

        return coin_id

    def validate_connection(self) -> bool:
        """
        Test CoinGecko connection.

        Returns:
            True if connection successful
        """
        try:
            endpoint = f"{self.BASE_URL}/ping"
            response = self.session.get(endpoint, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"CoinGecko connection test failed: {e}")
            return False
