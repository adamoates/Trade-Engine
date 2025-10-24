"""Unit tests for Moving Average Crossover Alpha Model."""
import pytest
from datetime import datetime, timezone

from app.data.types import OHLCV, DataSourceType
from app.strategies.alpha_ma_crossover import MovingAverageCrossoverAlpha
from app.strategies.types import InsightDirection


class TestMovingAverageCrossoverInit:
    """Test MA Crossover initialization."""

    def test_init_with_default_parameters(self):
        """Test initialization with defaults."""
        # ACT
        alpha = MovingAverageCrossoverAlpha()

        # ASSERT
        assert alpha.fast_period == 10
        assert alpha.slow_period == 30
        assert alpha.base_confidence == 0.7
        assert alpha.insight_duration_seconds == 86400

    def test_init_with_custom_parameters(self):
        """Test initialization with custom parameters."""
        # ACT
        alpha = MovingAverageCrossoverAlpha(
            fast_period=5,
            slow_period=20,
            confidence=0.9,
            insight_duration_seconds=3600
        )

        # ASSERT
        assert alpha.fast_period == 5
        assert alpha.slow_period == 20
        assert alpha.base_confidence == 0.9
        assert alpha.insight_duration_seconds == 3600

    def test_init_validates_period_order(self):
        """Test fast period must be less than slow period."""
        # ACT & ASSERT
        with pytest.raises(ValueError, match="Fast period.*must be less than"):
            MovingAverageCrossoverAlpha(fast_period=30, slow_period=10)

        with pytest.raises(ValueError, match="Fast period.*must be less than"):
            MovingAverageCrossoverAlpha(fast_period=20, slow_period=20)

    def test_init_validates_confidence_range(self):
        """Test confidence must be between 0 and 1."""
        # ACT & ASSERT
        with pytest.raises(ValueError, match="Confidence must be between 0 and 1"):
            MovingAverageCrossoverAlpha(confidence=1.5)

        with pytest.raises(ValueError, match="Confidence must be between 0 and 1"):
            MovingAverageCrossoverAlpha(confidence=-0.1)

    def test_name_property(self):
        """Test alpha model name includes periods."""
        # ARRANGE
        alpha = MovingAverageCrossoverAlpha(fast_period=5, slow_period=15)

        # ACT
        name = alpha.name

        # ASSERT
        assert name == "MA_Crossover_5_15"


class TestMovingAverageCrossoverSMA:
    """Test SMA calculation."""

    def test_calculate_sma_with_sufficient_data(self):
        """Test SMA calculation with enough data points."""
        # ARRANGE
        alpha = MovingAverageCrossoverAlpha()
        prices = [100, 102, 101, 103, 105]

        # ACT
        sma = alpha._calculate_sma(prices, period=5)

        # ASSERT
        expected = (100 + 102 + 101 + 103 + 105) / 5
        assert sma == expected

    def test_calculate_sma_with_insufficient_data(self):
        """Test SMA returns None with insufficient data."""
        # ARRANGE
        alpha = MovingAverageCrossoverAlpha()
        prices = [100, 102, 101]

        # ACT
        sma = alpha._calculate_sma(prices, period=5)

        # ASSERT
        assert sma is None

    def test_calculate_sma_uses_last_n_periods(self):
        """Test SMA only uses last N periods."""
        # ARRANGE
        alpha = MovingAverageCrossoverAlpha()
        prices = [90, 95, 100, 102, 101, 103, 105]

        # ACT
        sma = alpha._calculate_sma(prices, period=3)

        # ASSERT
        expected = (101 + 103 + 105) / 3
        assert sma == expected


class TestMovingAverageCrossoverDetection:
    """Test crossover detection logic."""

    def test_detect_bullish_crossover(self):
        """Test detection of bullish crossover (fast crosses above slow)."""
        # ARRANGE
        alpha = MovingAverageCrossoverAlpha()

        # ACT - Fast was below, now above
        direction = alpha._detect_crossover(
            fast_ma_current=105.0,
            slow_ma_current=100.0,
            fast_ma_prev=99.0,
            slow_ma_prev=100.0
        )

        # ASSERT
        assert direction == InsightDirection.UP

    def test_detect_bearish_crossover(self):
        """Test detection of bearish crossover (fast crosses below slow)."""
        # ARRANGE
        alpha = MovingAverageCrossoverAlpha()

        # ACT - Fast was above, now below
        direction = alpha._detect_crossover(
            fast_ma_current=99.0,
            slow_ma_current=100.0,
            fast_ma_prev=101.0,
            slow_ma_prev=100.0
        )

        # ASSERT
        assert direction == InsightDirection.DOWN

    def test_detect_no_crossover_both_above(self):
        """Test no crossover when fast remains above slow."""
        # ARRANGE
        alpha = MovingAverageCrossoverAlpha()

        # ACT
        direction = alpha._detect_crossover(
            fast_ma_current=105.0,
            slow_ma_current=100.0,
            fast_ma_prev=104.0,
            slow_ma_prev=100.0
        )

        # ASSERT
        assert direction is None

    def test_detect_no_crossover_both_below(self):
        """Test no crossover when fast remains below slow."""
        # ARRANGE
        alpha = MovingAverageCrossoverAlpha()

        # ACT
        direction = alpha._detect_crossover(
            fast_ma_current=99.0,
            slow_ma_current=100.0,
            fast_ma_prev=98.0,
            slow_ma_prev=100.0
        )

        # ASSERT
        assert direction is None

    def test_detect_no_crossover_missing_previous(self):
        """Test returns None if previous MA values are missing."""
        # ARRANGE
        alpha = MovingAverageCrossoverAlpha()

        # ACT
        direction = alpha._detect_crossover(
            fast_ma_current=105.0,
            slow_ma_current=100.0,
            fast_ma_prev=None,
            slow_ma_prev=100.0
        )

        # ASSERT
        assert direction is None


