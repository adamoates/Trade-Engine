"""
Data source interfaces and common types.

Defines abstract base class for data sources and shared data structures.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from enum import Enum


class AssetType(Enum):
    """Asset type classification."""
    CRYPTO = "crypto"
    STOCK = "stock"
    ETF = "etf"
    INDEX = "index"
    FOREX = "forex"
    COMMODITY = "commodity"


class DataSourceType(Enum):
    """Data source provider."""
    BINANCE = "binance"
    YAHOO_FINANCE = "yahoo"
    COINGECKO = "coingecko"
    ALPHA_VANTAGE = "alphavantage"
    TRADINGVIEW = "tradingview"
    INVESTING_COM = "investing"


@dataclass
class OHLCV:
    """
    OHLCV candle data (normalized across sources).

    All prices in quote currency (USD, USDT, etc.)
    """
    timestamp: int          # UTC timestamp (milliseconds)
    open: float
    high: float
    low: float
    close: float
    volume: float
    source: DataSourceType  # Where this data came from
    symbol: str             # Original symbol from source

    @property
    def datetime_utc(self) -> datetime:
        """Convert timestamp to datetime (UTC)."""
        return datetime.utcfromtimestamp(self.timestamp / 1000)

    def __repr__(self):
        return (f"OHLCV({self.datetime_utc.isoformat()}, O={self.open:.2f}, "
                f"H={self.high:.2f}, L={self.low:.2f}, C={self.close:.2f}, "
                f"V={self.volume:.2f}, src={self.source.value})")


@dataclass
class Quote:
    """
    Real-time quote data.

    For live price checks and cross-validation.
    """
    symbol: str
    price: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume_24h: Optional[float] = None
    timestamp: Optional[int] = None
    source: Optional[DataSourceType] = None

    @property
    def spread(self) -> Optional[float]:
        """Bid-ask spread in basis points."""
        if self.bid and self.ask and self.bid > 0:
            return ((self.ask - self.bid) / self.bid) * 10000
        return None


@dataclass
class DataQualityMetrics:
    """
    Data quality assessment.

    Used to compare sources and detect issues.
    """
    source: DataSourceType
    symbol: str
    rows: int
    missing_bars: int
    zero_volume_bars: int
    price_anomalies: int      # Spikes > 10% from moving average
    duplicate_timestamps: int
    gaps_seconds_total: int   # Total seconds of missing data
    avg_spread_bps: Optional[float] = None

    @property
    def quality_score(self) -> float:
        """
        Quality score 0-100 (higher = better).

        Penalizes missing data, anomalies, gaps.
        """
        if self.rows == 0:
            return 0.0

        missing_pct = (self.missing_bars / self.rows) * 100
        zero_vol_pct = (self.zero_volume_bars / self.rows) * 100
        anomaly_pct = (self.price_anomalies / self.rows) * 100

        score = 100.0
        score -= missing_pct * 2  # Missing data is bad
        score -= zero_vol_pct * 1.5
        score -= anomaly_pct * 3  # Price spikes are very bad

        return max(0.0, score)


class DataSource(ABC):
    """
    Abstract data source interface.

    All data adapters (Binance, Yahoo, etc.) implement this interface.
    """

    @property
    @abstractmethod
    def source_type(self) -> DataSourceType:
        """Return the data source type."""
        pass

    @property
    @abstractmethod
    def supported_asset_types(self) -> List[AssetType]:
        """Return list of supported asset types."""
        pass

    @abstractmethod
    def fetch_ohlcv(
        self,
        symbol: str,
        interval: str,
        start: datetime,
        end: datetime,
        limit: Optional[int] = None
    ) -> List[OHLCV]:
        """
        Fetch OHLCV candles.

        Args:
            symbol: Trading pair/ticker (e.g., "BTCUSDT", "AAPL", "SPY")
            interval: Candle interval (e.g., "1m", "5m", "1h", "1d")
            start: Start time (UTC)
            end: End time (UTC)
            limit: Max number of candles (optional)

        Returns:
            List of OHLCV candles

        Raises:
            ValueError: If symbol not supported
            requests.HTTPError: If API request fails
        """
        pass

    @abstractmethod
    def fetch_quote(self, symbol: str) -> Quote:
        """
        Fetch current quote (real-time price).

        Args:
            symbol: Trading pair/ticker

        Returns:
            Current quote with bid/ask if available
        """
        pass

    @abstractmethod
    def normalize_symbol(self, symbol: str, asset_type: AssetType) -> str:
        """
        Normalize symbol to source-specific format.

        Args:
            symbol: Universal symbol (e.g., "BTC/USDT", "BTC-USD")
            asset_type: Asset type hint

        Returns:
            Source-specific symbol (e.g., "BTCUSDT" for Binance)
        """
        pass

    @abstractmethod
    def validate_connection(self) -> bool:
        """
        Test connection to data source.

        Returns:
            True if connection successful
        """
        pass
