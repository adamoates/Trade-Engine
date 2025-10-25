"""Unit tests for Market Regime Detection."""
import pytest
from enum import Enum

from trade_engine.services.data.types import OHLCV, DataSourceType
from trade_engine.services.strategies.market_regime import MarketRegimeDetector, MarketRegime


class TestMarketRegime:
    """Test MarketRegime enum."""

    def test_market_regime_values(self):
        """Test all regime types exist."""
        assert MarketRegime.TRENDING == "trending"
        assert MarketRegime.RANGING == "ranging"
        assert MarketRegime.UNKNOWN == "unknown"


class TestMarketRegimeDetectorInit:
    """Test Market Regime Detector initialization."""

    def test_init_with_default_parameters(self):
        """Test initialization with defaults."""
        # ACT
        detector = MarketRegimeDetector()

        # ASSERT
        assert detector.adx_period == 14
        assert detector.trending_threshold == 25
        assert detector.strong_trend_threshold == 50

    def test_init_with_custom_parameters(self):
        """Test initialization with custom parameters."""
        # ACT
        detector = MarketRegimeDetector(
            adx_period=20,
            trending_threshold=30,
            strong_trend_threshold=60
        )

        # ASSERT
        assert detector.adx_period == 20
        assert detector.trending_threshold == 30
        assert detector.strong_trend_threshold == 60

    def test_init_validates_adx_period(self):
        """Test ADX period must be at least 2."""
        # ACT & ASSERT
        with pytest.raises(ValueError, match="ADX period must be at least 2"):
            MarketRegimeDetector(adx_period=1)

    def test_init_validates_threshold_order(self):
        """Test trending threshold must be less than strong trend threshold."""
        # ACT & ASSERT
        with pytest.raises(ValueError, match="Trending threshold.*must be less than strong trend threshold"):
            MarketRegimeDetector(trending_threshold=50, strong_trend_threshold=30)


class TestADXCalculation:
    """Test ADX calculation."""

    def _create_test_candles(self, highs: list, lows: list, closes: list) -> list:
        """Helper to create test OHLCV candles."""
        assert len(highs) == len(lows) == len(closes)
        return [
            OHLCV(
                timestamp=i * 60000,
                open=closes[i],
                high=highs[i],
                low=lows[i],
                close=closes[i],
                volume=1000.0,
                source=DataSourceType.BINANCE,
                symbol="BTC"
            )
            for i in range(len(closes))
        ]

    def test_calculate_adx_with_sufficient_data(self):
        """Test ADX calculation with enough data points."""
        # ARRANGE
        detector = MarketRegimeDetector(adx_period=14)

        # Create uptrending data
        closes = [100 + i for i in range(30)]
        highs = [c + 2 for c in closes]
        lows = [c - 2 for c in closes]
        candles = self._create_test_candles(highs, lows, closes)

        # ACT
        adx = detector._calculate_adx(candles, period=14)

        # ASSERT
        assert adx is not None
        assert 0 <= adx <= 100

    def test_calculate_adx_with_insufficient_data(self):
        """Test ADX returns None with insufficient data."""
        # ARRANGE
        detector = MarketRegimeDetector(adx_period=14)

        closes = [100, 101, 102]
        highs = [c + 1 for c in closes]
        lows = [c - 1 for c in closes]
        candles = self._create_test_candles(highs, lows, closes)

        # ACT
        adx = detector._calculate_adx(candles, period=14)

        # ASSERT
        assert adx is None

    def test_calculate_adx_strong_trend(self):
        """Test ADX is high during strong trends."""
        # ARRANGE
        detector = MarketRegimeDetector(adx_period=14)

        # Strong uptrend
        closes = [100 + i * 3 for i in range(30)]
        highs = [c + 3 for c in closes]
        lows = [c - 1 for c in closes]
        candles = self._create_test_candles(highs, lows, closes)

        # ACT
        adx = detector._calculate_adx(candles, period=14)

        # ASSERT
        assert adx is not None
        assert adx > 25  # Should indicate trending

    def test_calculate_adx_ranging_market(self):
        """Test ADX is low during ranging markets."""
        # ARRANGE
        detector = MarketRegimeDetector(adx_period=14)

        # Ranging market (oscillating)
        closes = []
        for i in range(30):
            closes.append(100 + (5 if i % 2 == 0 else -5))
        highs = [c + 2 for c in closes]
        lows = [c - 2 for c in closes]
        candles = self._create_test_candles(highs, lows, closes)

        # ACT
        adx = detector._calculate_adx(candles, period=14)

        # ASSERT
        assert adx is not None
        assert adx < 25  # Should indicate ranging