class TestMovingAverageCrossoverInsights:
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

    def test_generate_insights_bullish_crossover(self):
        """Test generates bullish insight on MA crossover."""
        # ARRANGE
        alpha = MovingAverageCrossoverAlpha(fast_period=3, slow_period=5)

        # Prices that create bullish crossover
        # Start with downtrend, then reverse to uptrend
        # Bar 0-4: downtrend (fast MA below slow MA)
        # Bar 5: fast crosses above slow
        prices = [110, 108, 106, 104, 108, 112]
        # At bar 4: fast=[106,104,108]=106, slow=[110,108,106,104,108]=107.2 (fast < slow)
        # At bar 5: fast=[104,108,112]=108, slow=[108,106,104,108,112]=107.6 (fast > slow)
        # This creates a bullish crossover
        candles = self._create_test_candles(prices, symbol="BTC")
        data = {"BTC": candles}
        current_time = datetime.now(timezone.utc)

        # ACT
        insights = alpha.generate_insights(data, current_time)

        # ASSERT
        assert len(insights) == 1
        assert insights[0].symbol == "BTC"
        assert insights[0].direction == InsightDirection.UP
        assert insights[0].confidence == 0.7
        assert insights[0].source == "MA_Crossover_3_5"

    def test_generate_insights_bearish_crossover(self):
        """Test generates bearish insight on MA crossover."""
        # ARRANGE
        alpha = MovingAverageCrossoverAlpha(fast_period=3, slow_period=5)

        # Prices that create bearish crossover
        # Start with uptrend, then reverse to downtrend
        # Bar 0-4: uptrend (fast MA above slow MA)
        # Bar 5: fast crosses below slow
        prices = [100, 102, 104, 106, 102, 98]
        # At bar 4: fast=[104,106,102]=104, slow=[100,102,104,106,102]=102.8 (fast > slow)
        # At bar 5: fast=[106,102,98]=102, slow=[102,104,106,102,98]=102.4 (fast < slow)
        # This creates a bearish crossover
        candles = self._create_test_candles(prices, symbol="ETH")
        data = {"ETH": candles}
        current_time = datetime.now(timezone.utc)

        # ACT
        insights = alpha.generate_insights(data, current_time)

        # ASSERT
        assert len(insights) == 1
        assert insights[0].symbol == "ETH"
        assert insights[0].direction == InsightDirection.DOWN

    def test_generate_insights_insufficient_data(self):
        """Test returns empty list with insufficient data."""
        # ARRANGE
        alpha = MovingAverageCrossoverAlpha(fast_period=10, slow_period=30)
        prices = [100, 102, 104]  # Only 3 bars, need 31
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
        alpha = MovingAverageCrossoverAlpha(fast_period=3, slow_period=5)

        # Flat prices - no crossover
        prices = [100, 100, 100, 100, 100, 100]
        candles = self._create_test_candles(prices)
        data = {"BTC": candles}
        current_time = datetime.now(timezone.utc)

        # ACT
        insights = alpha.generate_insights(data, current_time)

        # ASSERT
        assert insights == []

    def test_generate_insights_multiple_symbols(self):
        """Test processes multiple symbols independently."""
        # ARRANGE
        alpha = MovingAverageCrossoverAlpha(fast_period=3, slow_period=5)

        # BTC: bullish crossover
        btc_prices = [110, 108, 106, 104, 108, 112]
        btc_candles = self._create_test_candles(btc_prices, symbol="BTC")

        # ETH: bearish crossover
        eth_prices = [100, 102, 104, 106, 102, 98]
        eth_candles = self._create_test_candles(eth_prices, symbol="ETH")

        # ADA: no crossover
        ada_prices = [100, 100, 100, 100, 100, 100]
        ada_candles = self._create_test_candles(ada_prices, symbol="ADA")

        data = {"BTC": btc_candles, "ETH": eth_candles, "ADA": ada_candles}
        current_time = datetime.now(timezone.utc)

        # ACT
        insights = alpha.generate_insights(data, current_time)

        # ASSERT
        assert len(insights) == 2
        btc_insight = next(i for i in insights if i.symbol == "BTC")
        eth_insight = next(i for i in insights if i.symbol == "ETH")

        assert btc_insight.direction == InsightDirection.UP
        assert eth_insight.direction == InsightDirection.DOWN

    def test_generate_insights_calculates_magnitude(self):
        """Test magnitude is calculated as % difference between MAs."""
        # ARRANGE
        alpha = MovingAverageCrossoverAlpha(fast_period=3, slow_period=5)
        prices = [110, 108, 106, 104, 108, 112]
        candles = self._create_test_candles(prices)
        data = {"BTC": candles}
        current_time = datetime.now(timezone.utc)

        # ACT
        insights = alpha.generate_insights(data, current_time)

        # ASSERT
        assert insights[0].magnitude is not None
        assert insights[0].magnitude > 0  # Should be positive % difference
