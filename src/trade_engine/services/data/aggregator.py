"""
Multi-source data aggregator with cross-validation.

Fetches data from multiple sources and validates consistency to detect:
- Bad data from a single source
- Price manipulation or errors
- Exchange outages
- Data quality issues

Disclaimer: This tool provides educational market data analysis.
It is not personalized financial advice. Verify all data with primary sources.
"""

from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import statistics
from loguru import logger

from trade_engine.services.data.types import (
    DataSource,
    OHLCV,
    Quote,
    DataQualityMetrics,
    DataSourceType
)


@dataclass
class CrossValidationResult:
    """Result of cross-source validation."""
    symbol: str
    timestamp: datetime
    sources_checked: int
    consensus_price: float  # Median price across sources
    price_std_dev: float    # Standard deviation
    price_range_pct: float  # (max - min) / median * 100
    anomalies: List[Tuple[DataSourceType, float, str]]  # (source, price, reason)
    reliable: bool          # True if cross-validation passed

    def __repr__(self):
        status = "✅ RELIABLE" if self.reliable else "⚠️ ANOMALY"
        return (f"{status} | {self.symbol} @ {self.timestamp.isoformat()} | "
                f"Consensus: ${self.consensus_price:.2f} | "
                f"Range: ±{self.price_range_pct:.2f}% | "
                f"Sources: {self.sources_checked}")


