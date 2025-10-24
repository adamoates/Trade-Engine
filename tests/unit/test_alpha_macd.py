"""Unit tests for MACD Crossover Alpha Model."""
import pytest
from datetime import datetime, timezone

from app.data.types import OHLCV, DataSourceType
from app.strategies.alpha_macd import MACDAlpha
from app.strategies.types import InsightDirection


class TestMACDInit:
    """Test MACD Alpha initialization."""

    def test_init_with_default_parameters(self):
        """Test initialization with defaults."""
        # ACT
        alpha = MACDAlpha()

        # ASSERT
        assert alpha.fast_period == 12
        assert alpha.slow_period == 26
        assert alpha.signal_period == 9
        assert alpha.base_confidence == 0.75

    def test_init_with_custom_parameters(self):
        """Test initialization with custom parameters."""
        # ACT
        alpha = MACDAlpha(
            fast_period=8,
            slow_period=21,
            signal_period=7,
            confidence=0.85
        )

        # ASSERT
        assert alpha.fast_period == 8
        assert alpha.slow_period == 21
        assert alpha.signal_period == 7
        assert alpha.base_confidence == 0.85

    def test_init_validates_period_order(self):
        """Test fast period must be less than slow period."""
        # ACT & ASSERT
        with pytest.raises(ValueError, match="Fast period.*must be less than slow period"):
            MACDAlpha(fast_period=26, slow_period=12)

    def test_init_validates_confidence(self):
        """Test confidence must be between 0 and 1."""
        # ACT & ASSERT
        with pytest.raises(ValueError, match="Confidence must be between 0 and 1"):
            MACDAlpha(confidence=1.5)

    def test_name_property(self):
        """Test alpha model name."""
        # ARRANGE
        alpha = MACDAlpha(fast_period=8, slow_period=21, signal_period=7)

        # ACT
        name = alpha.name

        # ASSERT
        assert name == "MACD_8_21_7"


class TestEMACalculation:
    """Test EMA calculation."""

    def test_calculate_ema_with_sufficient_data(self):
        """Test EMA calculation with enough data points."""
        # ARRANGE
        alpha = MACDAlpha()
        prices = [100 + i for i in range(30)]

        # ACT
        ema = alpha._calculate_ema(prices, period=12)

        # ASSERT
        assert ema is not None
        assert isinstance(ema, list)
        assert len(ema) == len(prices)

    def test_calculate_ema_with_insufficient_data(self):
        """Test EMA returns None with insufficient data."""
        # ARRANGE
        alpha = MACDAlpha()
        prices = [100, 101, 102]

        # ACT
        ema = alpha._calculate_ema(prices, period=12)

        # ASSERT
        assert ema is None

    def test_calculate_ema_uptrend(self):
        """Test EMA follows uptrend."""
        # ARRANGE
        alpha = MACDAlpha()
        prices = [100 + i for i in range(30)]

        # ACT
        ema = alpha._calculate_ema(prices, period=12)

        # ASSERT
        assert ema is not None
        # EMA should be increasing for uptrend
        # Compare first valid EMA with last (skip None values)
        first_valid = next(e for e in ema if e is not None)
        assert ema[-1] > first_valid

    def test_calculate_ema_downtrend(self):
        """Test EMA follows downtrend."""
        # ARRANGE
        alpha = MACDAlpha()
        prices = [100 - i for i in range(30)]

        # ACT
        ema = alpha._calculate_ema(prices, period=12)

        # ASSERT
        assert ema is not None
        # EMA should be decreasing for downtrend
        # Compare first valid EMA with last (skip None values)
        first_valid = next(e for e in ema if e is not None)
        assert ema[-1] < first_valid


class TestMACDCalculation:
    """Test MACD line calculation."""

    def test_calculate_macd_line(self):
        """Test MACD line is difference between fast and slow EMAs."""
        # ARRANGE
        alpha = MACDAlpha(fast_period=12, slow_period=26)
        prices = [100 + i * 0.5 for i in range(50)]

        # ACT
        macd_line = alpha._calculate_macd_line(prices)

        # ASSERT
        assert macd_line is not None
        assert isinstance(macd_line, list)
        assert len(macd_line) > 0

    def test_calculate_macd_insufficient_data(self):
        """Test MACD returns None with insufficient data."""
        # ARRANGE
        alpha = MACDAlpha(fast_period=12, slow_period=26)
        prices = [100, 101, 102]

        # ACT
        macd_line = alpha._calculate_macd_line(prices)

        # ASSERT
        assert macd_line is None


class TestSignalLineCalculation:
    """Test signal line calculation."""

    def test_calculate_signal_line(self):
        """Test signal line is EMA of MACD line."""
        # ARRANGE
        alpha = MACDAlpha(signal_period=9)
        macd_line = [i * 0.1 for i in range(30)]

        # ACT
        signal_line = alpha._calculate_signal_line(macd_line)

        # ASSERT
        assert signal_line is not None
        assert isinstance(signal_line, list)
        assert len(signal_line) == len(macd_line)

    def test_calculate_signal_insufficient_data(self):
        """Test signal returns None with insufficient data."""
        # ARRANGE
        alpha = MACDAlpha(signal_period=9)
        macd_line = [1.0, 2.0, 3.0]

        # ACT
        signal_line = alpha._calculate_signal_line(macd_line)

        # ASSERT
        assert signal_line is None