class TestRegimeDetection:
    """Test regime detection logic."""

    def test_detect_trending_regime(self):
        """Test detection of trending market."""
        # ARRANGE
        detector = MarketRegimeDetector(trending_threshold=25)

        # ACT
        regime = detector._classify_regime(adx=30)

        # ASSERT
        assert regime == MarketRegime.TRENDING

    def test_detect_ranging_regime(self):
        """Test detection of ranging market."""
        # ARRANGE
        detector = MarketRegimeDetector(trending_threshold=25)

        # ACT
        regime = detector._classify_regime(adx=20)

        # ASSERT
        assert regime == MarketRegime.RANGING

    def test_detect_unknown_regime_no_adx(self):
        """Test returns unknown when ADX is None."""
        # ARRANGE
        detector = MarketRegimeDetector()

        # ACT
        regime = detector._classify_regime(adx=None)

        # ASSERT
        assert regime == MarketRegime.UNKNOWN

    def test_threshold_boundary(self):
        """Test regime at threshold boundary."""
        # ARRANGE
        detector = MarketRegimeDetector(trending_threshold=25)

        # ACT - Exactly at threshold should be ranging
        regime_at = detector._classify_regime(adx=25.0)
        regime_just_above = detector._classify_regime(adx=25.1)

        # ASSERT
        assert regime_at == MarketRegime.RANGING
        assert regime_just_above == MarketRegime.TRENDING


class TestRegimeDetectorIntegration:
    """Test end-to-end regime detection."""

    def _create_test_candles(self, highs: list, lows: list, closes: list, symbol: str = "BTC") -> list:
        """Helper to create test OHLCV candles."""
        assert len(highs) == len(lows) == len(closes)
        return [
            OHLCV(
                timestamp=i * 60000,
                open=closes[i],
                high=highs[i],
                low=lows[i],
                close=closes[i],
                volume=1000.0,
                source=DataSourceType.BINANCE,
                symbol=symbol
            )
            for i in range(len(closes))
        ]

    def test_detect_regime_for_symbol_trending(self):
        """Test detecting trending regime for a symbol."""
        # ARRANGE
        detector = MarketRegimeDetector(adx_period=14, trending_threshold=25)

        # Strong uptrend
        closes = [100 + i * 2 for i in range(30)]
        highs = [c + 2 for c in closes]
        lows = [c - 1 for c in closes]
        candles = {"BTC": self._create_test_candles(highs, lows, closes)}

        # ACT
        regime = detector.detect_regime(candles, "BTC")

        # ASSERT
        assert regime == MarketRegime.TRENDING

    def test_detect_regime_for_symbol_ranging(self):
        """Test detecting ranging regime for a symbol."""
        # ARRANGE
        detector = MarketRegimeDetector(adx_period=14, trending_threshold=25)

        # Oscillating market
        closes = []
        for i in range(30):
            closes.append(100 + (3 if i % 2 == 0 else -3))
        highs = [c + 2 for c in closes]
        lows = [c - 2 for c in closes]
        candles = {"BTC": self._create_test_candles(highs, lows, closes)}

        # ACT
        regime = detector.detect_regime(candles, "BTC")

        # ASSERT
        assert regime == MarketRegime.RANGING

    def test_detect_regime_insufficient_data(self):
        """Test returns unknown with insufficient data."""
        # ARRANGE
        detector = MarketRegimeDetector(adx_period=14)

        closes = [100, 101, 102]
        highs = [c + 1 for c in closes]
        lows = [c - 1 for c in closes]
        candles = {"BTC": self._create_test_candles(highs, lows, closes)}

        # ACT
        regime = detector.detect_regime(candles, "BTC")

        # ASSERT
        assert regime == MarketRegime.UNKNOWN

    def test_detect_regime_missing_symbol(self):
        """Test returns unknown for missing symbol."""
        # ARRANGE
        detector = MarketRegimeDetector()
        candles = {}

        # ACT
        regime = detector.detect_regime(candles, "BTC")

        # ASSERT
        assert regime == MarketRegime.UNKNOWN

    def test_detect_regimes_for_all_symbols(self):
        """Test detecting regimes for multiple symbols."""
        # ARRANGE
        detector = MarketRegimeDetector(adx_period=14, trending_threshold=25)

        # BTC: trending
        btc_closes = [100 + i * 2 for i in range(30)]
        btc_highs = [c + 2 for c in btc_closes]
        btc_lows = [c - 1 for c in btc_closes]

        # ETH: ranging
        eth_closes = []
        for i in range(30):
            eth_closes.append(100 + (3 if i % 2 == 0 else -3))
        eth_highs = [c + 2 for c in eth_closes]
        eth_lows = [c - 2 for c in eth_closes]

        candles = {
            "BTC": self._create_test_candles(btc_highs, btc_lows, btc_closes, "BTC"),
            "ETH": self._create_test_candles(eth_highs, eth_lows, eth_closes, "ETH")
        }

        # ACT
        regimes = detector.detect_regimes_for_all(candles)

        # ASSERT
        assert regimes["BTC"] == MarketRegime.TRENDING
        assert regimes["ETH"] == MarketRegime.RANGING

    def test_get_adx_value(self):
        """Test getting raw ADX value for a symbol."""
        # ARRANGE
        detector = MarketRegimeDetector(adx_period=14)

        closes = [100 + i * 2 for i in range(30)]
        highs = [c + 2 for c in closes]
        lows = [c - 1 for c in closes]
        candles = {"BTC": self._create_test_candles(highs, lows, closes)}

        # ACT
        adx = detector.get_adx(candles, "BTC")

        # ASSERT
        assert adx is not None
        assert 0 <= adx <= 100