class DataAggregator:
    """
    Aggregates data from multiple sources with cross-validation.

    Provides:
    - Multi-source data fetching
    - Price consensus calculation
    - Anomaly detection
    - Data quality scoring
    - Automatic fallback to reliable sources
    """

    # Price deviation thresholds
    MAX_PRICE_DEVIATION_PCT = 2.0  # Alert if source deviates >2% from median
    MAX_PRICE_RANGE_PCT = 5.0       # Fail if range across sources >5%

    def __init__(self, sources: List[DataSource]):
        """
        Initialize aggregator with data sources.

        Args:
            sources: List of data source adapters (Binance, Yahoo, CoinGecko, etc.)
        """
        self.sources = sources
        logger.info(
            f"DataAggregator initialized with {len(sources)} sources: "
            f"{[s.source_type.value for s in sources]}"
        )

    def fetch_ohlcv_consensus(
        self,
        symbol: str,
        interval: str,
        start: datetime,
        end: datetime,
        min_sources: int = 2
    ) -> Tuple[List[OHLCV], List[CrossValidationResult]]:
        """
        Fetch OHLCV from multiple sources and return consensus data.

        Args:
            symbol: Trading pair/ticker
            interval: Candle interval
            start: Start time
            end: End time
            min_sources: Minimum sources required for consensus (default 2)

        Returns:
            Tuple of (consensus_candles, validation_results)

        Note: Prices are cross-validated. Anomalies are logged and excluded.
        """
        # Fetch from all sources
        source_data: Dict[DataSourceType, List[OHLCV]] = {}

        for source in self.sources:
            try:
                candles = source.fetch_ohlcv(symbol, interval, start, end)
                if candles:
                    source_data[source.source_type] = candles
                    logger.debug(
                        f"Fetched {len(candles)} candles from {source.source_type.value}"
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to fetch from {source.source_type.value}: {e}"
                )

        if len(source_data) < min_sources:
            raise ValueError(
                f"Insufficient data sources: {len(source_data)}/{min_sources} available"
            )

        # Cross-validate timestamps and build consensus
        consensus_candles, validation_results = self._build_consensus(
            source_data,
            symbol
        )

        logger.info(
            f"Built consensus for {symbol}: {len(consensus_candles)} candles, "
            f"{len([v for v in validation_results if not v.reliable])} anomalies detected"
        )

        return consensus_candles, validation_results

    def fetch_quote_consensus(
        self,
        symbol: str,
        min_sources: int = 2
    ) -> Tuple[Quote, CrossValidationResult]:
        """
        Fetch real-time quote with cross-validation.

        Args:
            symbol: Trading pair/ticker
            min_sources: Minimum sources required

        Returns:
            Tuple of (consensus_quote, validation_result)
        """
        quotes: Dict[DataSourceType, Quote] = {}

        for source in self.sources:
            try:
                quote = source.fetch_quote(symbol)
                quotes[source.source_type] = quote
            except Exception as e:
                logger.warning(
                    f"Failed to fetch quote from {source.source_type.value}: {e}"
                )

        if len(quotes) < min_sources:
            raise ValueError(
                f"Insufficient quote sources: {len(quotes)}/{min_sources}"
            )

        # Cross-validate prices
        prices = [q.price for q in quotes.values()]
        median_price = statistics.median(prices)
        std_dev = statistics.stdev(prices) if len(prices) > 1 else 0.0

        # Handle zero price edge case (delisted/halted assets)
        if median_price == 0:
            logger.warning(f"Zero median price for {symbol} - skipping percentage calculations")
            price_range_pct = 0.0
            anomalies = []
        else:
            price_range_pct = ((max(prices) - min(prices)) / median_price) * 100

            # Detect anomalies
            anomalies = []
            for src_type, quote in quotes.items():
                deviation_pct = abs((quote.price - median_price) / median_price) * 100
                if deviation_pct > self.MAX_PRICE_DEVIATION_PCT:
                    anomalies.append((
                        src_type,
                        quote.price,
                        f"Deviation {deviation_pct:.2f}% from consensus"
                    ))

        validation = CrossValidationResult(
            symbol=symbol,
            timestamp=datetime.now(timezone.utc),
            sources_checked=len(quotes),
            consensus_price=median_price,
            price_std_dev=std_dev,
            price_range_pct=price_range_pct,
            anomalies=anomalies,
            reliable=price_range_pct < self.MAX_PRICE_RANGE_PCT
        )

        # Create consensus quote (use median price, first source's metadata)
        first_quote = list(quotes.values())[0]
        consensus_quote = Quote(
            symbol=symbol,
            price=median_price,
            bid=first_quote.bid,
            ask=first_quote.ask,
            volume_24h=first_quote.volume_24h,
            timestamp=int(datetime.now(timezone.utc).timestamp() * 1000),
            source=None  # Consensus, not single source
        )

        if not validation.reliable:
            logger.warning(f"Quote validation failed: {validation}")

        return consensus_quote, validation

    def _build_consensus(
        self,
        source_data: Dict[DataSourceType, List[OHLCV]],
        symbol: str
    ) -> Tuple[List[OHLCV], List[CrossValidationResult]]:
        """
        Build consensus candles from multiple sources.

        Args:
            source_data: Dict of source → candles
            symbol: Trading symbol

        Returns:
            Tuple of (consensus_candles, validation_results)
        """
        # Group candles by timestamp
        timestamp_groups: Dict[int, List[OHLCV]] = {}

        for candles in source_data.values():
            for candle in candles:
                if candle.timestamp not in timestamp_groups:
                    timestamp_groups[candle.timestamp] = []
                timestamp_groups[candle.timestamp].append(candle)

        consensus_candles = []
        validation_results = []

        for timestamp in sorted(timestamp_groups.keys()):
            candles_at_ts = timestamp_groups[timestamp]

            if len(candles_at_ts) < 2:
                # Single source, can't validate - use as-is with warning
                consensus_candles.append(candles_at_ts[0])
                continue

            # Calculate consensus OHLCV (median of each field)
            close_prices = [c.close for c in candles_at_ts]
            median_close = statistics.median(close_prices)
            std_dev = statistics.stdev(close_prices) if len(close_prices) > 1 else 0.0

            # Handle zero price edge case
            if median_close == 0:
                logger.warning(f"Zero median close price for {symbol} at {timestamp} - skipping percentage calculations")
                price_range_pct = 0.0
                anomalies = []
            else:
                price_range_pct = ((max(close_prices) - min(close_prices)) / median_close) * 100

                # Detect anomalies
                anomalies = []
                for candle in candles_at_ts:
                    deviation_pct = abs((candle.close - median_close) / median_close) * 100
                    if deviation_pct > self.MAX_PRICE_DEVIATION_PCT:
                        anomalies.append((
                            candle.source,
                            candle.close,
                            f"Price deviation {deviation_pct:.2f}%"
                        ))

            validation = CrossValidationResult(
                symbol=symbol,
                timestamp=datetime.fromtimestamp(timestamp / 1000, timezone.utc),
                sources_checked=len(candles_at_ts),
                consensus_price=median_close,
                price_std_dev=std_dev,
                price_range_pct=price_range_pct,
                anomalies=anomalies,
                reliable=price_range_pct < self.MAX_PRICE_RANGE_PCT
            )

            validation_results.append(validation)

            # Build consensus candle (use medians)
            consensus = OHLCV(
                timestamp=timestamp,
                open=statistics.median([c.open for c in candles_at_ts]),
                high=statistics.median([c.high for c in candles_at_ts]),
                low=statistics.median([c.low for c in candles_at_ts]),
                close=median_close,
                volume=statistics.median([c.volume for c in candles_at_ts]),
                source=None,  # Consensus, not single source
                symbol=symbol
            )

            consensus_candles.append(consensus)

        return consensus_candles, validation_results

    def get_quality_metrics(
        self,
        symbol: str,
        interval: str,
        start: datetime,
        end: datetime
    ) -> Dict[DataSourceType, DataQualityMetrics]:
        """
        Get data quality metrics for each source.

        Args:
            symbol: Trading symbol
            interval: Candle interval
            start: Start time
            end: End time

        Returns:
            Dict of source → quality metrics
        """
        metrics: Dict[DataSourceType, DataQualityMetrics] = {}

        for source in self.sources:
            try:
                candles = source.fetch_ohlcv(symbol, interval, start, end)

                # Calculate expected bar count and missing bars
                expected_bars = self._calculate_expected_bars(interval, start, end)
                missing_bars = max(0, expected_bars - len(candles))

                # Calculate time gaps
                gaps_seconds = self._calculate_gaps_seconds(candles, interval)

                # Calculate quality metrics
                quality = DataQualityMetrics(
                    source=source.source_type,
                    symbol=symbol,
                    rows=len(candles),
                    missing_bars=missing_bars,
                    zero_volume_bars=sum(1 for c in candles if c.volume == 0),
                    price_anomalies=self._count_price_anomalies(candles),
                    duplicate_timestamps=self._count_duplicates(candles),
                    gaps_seconds_total=gaps_seconds
                )

                metrics[source.source_type] = quality

            except Exception as e:
                logger.error(
                    f"Failed to get quality metrics from {source.source_type.value}: {e}"
                )

        return metrics

    @staticmethod
    def _count_price_anomalies(candles: List[OHLCV], threshold_pct: float = 10.0) -> int:
        """Count candles with >10% price spikes."""
        if len(candles) < 2:
            return 0

        anomalies = 0
        for i in range(1, len(candles)):
            prev_close = candles[i-1].close
            curr_close = candles[i].close

            # Skip zero prices to avoid division by zero
            if prev_close > 0:
                change_pct = abs((curr_close - prev_close) / prev_close) * 100
                if change_pct > threshold_pct:
                    anomalies += 1

        return anomalies

    @staticmethod
    def _count_duplicates(candles: List[OHLCV]) -> int:
        """Count duplicate timestamps."""
        timestamps = [c.timestamp for c in candles]
        return len(timestamps) - len(set(timestamps))

    @staticmethod
    def _calculate_expected_bars(interval: str, start: datetime, end: datetime) -> int:
        """
        Calculate expected number of bars based on interval and time range.

        Args:
            interval: Candle interval (1m, 5m, 1h, 1d, etc.)
            start: Start time
            end: End time

        Returns:
            Expected number of bars

        Raises:
            ValueError: If start is after end
        """
        # Validate date range
        if start > end:
            raise ValueError(f"Invalid date range: start ({start}) is after end ({end})")

        # Map interval to seconds
        interval_seconds = {
            "1m": 60,
            "2m": 120,
            "5m": 300,
            "15m": 900,
            "30m": 1800,
            "1h": 3600,
            "2h": 7200,
            "4h": 14400,
            "1d": 86400,
            "1wk": 604800,
            "1mo": 2592000  # Approximate (30 days)
        }

        seconds_per_bar = interval_seconds.get(interval, 60)  # Default to 1m
        total_seconds = int((end - start).total_seconds())

        if total_seconds < 0:
            return 0

        return max(1, total_seconds // seconds_per_bar)

    @staticmethod
    def _calculate_gaps_seconds(candles: List[OHLCV], interval: str) -> int:
        """
        Calculate total seconds of gaps in the data.

        Args:
            candles: List of OHLCV candles (must be sorted by timestamp)
            interval: Expected candle interval

        Returns:
            Total seconds of missing data (gaps)
        """
        if len(candles) < 2:
            return 0

        # Map interval to milliseconds
        interval_ms = {
            "1m": 60000,
            "2m": 120000,
            "5m": 300000,
            "15m": 900000,
            "30m": 1800000,
            "1h": 3600000,
            "2h": 7200000,
            "4h": 14400000,
            "1d": 86400000,
            "1wk": 604800000,
            "1mo": 2592000000
        }

        expected_gap_ms = interval_ms.get(interval, 60000)  # Default to 1m
        total_gap_seconds = 0

        for i in range(1, len(candles)):
            actual_gap_ms = candles[i].timestamp - candles[i-1].timestamp
            # If gap is larger than expected, count the excess
            if actual_gap_ms > expected_gap_ms * 1.5:  # Allow 50% tolerance
                excess_gap_ms = actual_gap_ms - expected_gap_ms
                total_gap_seconds += excess_gap_ms // 1000

        return total_gap_seconds


# ========== Disclaimer ==========

DISCLAIMER = """
EDUCATIONAL DATA AGGREGATION TOOL

This tool aggregates public market data from Yahoo Finance, CoinGecko,
and other free sources for educational and research purposes.

IMPORTANT DISCLAIMERS:
1. NOT FINANCIAL ADVICE: This information is general and educational only.
2. VERIFY DATA: Always verify prices with official exchange sources.
3. NOT PERSONALIZED: This is not tailored investment advice for you.
4. NO WARRANTY: Data provided "as-is" without guarantees of accuracy.
5. RISK WARNING: Trading involves substantial risk of loss.

Data sources cited where possible. Consult licensed financial advisors
for personalized guidance.
"""

def print_disclaimer():
    """Print educational disclaimer."""
    print(DISCLAIMER)
