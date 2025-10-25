"""Unit tests for multi-source data aggregation."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch
import statistics

from mft.services.data.types import (
    DataSource,
    DataSourceType,
    AssetType,
    OHLCV,
    Quote,
    DataQualityMetrics
)
from mft.services.data.aggregator import DataAggregator, CrossValidationResult


class MockDataSource(DataSource):
    """Mock data source for testing."""

    def __init__(self, source_type: DataSourceType, return_data=None):
        self._source_type = source_type
        self._return_data = return_data or []

    @property
    def source_type(self) -> DataSourceType:
        return self._source_type

    @property
    def supported_asset_types(self):
        return [AssetType.CRYPTO]

    def fetch_ohlcv(self, symbol, interval, start, end, limit=None):
        return self._return_data

    def fetch_quote(self, symbol):
        if isinstance(self._return_data, Quote):
            return self._return_data
        raise ValueError("No quote data")

    def normalize_symbol(self, symbol, asset_type):
        return symbol.upper()

    def validate_connection(self):
        return True


class TestDataAggregatorInit:
    """Test DataAggregator initialization."""

    def test_aggregator_initializes_with_sources(self):
        """Test aggregator accepts list of sources."""
        # ARRANGE
        source1 = MockDataSource(DataSourceType.BINANCE)
        source2 = MockDataSource(DataSourceType.YAHOO_FINANCE)

        # ACT
        aggregator = DataAggregator([source1, source2])

        # ASSERT
        assert len(aggregator.sources) == 2
        assert aggregator.sources[0].source_type == DataSourceType.BINANCE
        assert aggregator.sources[1].source_type == DataSourceType.YAHOO_FINANCE

    def test_aggregator_requires_at_least_one_source(self):
        """Test aggregator with empty source list."""
        # ACT
        aggregator = DataAggregator([])

        # ASSERT
        assert len(aggregator.sources) == 0


class TestQuoteConsensus:
    """Test real-time quote consensus calculation."""

    def test_quote_consensus_with_two_agreeing_sources(self):
        """Test consensus when sources agree."""
        # ARRANGE
        quote1 = Quote(symbol="BTC", price=66500.0, source=DataSourceType.BINANCE)
        quote2 = Quote(symbol="BTC", price=66520.0, source=DataSourceType.YAHOO_FINANCE)

        source1 = MockDataSource(DataSourceType.BINANCE, quote1)
        source2 = MockDataSource(DataSourceType.YAHOO_FINANCE, quote2)

        aggregator = DataAggregator([source1, source2])

        # ACT
        consensus_quote, validation = aggregator.fetch_quote_consensus("BTC", min_sources=2)

        # ASSERT
        # Consensus should be median of 66500 and 66520 = 66510
        assert consensus_quote.price == 66510.0
        assert validation.sources_checked == 2
        assert validation.reliable  # Price range <5%

    def test_quote_consensus_detects_anomaly(self):
        """Test anomaly detection when sources disagree significantly."""
        # ARRANGE
        quote1 = Quote(symbol="BTC", price=66000.0, source=DataSourceType.BINANCE)
        quote2 = Quote(symbol="BTC", price=70000.0, source=DataSourceType.COINGECKO)  # 6% higher

        source1 = MockDataSource(DataSourceType.BINANCE, quote1)
        source2 = MockDataSource(DataSourceType.COINGECKO, quote2)

        aggregator = DataAggregator([source1, source2])

        # ACT
        consensus_quote, validation = aggregator.fetch_quote_consensus("BTC", min_sources=2)

        # ASSERT
        assert not validation.reliable  # Should fail reliability check (>5% range)
        assert len(validation.anomalies) > 0  # Should detect anomaly

    def test_quote_consensus_fails_with_insufficient_sources(self):
        """Test that consensus requires minimum sources."""
        # ARRANGE
        quote1 = Quote(symbol="BTC", price=66000.0, source=DataSourceType.BINANCE)
        source1 = MockDataSource(DataSourceType.BINANCE, quote1)

        aggregator = DataAggregator([source1])

        # ACT & ASSERT
        with pytest.raises(ValueError, match="Insufficient quote sources"):
            aggregator.fetch_quote_consensus("BTC", min_sources=2)


class TestOHLCVConsensus:
    """Test historical OHLCV consensus calculation."""

    def test_ohlcv_consensus_with_matching_timestamps(self):
        """Test consensus when sources have matching timestamps."""
        # ARRANGE
        ts = int(datetime.now(timezone.utc).timestamp() * 1000)

        candles1 = [
            OHLCV(ts, 100.0, 105.0, 99.0, 102.0, 1000.0, DataSourceType.BINANCE, "BTC"),
            OHLCV(ts + 60000, 102.0, 107.0, 101.0, 105.0, 1100.0, DataSourceType.BINANCE, "BTC")
        ]

        candles2 = [
            OHLCV(ts, 100.5, 105.5, 98.5, 102.5, 1020.0, DataSourceType.YAHOO_FINANCE, "BTC"),
            OHLCV(ts + 60000, 102.5, 107.5, 100.5, 105.5, 1120.0, DataSourceType.YAHOO_FINANCE, "BTC")
        ]

        source1 = MockDataSource(DataSourceType.BINANCE, candles1)
        source2 = MockDataSource(DataSourceType.YAHOO_FINANCE, candles2)

        aggregator = DataAggregator([source1, source2])

        start = datetime.fromtimestamp(ts / 1000, timezone.utc)
        end = start + timedelta(minutes=5)

        # ACT
        consensus_candles, validations = aggregator.fetch_ohlcv_consensus(
            "BTC", "1m", start, end, min_sources=2
        )

        # ASSERT
        assert len(consensus_candles) == 2
        # Consensus should be median of close prices
        assert consensus_candles[0].close == statistics.median([102.0, 102.5])
        assert len(validations) == 2

    def test_ohlcv_consensus_detects_price_anomaly(self):
        """Test detection of abnormal price in one source."""
        # ARRANGE
        ts = int(datetime.now(timezone.utc).timestamp() * 1000)

        candles1 = [
            OHLCV(ts, 100.0, 105.0, 99.0, 102.0, 1000.0, DataSourceType.BINANCE, "BTC")
        ]

        candles2 = [
            OHLCV(ts, 100.0, 105.0, 99.0, 110.0, 1000.0, DataSourceType.YAHOO_FINANCE, "BTC")  # 8% spike
        ]

        source1 = MockDataSource(DataSourceType.BINANCE, candles1)
        source2 = MockDataSource(DataSourceType.YAHOO_FINANCE, candles2)

        aggregator = DataAggregator([source1, source2])

        start = datetime.fromtimestamp(ts / 1000, timezone.utc)
        end = start + timedelta(minutes=5)

        # ACT
        consensus_candles, validations = aggregator.fetch_ohlcv_consensus(
            "BTC", "1m", start, end, min_sources=2
        )

        # ASSERT
        assert len(validations) == 1
        # Should detect anomaly (>2% deviation)
        assert len(validations[0].anomalies) > 0


class TestDataQualityMetrics:
    """Test data quality assessment."""

    def test_quality_score_calculation(self):
        """Test quality score formula."""
        # ARRANGE - High quality data
        metrics_good = DataQualityMetrics(
            source=DataSourceType.BINANCE,
            symbol="BTC",
            rows=1000,
            missing_bars=0,
            zero_volume_bars=0,
            price_anomalies=0,
            duplicate_timestamps=0,
            gaps_seconds_total=0
        )

        # ACT
        score = metrics_good.quality_score

        # ASSERT
        assert score == 100.0  # Perfect score

    def test_quality_score_penalizes_issues(self):
        """Test quality score with data issues."""
        # ARRANGE - Poor quality data
        metrics_poor = DataQualityMetrics(
            source=DataSourceType.BINANCE,
            symbol="BTC",
            rows=1000,
            missing_bars=100,  # 10% missing
            zero_volume_bars=50,  # 5% zero volume
            price_anomalies=20,  # 2% anomalies
            duplicate_timestamps=10,
            gaps_seconds_total=3600
        )

        # ACT
        score = metrics_poor.quality_score

        # ASSERT
        assert score < 80.0  # Should be significantly penalized
        assert score > 0.0   # But not zero

    def test_get_quality_metrics_for_sources(self):
        """Test quality metrics calculation for each source."""
        # ARRANGE
        candles = [
            OHLCV(1000, 100.0, 105.0, 99.0, 102.0, 1000.0, DataSourceType.BINANCE, "BTC"),
            OHLCV(2000, 102.0, 107.0, 101.0, 105.0, 0.0, DataSourceType.BINANCE, "BTC"),  # Zero volume
        ]

        source = MockDataSource(DataSourceType.BINANCE, candles)
        aggregator = DataAggregator([source])

        start = datetime.now(timezone.utc) - timedelta(days=1)
        end = datetime.now(timezone.utc)

        # ACT
        metrics = aggregator.get_quality_metrics("BTC", "1m", start, end)

        # ASSERT
        assert DataSourceType.BINANCE in metrics
        quality = metrics[DataSourceType.BINANCE]
        assert quality.rows == 2
        assert quality.zero_volume_bars == 1


class TestCrossValidationResult:
    """Test CrossValidationResult dataclass."""

    def test_cross_validation_result_repr(self):
        """Test string representation."""
        # ARRANGE
        result = CrossValidationResult(
            symbol="BTC",
            timestamp=datetime(2025, 10, 23, 12, 0, 0),
            sources_checked=3,
            consensus_price=66500.0,
            price_std_dev=50.0,
            price_range_pct=0.15,
            anomalies=[],
            reliable=True
        )

        # ACT
        repr_str = repr(result)

        # ASSERT
        assert "✅ RELIABLE" in repr_str
        assert "BTC" in repr_str
        assert "$66500.00" in repr_str
        assert "Sources: 3" in repr_str

    def test_cross_validation_shows_anomaly_status(self):
        """Test unreliable data is flagged."""
        # ARRANGE
        result = CrossValidationResult(
            symbol="BTC",
            timestamp=datetime.now(timezone.utc),
            sources_checked=2,
            consensus_price=66500.0,
            price_std_dev=2000.0,
            price_range_pct=6.0,  # >5% = unreliable
            anomalies=[(DataSourceType.BINANCE, 70000.0, "Deviation 5.3%")],
            reliable=False
        )

        # ACT
        repr_str = repr(result)

        # ASSERT
        assert "⚠️ ANOMALY" in repr_str


class TestAnomalyDetection:
    """Test price anomaly detection."""

    def test_count_price_anomalies_detects_spikes(self):
        """Test detection of >10% price spikes."""
        # ARRANGE
        candles = [
            OHLCV(1000, 100.0, 105.0, 99.0, 100.0, 1000.0, DataSourceType.BINANCE, "BTC"),
            OHLCV(2000, 100.0, 120.0, 100.0, 115.0, 1000.0, DataSourceType.BINANCE, "BTC"),  # 15% spike
            OHLCV(3000, 115.0, 120.0, 114.0, 116.0, 1000.0, DataSourceType.BINANCE, "BTC"),  # Normal
        ]

        # ACT
        anomalies = DataAggregator._count_price_anomalies(candles, threshold_pct=10.0)

        # ASSERT
        assert anomalies == 1  # Only the 15% spike

    def test_count_duplicates_detects_duplicate_timestamps(self):
        """Test detection of duplicate timestamps."""
        # ARRANGE
        candles = [
            OHLCV(1000, 100.0, 105.0, 99.0, 102.0, 1000.0, DataSourceType.BINANCE, "BTC"),
            OHLCV(1000, 100.0, 105.0, 99.0, 102.0, 1000.0, DataSourceType.BINANCE, "BTC"),  # Duplicate
            OHLCV(2000, 102.0, 107.0, 101.0, 105.0, 1000.0, DataSourceType.BINANCE, "BTC"),
        ]

        # ACT
        duplicates = DataAggregator._count_duplicates(candles)

        # ASSERT
        assert duplicates == 1  # One duplicate timestamp
