"""Unit tests for Bollinger Band Breakout Alpha Model."""
import pytest
from datetime import datetime, timezone

from mft.services.data.types import OHLCV, DataSourceType
from mft.services.strategies.alpha_bollinger import BollingerAlpha
from mft.services.strategies.types import InsightDirection


class TestBollingerInit:
    """Test Bollinger Band Alpha initialization."""

    def test_init_with_default_parameters(self):
        """Test initialization with defaults."""
        # ACT
        alpha = BollingerAlpha()

        # ASSERT
        assert alpha.period == 20
        assert alpha.num_std_dev == 2.0
        assert alpha.base_confidence == 0.7

    def test_init_with_custom_parameters(self):
        """Test initialization with custom parameters."""
        # ACT
        alpha = BollingerAlpha(
            period=10,
            num_std_dev=2.5,
            confidence=0.8
        )

        # ASSERT
        assert alpha.period == 10
        assert alpha.num_std_dev == 2.5
        assert alpha.base_confidence == 0.8

    def test_init_validates_period(self):
        """Test period must be at least 2."""
        # ACT & ASSERT
        with pytest.raises(ValueError, match="Period must be at least 2"):
            BollingerAlpha(period=1)

    def test_init_validates_std_dev(self):
        """Test num_std_dev must be positive."""
        # ACT & ASSERT
        with pytest.raises(ValueError, match="Standard deviation multiplier must be positive"):
            BollingerAlpha(num_std_dev=0)

    def test_init_validates_confidence(self):
        """Test confidence must be between 0 and 1."""
        # ACT & ASSERT
        with pytest.raises(ValueError, match="Confidence must be between 0 and 1"):
            BollingerAlpha(confidence=1.5)

    def test_name_property(self):
        """Test alpha model name."""
        # ARRANGE
        alpha = BollingerAlpha(period=10, num_std_dev=2.5)

        # ACT
        name = alpha.name

        # ASSERT
        assert name == "Bollinger_10_2.5"


class TestSMACalculation:
    """Test Simple Moving Average calculation."""

    def test_calculate_sma_with_sufficient_data(self):
        """Test SMA calculation with enough data points."""
        # ARRANGE
        alpha = BollingerAlpha(period=5)
        prices = [100, 102, 104, 106, 108, 110, 112]

        # ACT
        sma = alpha._calculate_sma(prices, period=5)

        # ASSERT
        assert sma is not None
        # SMA of last 5 prices: (104 + 106 + 108 + 110 + 112) / 5 = 108
        assert abs(sma - 108.0) < 0.01

    def test_calculate_sma_with_insufficient_data(self):
        """Test SMA returns None with insufficient data."""
        # ARRANGE
        alpha = BollingerAlpha(period=20)
        prices = [100, 101, 102]

        # ACT
        sma = alpha._calculate_sma(prices, period=20)

        # ASSERT
        assert sma is None


class TestStandardDeviationCalculation:
    """Test standard deviation calculation."""

    def test_calculate_std_dev_with_sufficient_data(self):
        """Test std dev calculation with enough data points."""
        # ARRANGE
        alpha = BollingerAlpha(period=5)
        prices = [100, 102, 104, 106, 108]

        # ACT
        std_dev = alpha._calculate_std_dev(prices, period=5)

        # ASSERT
        assert std_dev is not None
        assert std_dev > 0
        # Std dev of [100, 102, 104, 106, 108] should be ~2.83
        assert abs(std_dev - 2.83) < 0.1

    def test_calculate_std_dev_with_insufficient_data(self):
        """Test std dev returns None with insufficient data."""
        # ARRANGE
        alpha = BollingerAlpha(period=20)
        prices = [100, 101, 102]

        # ACT
        std_dev = alpha._calculate_std_dev(prices, period=20)

        # ASSERT
        assert std_dev is None

    def test_calculate_std_dev_flat_prices(self):
        """Test std dev is zero for flat prices."""
        # ARRANGE
        alpha = BollingerAlpha(period=5)
        prices = [100.0] * 10

        # ACT
        std_dev = alpha._calculate_std_dev(prices, period=5)

        # ASSERT
        assert std_dev is not None
        assert abs(std_dev) < 0.01  # Should be near zero


class TestBollingerBandsCalculation:
    """Test Bollinger Bands calculation."""

    def test_calculate_bands_with_sufficient_data(self):
        """Test bands calculation with enough data points."""
        # ARRANGE
        alpha = BollingerAlpha(period=5, num_std_dev=2.0)
        prices = [100, 102, 104, 106, 108]

        # ACT
        lower, middle, upper = alpha._calculate_bands(prices)

        # ASSERT
        assert lower is not None
        assert middle is not None
        assert upper is not None
        assert lower < middle < upper

    def test_calculate_bands_with_insufficient_data(self):
        """Test bands return None with insufficient data."""
        # ARRANGE
        alpha = BollingerAlpha(period=20)
        prices = [100, 101, 102]

        # ACT
        lower, middle, upper = alpha._calculate_bands(prices)

        # ASSERT
        assert lower is None
        assert middle is None
        assert upper is None

    def test_calculate_bands_relationships(self):
        """Test relationship between bands."""
        # ARRANGE
        alpha = BollingerAlpha(period=5, num_std_dev=2.0)
        prices = [100, 102, 104, 106, 108, 110]

        # ACT
        lower, middle, upper = alpha._calculate_bands(prices)

        # ASSERT
        # Middle band should be the SMA
        expected_sma = sum(prices[-5:]) / 5
        assert abs(middle - expected_sma) < 0.01
        # Distance between middle and upper should equal distance between middle and lower
        upper_distance = upper - middle
        lower_distance = middle - lower
        assert abs(upper_distance - lower_distance) < 0.01


