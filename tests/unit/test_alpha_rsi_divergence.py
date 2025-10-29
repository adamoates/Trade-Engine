"""Unit tests for RSI Divergence Alpha Model."""
import pytest
from datetime import datetime, timezone

from trade_engine.services.data.types import OHLCV, DataSourceType
from trade_engine.domain.strategies.alpha_rsi_divergence import RSIDivergenceAlpha
from trade_engine.domain.strategies.types import InsightDirection


class TestRSIDivergenceInit:
    """Test RSI Divergence initialization."""

    def test_init_with_default_parameters(self):
        """Test initialization with defaults."""
        # ACT
        alpha = RSIDivergenceAlpha()

        # ASSERT
        assert alpha.rsi_period == 14
        assert alpha.overbought_threshold == 70
        assert alpha.oversold_threshold == 30
        assert alpha.lookback_periods == 5
        assert alpha.base_confidence == 0.8

    def test_init_with_custom_parameters(self):
        """Test initialization with custom parameters."""
        # ACT
        alpha = RSIDivergenceAlpha(
            rsi_period=10,
            overbought_threshold=75,
            oversold_threshold=25,
            lookback_periods=3,
            confidence=0.9
        )

        # ASSERT
        assert alpha.rsi_period == 10
        assert alpha.overbought_threshold == 75
        assert alpha.oversold_threshold == 25
        assert alpha.lookback_periods == 3
        assert alpha.base_confidence == 0.9

    def test_init_validates_rsi_period(self):
        """Test RSI period must be at least 2."""
        # ACT & ASSERT
        with pytest.raises(ValueError, match="RSI period must be at least 2"):
            RSIDivergenceAlpha(rsi_period=1)

    def test_init_validates_thresholds(self):
        """Test overbought > oversold and within 0-100."""
        # ACT & ASSERT
        with pytest.raises(ValueError, match="Overbought threshold.*must be greater than oversold"):
            RSIDivergenceAlpha(overbought_threshold=60, oversold_threshold=70)

        with pytest.raises(ValueError, match="must be between 0 and 100"):
            RSIDivergenceAlpha(overbought_threshold=110)

        with pytest.raises(ValueError, match="must be between 0 and 100"):
            RSIDivergenceAlpha(oversold_threshold=-5)

    def test_init_validates_confidence(self):
        """Test confidence must be between 0 and 1."""
        # ACT & ASSERT
        with pytest.raises(ValueError, match="Confidence must be between 0 and 1"):
            RSIDivergenceAlpha(confidence=1.5)

    def test_name_property(self):
        """Test alpha model name."""
        # ARRANGE
        alpha = RSIDivergenceAlpha(rsi_period=10, lookback_periods=3)

        # ACT
        name = alpha.name

        # ASSERT
        assert name == "RSI_Divergence_10_3"


class TestRSICalculation:
    """Test RSI calculation."""

    def test_calculate_rsi_with_sufficient_data(self):
        """Test RSI calculation with enough data points."""
        # ARRANGE
        alpha = RSIDivergenceAlpha(rsi_period=14)

        # Create price data with clear uptrend (RSI should be > 50)
        prices = [100 + i for i in range(20)]  # 100, 101, 102, ..., 119

        # ACT
        rsi = alpha._calculate_rsi(prices, period=14)

        # ASSERT
        assert rsi is not None
        assert 50 < rsi <= 100  # Uptrend should have RSI > 50

    def test_calculate_rsi_with_insufficient_data(self):
        """Test RSI returns None with insufficient data."""
        # ARRANGE
        alpha = RSIDivergenceAlpha(rsi_period=14)
        prices = [100, 101, 102]  # Only 3 bars, need 15 (period + 1)

        # ACT
        rsi = alpha._calculate_rsi(prices, period=14)

        # ASSERT
        assert rsi is None

    def test_calculate_rsi_all_same_prices(self):
        """Test RSI with no price movement returns 50."""
        # ARRANGE
        alpha = RSIDivergenceAlpha(rsi_period=14)
        prices = [100.0] * 20  # Flat prices

        # ACT
        rsi = alpha._calculate_rsi(prices, period=14)

        # ASSERT
        assert rsi is not None
        assert 49 <= rsi <= 51  # Should be near 50 (neutral)

    def test_calculate_rsi_pure_uptrend(self):
        """Test RSI approaches 100 in strong uptrend."""
        # ARRANGE
        alpha = RSIDivergenceAlpha(rsi_period=14)
        prices = [100 + i * 5 for i in range(20)]  # Strong uptrend

        # ACT
        rsi = alpha._calculate_rsi(prices, period=14)

        # ASSERT
        assert rsi is not None
        assert rsi > 90  # Strong uptrend

    def test_calculate_rsi_pure_downtrend(self):
        """Test RSI approaches 0 in strong downtrend."""
        # ARRANGE
        alpha = RSIDivergenceAlpha(rsi_period=14)
        prices = [100 - i * 5 for i in range(20)]  # Strong downtrend

        # ACT
        rsi = alpha._calculate_rsi(prices, period=14)

        # ASSERT
        assert rsi is not None
        assert rsi < 10  # Strong downtrend


