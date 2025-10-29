"""Base data source adapter interface.

All data source implementations should inherit from this base class to ensure
consistent interface for fetching market data.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd


class DataSourceAdapter(ABC):
    """Base class for all data source adapters.

    This defines the interface that all data source implementations must follow.
    Data sources provide historical and real-time market data.
    """

    @abstractmethod
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """Fetch OHLCV (candlestick) data.

        Args:
            symbol: Trading pair (e.g., "BTC/USD")
            timeframe: Candle timeframe (e.g., "1m", "1h", "1d")
            start: Start datetime
            end: End datetime
            limit: Maximum number of candles

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        pass

    @abstractmethod
    async def fetch_ticker(self, symbol: str) -> Dict:
        """Fetch current ticker data.

        Args:
            symbol: Trading pair

        Returns:
            Dict with bid, ask, last, volume, etc.
        """
        pass

    @abstractmethod
    def supports_timeframe(self, timeframe: str) -> bool:
        """Check if timeframe is supported.

        Args:
            timeframe: Timeframe string (e.g., "1m", "1h")

        Returns:
            True if supported
        """
        pass

    @abstractmethod
    def get_supported_symbols(self) -> List[str]:
        """Get list of supported trading pairs.

        Returns:
            List of symbol strings
        """
        pass

    @abstractmethod
    def normalize_symbol(self, symbol: str) -> str:
        """Convert symbol to source-specific format.

        Args:
            symbol: Standard format (e.g., "BTC/USD")

        Returns:
            Source-specific format (e.g., "BTCUSD" for Binance)
        """
        pass

    @abstractmethod
    def get_rate_limit(self) -> int:
        """Get API rate limit (requests per minute).

        Returns:
            Max requests per minute
        """
        pass