class TestBreakoutDetection:
    """Test breakout detection logic."""

    def test_detect_bullish_breakout(self):
        """Test detection of bullish breakout (price above upper band)."""
        # ARRANGE
        alpha = BollingerAlpha()

        # ACT
        direction = alpha._detect_breakout(
            current_price=115.0,
            upper_band=110.0,
            lower_band=90.0
        )

        # ASSERT
        assert direction == InsightDirection.UP

    def test_detect_bearish_breakout(self):
        """Test detection of bearish breakout (price below lower band)."""
        # ARRANGE
        alpha = BollingerAlpha()

        # ACT
        direction = alpha._detect_breakout(
            current_price=85.0,
            upper_band=110.0,
            lower_band=90.0
        )

        # ASSERT
        assert direction == InsightDirection.DOWN

    def test_detect_no_breakout_inside_bands(self):
        """Test no breakout when price is inside bands."""
        # ARRANGE
        alpha = BollingerAlpha()

        # ACT
        direction = alpha._detect_breakout(
            current_price=100.0,
            upper_band=110.0,
            lower_band=90.0
        )

        # ASSERT
        assert direction is None

    def test_detect_no_breakout_at_band(self):
        """Test no breakout when price is exactly at band."""
        # ARRANGE
        alpha = BollingerAlpha()

        # ACT - Price exactly at upper band
        direction_upper = alpha._detect_breakout(
            current_price=110.0,
            upper_band=110.0,
            lower_band=90.0
        )

        # ACT - Price exactly at lower band
        direction_lower = alpha._detect_breakout(
            current_price=90.0,
            upper_band=110.0,
            lower_band=90.0
        )

        # ASSERT
        assert direction_upper is None
        assert direction_lower is None


class TestBollingerInsights:
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

    def test_generate_insights_bullish_breakout(self):
        """Test generates bullish insight on breakout above upper band."""
        # ARRANGE
        alpha = BollingerAlpha(period=10, num_std_dev=2.0)

        # Create prices that stay in a range then break out upward
        prices = []
        # Consolidation around 100 for 20 bars
        for i in range(20):
            prices.append(100 + (i % 5) - 2)  # Oscillates 98-102
        # Sharp breakout above
        prices.append(115)

        candles = self._create_test_candles(prices, symbol="BTC")
        data = {"BTC": candles}
        current_time = datetime.now(timezone.utc)

        # ACT
        insights = alpha.generate_insights(data, current_time)

        # ASSERT
        bullish_insights = [i for i in insights if i.direction == InsightDirection.UP]
        assert len(bullish_insights) > 0
        assert bullish_insights[0].symbol == "BTC"
        assert bullish_insights[0].confidence == 0.7

    def test_generate_insights_bearish_breakout(self):
        """Test generates bearish insight on breakout below lower band."""
        # ARRANGE
        alpha = BollingerAlpha(period=10, num_std_dev=2.0)

        # Create prices that stay in a range then break down
        prices = []
        # Consolidation around 100 for 20 bars
        for i in range(20):
            prices.append(100 + (i % 5) - 2)  # Oscillates 98-102
        # Sharp breakdown below
        prices.append(85)

        candles = self._create_test_candles(prices, symbol="ETH")
        data = {"ETH": candles}
        current_time = datetime.now(timezone.utc)

        # ACT
        insights = alpha.generate_insights(data, current_time)

        # ASSERT
        bearish_insights = [i for i in insights if i.direction == InsightDirection.DOWN]
        assert len(bearish_insights) > 0
        assert bearish_insights[0].symbol == "ETH"
        assert bearish_insights[0].confidence == 0.7

    def test_generate_insights_insufficient_data(self):
        """Test returns empty list with insufficient data."""
        # ARRANGE
        alpha = BollingerAlpha(period=20)
        prices = [100, 101, 102]
        candles = self._create_test_candles(prices)
        data = {"BTC": candles}
        current_time = datetime.now(timezone.utc)

        # ACT
        insights = alpha.generate_insights(data, current_time)

        # ASSERT
        assert insights == []

    def test_generate_insights_no_breakout(self):
        """Test returns empty list when no breakout occurs."""
        # ARRANGE
        alpha = BollingerAlpha(period=10)

        # Prices stay within bands
        prices = [100 + (i % 5) - 2 for i in range(30)]
        candles = self._create_test_candles(prices)
        data = {"BTC": candles}
        current_time = datetime.now(timezone.utc)

        # ACT
        insights = alpha.generate_insights(data, current_time)

        # ASSERT
        assert insights == []

    def test_generate_insights_calculates_magnitude(self):
        """Test magnitude is calculated from distance to band."""
        # ARRANGE
        alpha = BollingerAlpha(period=10, num_std_dev=2.0)

        # Create breakout
        prices = []
        for i in range(20):
            prices.append(100 + (i % 5) - 2)
        prices.append(115)

        candles = self._create_test_candles(prices)
        data = {"BTC": candles}
        current_time = datetime.now(timezone.utc)

        # ACT
        insights = alpha.generate_insights(data, current_time)

        # ASSERT
        assert len(insights) > 0
        assert insights[0].magnitude is not None
        assert insights[0].magnitude > 0