class TestDivergenceDetection:
    """Test divergence detection logic."""

    def test_detect_bullish_divergence(self):
        """Test detection of bullish divergence (price down, RSI up)."""
        # ARRANGE
        alpha = RSIDivergenceAlpha(lookback_periods=3)

        # Price making lower lows, but RSI making higher lows
        price_lows = [100, 98, 95, 93, 92]  # Lower lows
        rsi_values = [25, 23, 26, 28, 30]   # Higher lows (divergence!)

        # ACT
        direction = alpha._detect_divergence(
            prices=price_lows,
            rsi_values=rsi_values,
            current_rsi=30  # Oversold zone
        )

        # ASSERT
        assert direction == InsightDirection.UP

    def test_detect_bearish_divergence(self):
        """Test detection of bearish divergence (price up, RSI down)."""
        # ARRANGE
        alpha = RSIDivergenceAlpha(lookback_periods=3)

        # Price making higher highs, but RSI making lower highs
        price_highs = [100, 102, 105, 107, 110]  # Higher highs
        rsi_values = [75, 77, 74, 72, 70]        # Lower highs (divergence!)

        # ACT
        direction = alpha._detect_divergence(
            prices=price_highs,
            rsi_values=rsi_values,
            current_rsi=70  # Overbought zone
        )

        # ASSERT
        assert direction == InsightDirection.DOWN

    def test_detect_no_divergence_both_rising(self):
        """Test no divergence when both price and RSI rising."""
        # ARRANGE
        alpha = RSIDivergenceAlpha(lookback_periods=3)

        price_highs = [100, 102, 105, 107, 110]  # Higher highs
        rsi_values = [60, 65, 70, 72, 75]        # Higher highs (no divergence)

        # ACT
        direction = alpha._detect_divergence(
            prices=price_highs,
            rsi_values=rsi_values,
            current_rsi=75
        )

        # ASSERT
        assert direction is None

    def test_detect_no_divergence_both_falling(self):
        """Test no divergence when both price and RSI falling."""
        # ARRANGE
        alpha = RSIDivergenceAlpha(lookback_periods=3)

        price_lows = [100, 98, 95, 93, 90]   # Lower lows
        rsi_values = [40, 35, 32, 28, 25]    # Lower lows (no divergence)

        # ACT
        direction = alpha._detect_divergence(
            prices=price_lows,
            rsi_values=rsi_values,
            current_rsi=25
        )

        # ASSERT
        assert direction is None

    def test_detect_requires_oversold_for_bullish(self):
        """Test bullish divergence only triggers in oversold zone."""
        # ARRANGE
        alpha = RSIDivergenceAlpha(oversold_threshold=30)

        price_lows = [100, 98, 95, 93, 92]
        rsi_values = [45, 43, 46, 48, 50]  # Divergence but not oversold

        # ACT
        direction = alpha._detect_divergence(
            prices=price_lows,
            rsi_values=rsi_values,
            current_rsi=50  # Not in oversold zone
        )

        # ASSERT
        assert direction is None

    def test_detect_requires_overbought_for_bearish(self):
        """Test bearish divergence only triggers in overbought zone."""
        # ARRANGE
        alpha = RSIDivergenceAlpha(overbought_threshold=70)

        price_highs = [100, 102, 105, 107, 110]
        rsi_values = [55, 57, 54, 52, 50]  # Divergence but not overbought

        # ACT
        direction = alpha._detect_divergence(
            prices=price_highs,
            rsi_values=rsi_values,
            current_rsi=50  # Not in overbought zone
        )

        # ASSERT
        assert direction is None