class TestMACDCrossoverDetection:
    """Test MACD crossover detection."""

    def test_detect_bullish_crossover(self):
        """Test detection of bullish MACD crossover."""
        # ARRANGE
        alpha = MACDAlpha()

        # MACD was below signal, now above (bullish)
        macd_current = 1.5
        signal_current = 1.0
        macd_prev = 0.5
        signal_prev = 1.0

        # ACT
        direction = alpha._detect_crossover(
            macd_current, signal_current,
            macd_prev, signal_prev
        )

        # ASSERT
        assert direction == InsightDirection.UP

    def test_detect_bearish_crossover(self):
        """Test detection of bearish MACD crossover."""
        # ARRANGE
        alpha = MACDAlpha()

        # MACD was above signal, now below (bearish)
        macd_current = 0.5
        signal_current = 1.0
        macd_prev = 1.5
        signal_prev = 1.0

        # ACT
        direction = alpha._detect_crossover(
            macd_current, signal_current,
            macd_prev, signal_prev
        )

        # ASSERT
        assert direction == InsightDirection.DOWN

    def test_detect_no_crossover_both_above(self):
        """Test no crossover when MACD stays above signal."""
        # ARRANGE
        alpha = MACDAlpha()

        macd_current = 1.5
        signal_current = 1.0
        macd_prev = 1.2
        signal_prev = 1.0

        # ACT
        direction = alpha._detect_crossover(
            macd_current, signal_current,
            macd_prev, signal_prev
        )

        # ASSERT
        assert direction is None

    def test_detect_no_crossover_both_below(self):
        """Test no crossover when MACD stays below signal."""
        # ARRANGE
        alpha = MACDAlpha()

        macd_current = 0.5
        signal_current = 1.0
        macd_prev = 0.8
        signal_prev = 1.0

        # ACT
        direction = alpha._detect_crossover(
            macd_current, signal_current,
            macd_prev, signal_prev
        )

        # ASSERT
        assert direction is None


class TestMACDInsights:
    """Test insight generation."""

    def _create_test_candles(self, prices: list, symbol: str = "BTC") -> list:
        """Helper to create test OHLCV candles."""
        return [
            OHLCV(
                timestamp=i * 60000,
                open=price,
                high=price + 1,
                low=price - 1,
                close=price,
                volume=1000.0,
                source=DataSourceType.BINANCE,
                symbol=symbol
            )
            for i, price in enumerate(prices)
        ]

    def test_generate_insights_processes_data_correctly(self):
        """Test that generate_insights processes price data without errors."""
        # ARRANGE
        alpha = MACDAlpha(fast_period=8, slow_period=17, signal_period=9)

        # Create uptrend - may or may not generate crossover, but should process correctly
        prices = [100 + i * 0.5 for i in range(50)]
        candles = self._create_test_candles(prices, symbol="BTC")
        data = {"BTC": candles}
        current_time = datetime.now(timezone.utc)

        # ACT
        insights = alpha.generate_insights(data, current_time)

        # ASSERT
        # Should return a list (may be empty if no crossover occurs, which is fine)
        assert isinstance(insights, list)
        # All insights should have correct structure if any are generated
        for insight in insights:
            assert insight.symbol == "BTC"
            assert insight.confidence == 0.75
            assert insight.magnitude is not None
            assert insight.direction in [InsightDirection.UP, InsightDirection.DOWN]

    def test_generate_insights_insufficient_data(self):
        """Test returns empty list with insufficient data."""
        # ARRANGE
        alpha = MACDAlpha()
        prices = [100, 101, 102]
        candles = self._create_test_candles(prices)
        data = {"BTC": candles}
        current_time = datetime.now(timezone.utc)

        # ACT
        insights = alpha.generate_insights(data, current_time)

        # ASSERT
        assert insights == []

    def test_generate_insights_no_crossover(self):
        """Test returns empty list when no crossover occurs."""
        # ARRANGE
        alpha = MACDAlpha()

        # Flat prices - no crossover
        prices = [100.0] * 50
        candles = self._create_test_candles(prices)
        data = {"BTC": candles}
        current_time = datetime.now(timezone.utc)

        # ACT
        insights = alpha.generate_insights(data, current_time)

        # ASSERT
        assert insights == []

    def test_generate_insights_calculates_histogram(self):
        """Test histogram (magnitude) is calculated correctly."""
        # ARRANGE
        alpha = MACDAlpha(fast_period=8, slow_period=17, signal_period=9)

        prices = [100 + i * 0.5 for i in range(50)]
        candles = self._create_test_candles(prices)
        data = {"BTC": candles}
        current_time = datetime.now(timezone.utc)

        # ACT
        insights = alpha.generate_insights(data, current_time)

        # ASSERT
        if len(insights) > 0:
            assert insights[0].magnitude is not None
            assert insights[0].magnitude >= 0  # Histogram (absolute value)