class TestRSIDivergenceInsights:
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

    def test_generate_insights_bullish_divergence(self):
        """Test generates bullish insight on RSI divergence."""
        # ARRANGE - Use smaller RSI period for easier testing
        alpha = RSIDivergenceAlpha(
            rsi_period=5,
            lookback_periods=3,
            oversold_threshold=30
        )

        # Create prices that form bullish divergence with shorter period
        # Strategy: Large drop, then small bounces making lower lows
        # This creates RSI oversold + divergence
        prices = [
            100, 90, 80, 70, 60,  # Sharp drop (RSI very low)
            55, 58, 53, 56, 51,    # Bouncing lower lows (RSI recovering while price down)
        ]

        candles = self._create_test_candles(prices, symbol="BTC")
        data = {"BTC": candles}
        current_time = datetime.now(timezone.utc)

        # ACT
        insights = alpha.generate_insights(data, current_time)

        # ASSERT
        assert len(insights) == 1
        assert insights[0].symbol == "BTC"
        assert insights[0].direction == InsightDirection.UP
        assert insights[0].confidence == 0.8
        assert insights[0].source == "RSI_Divergence_5_3"

    def test_generate_insights_bearish_divergence(self):
        """Test generates bearish insight on RSI divergence."""
        # ARRANGE - Use smaller RSI period for easier testing
        alpha = RSIDivergenceAlpha(
            rsi_period=5,
            lookback_periods=3,
            overbought_threshold=70
        )

        # Create prices that form bearish divergence
        # Strategy: Large rally, then small dips making higher highs
        prices = [
            50, 60, 70, 80, 90,   # Sharp rally (RSI very high)
            95, 92, 97, 94, 99,   # Dipping higher highs (RSI weakening while price up)
        ]

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
        alpha = RSIDivergenceAlpha(rsi_period=14, lookback_periods=5)
        prices = [100, 102, 104]  # Only 3 bars
        candles = self._create_test_candles(prices)
        data = {"BTC": candles}
        current_time = datetime.now(timezone.utc)

        # ACT
        insights = alpha.generate_insights(data, current_time)

        # ASSERT
        assert insights == []

    def test_generate_insights_no_divergence(self):
        """Test returns empty list when no divergence occurs."""
        # ARRANGE
        alpha = RSIDivergenceAlpha(rsi_period=14, lookback_periods=5)

        # Steady uptrend - no divergence
        prices = [100 + i for i in range(25)]
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
        alpha = RSIDivergenceAlpha(rsi_period=5, lookback_periods=3)

        # BTC: bullish divergence
        btc_prices = [
            100, 90, 80, 70, 60,
            55, 58, 53, 56, 51,
        ]
        btc_candles = self._create_test_candles(btc_prices, symbol="BTC")

        # ETH: no divergence (steady uptrend)
        eth_prices = [100 + i * 2 for i in range(10)]
        eth_candles = self._create_test_candles(eth_prices, symbol="ETH")

        data = {"BTC": btc_candles, "ETH": eth_candles}
        current_time = datetime.now(timezone.utc)

        # ACT
        insights = alpha.generate_insights(data, current_time)

        # ASSERT - Only BTC should have insight
        assert len(insights) == 1
        assert insights[0].symbol == "BTC"
        assert insights[0].direction == InsightDirection.UP

    def test_generate_insights_calculates_magnitude(self):
        """Test magnitude is calculated from RSI level."""
        # ARRANGE
        alpha = RSIDivergenceAlpha(rsi_period=5, lookback_periods=3)

        prices = [
            100, 90, 80, 70, 60,
            55, 58, 53, 56, 51,
        ]
        candles = self._create_test_candles(prices)
        data = {"BTC": candles}
        current_time = datetime.now(timezone.utc)

        # ACT
        insights = alpha.generate_insights(data, current_time)

        # ASSERT
        assert len(insights) > 0
        assert insights[0].magnitude is not None
        assert 0 < insights[0].magnitude <= 1  # Should be normalized 0-1
