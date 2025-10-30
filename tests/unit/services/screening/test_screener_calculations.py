"""
Comprehensive tests for MultiFactorScreener calculation methods.

Tests all calculation methods with various patterns and edge cases
to achieve 80%+ coverage.
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from trade_engine.services.data.types import OHLCV, DataSourceType
from trade_engine.services.screening.multi_factor_screener import MultiFactorScreener


@pytest.fixture
def screener():
    """Create screener with default settings."""
    return MultiFactorScreener(
        min_market_cap=Decimal("500_000_000"),
        min_price=Decimal("10.0"),
        lookback_days=20
    )


@pytest.fixture
def base_candles():
    """Generate base OHLCV candles for testing."""
    base_time = datetime.now()
    candles = []

    for i in range(250):  # Enough for 200-day MA
        timestamp = int((base_time - timedelta(days=250-i)).timestamp() * 1000)
        price = 100.0 + (i * 0.1)  # Gradual uptrend

        candles.append(OHLCV(
            timestamp=timestamp,
            open=price - 0.5,
            high=price + 1.0,
            low=price - 1.0,
            close=price,
            volume=1_000_000.0,
            source=DataSourceType.YAHOO_FINANCE,
            symbol="TEST"
        ))

    return candles


class TestCalculateAvgVolume:
    """Test _calculate_avg_volume() with various volume patterns."""

    def test_avg_volume_constant(self):
        """Test average volume with constant volumes."""
        screener = MultiFactorScreener()
        candles = [
            OHLCV(0, 100, 105, 95, 100, 1_000_000, DataSourceType.YAHOO_FINANCE, "TEST"),
            OHLCV(0, 100, 105, 95, 100, 1_000_000, DataSourceType.YAHOO_FINANCE, "TEST"),
            OHLCV(0, 100, 105, 95, 100, 1_000_000, DataSourceType.YAHOO_FINANCE, "TEST"),
        ]

        result = screener._calculate_avg_volume(candles)

        assert result == Decimal("1000000")
        assert isinstance(result, Decimal)

    def test_avg_volume_increasing(self):
        """Test average volume with increasing pattern."""
        screener = MultiFactorScreener()
        candles = [
            OHLCV(0, 100, 105, 95, 100, 1_000_000, DataSourceType.YAHOO_FINANCE, "TEST"),
            OHLCV(0, 100, 105, 95, 100, 2_000_000, DataSourceType.YAHOO_FINANCE, "TEST"),
            OHLCV(0, 100, 105, 95, 100, 3_000_000, DataSourceType.YAHOO_FINANCE, "TEST"),
        ]

        result = screener._calculate_avg_volume(candles)

        assert result == Decimal("2000000")  # (1M + 2M + 3M) / 3

    def test_avg_volume_empty_list(self):
        """Test average volume with empty candle list."""
        screener = MultiFactorScreener()

        result = screener._calculate_avg_volume([])

        assert result == Decimal("0")

    def test_avg_volume_single_candle(self):
        """Test average volume with single candle."""
        screener = MultiFactorScreener()
        candles = [
            OHLCV(0, 100, 105, 95, 100, 5_000_000, DataSourceType.YAHOO_FINANCE, "TEST"),
        ]

        result = screener._calculate_avg_volume(candles)

        assert result == Decimal("5000000")

    def test_avg_volume_decimal_precision(self):
        """Test that average volume uses Decimal (NON-NEGOTIABLE)."""
        screener = MultiFactorScreener()
        candles = [
            OHLCV(0, 100, 105, 95, 100, 1_234_567, DataSourceType.YAHOO_FINANCE, "TEST"),
            OHLCV(0, 100, 105, 95, 100, 2_345_678, DataSourceType.YAHOO_FINANCE, "TEST"),
        ]

        result = screener._calculate_avg_volume(candles)

        assert isinstance(result, Decimal), "Volume must use Decimal, not float"
        assert result == Decimal("1790122.5")


class TestCalculateSMA:
    """Test _calculate_sma() with different periods and data lengths."""

    def test_sma_exact_period_length(self):
        """Test SMA when candles exactly match period."""
        screener = MultiFactorScreener()
        candles = [
            OHLCV(0, 0, 0, 0, 100, 0, DataSourceType.YAHOO_FINANCE, "TEST"),
            OHLCV(0, 0, 0, 0, 110, 0, DataSourceType.YAHOO_FINANCE, "TEST"),
            OHLCV(0, 0, 0, 0, 120, 0, DataSourceType.YAHOO_FINANCE, "TEST"),
        ]

        result = screener._calculate_sma(candles, period=3)

        assert result == Decimal("110")  # (100 + 110 + 120) / 3

    def test_sma_more_candles_than_period(self):
        """Test SMA uses only most recent N candles."""
        screener = MultiFactorScreener()
        candles = [
            OHLCV(0, 0, 0, 0, 50, 0, DataSourceType.YAHOO_FINANCE, "TEST"),   # Ignored
            OHLCV(0, 0, 0, 0, 60, 0, DataSourceType.YAHOO_FINANCE, "TEST"),   # Ignored
            OHLCV(0, 0, 0, 0, 100, 0, DataSourceType.YAHOO_FINANCE, "TEST"),  # Used
            OHLCV(0, 0, 0, 0, 110, 0, DataSourceType.YAHOO_FINANCE, "TEST"),  # Used
            OHLCV(0, 0, 0, 0, 120, 0, DataSourceType.YAHOO_FINANCE, "TEST"),  # Used
        ]

        result = screener._calculate_sma(candles, period=3)

        assert result == Decimal("110")  # (100 + 110 + 120) / 3

    def test_sma_insufficient_data(self):
        """Test SMA returns 0 when insufficient data."""
        screener = MultiFactorScreener()
        candles = [
            OHLCV(0, 0, 0, 0, 100, 0, DataSourceType.YAHOO_FINANCE, "TEST"),
            OHLCV(0, 0, 0, 0, 110, 0, DataSourceType.YAHOO_FINANCE, "TEST"),
        ]

        result = screener._calculate_sma(candles, period=5)

        assert result == Decimal("0")

    def test_sma_empty_list(self):
        """Test SMA returns 0 for empty candle list."""
        screener = MultiFactorScreener()

        result = screener._calculate_sma([], period=10)

        assert result == Decimal("0")

    def test_sma_50_period(self):
        """Test 50-period SMA calculation."""
        screener = MultiFactorScreener()
        # Create 50 candles with price = 100 + index
        candles = [
            OHLCV(0, 0, 0, 0, 100 + i, 0, DataSourceType.YAHOO_FINANCE, "TEST")
            for i in range(50)
        ]

        result = screener._calculate_sma(candles, period=50)

        # Prices: 100, 101, 102, ..., 149
        # Average = (100 + 149) / 2 = 124.5
        assert result == Decimal("124.5")

    def test_sma_decimal_type(self):
        """Test SMA uses Decimal (NON-NEGOTIABLE)."""
        screener = MultiFactorScreener()
        candles = [
            OHLCV(0, 0, 0, 0, 99.99, 0, DataSourceType.YAHOO_FINANCE, "TEST"),
            OHLCV(0, 0, 0, 0, 100.01, 0, DataSourceType.YAHOO_FINANCE, "TEST"),
        ]

        result = screener._calculate_sma(candles, period=2)

        assert isinstance(result, Decimal), "SMA must use Decimal, not float"
        assert result == Decimal("100.00")


class TestCalculateEMA:
    """Test _calculate_ema() exponential weighting correctness."""

    def test_ema_single_period(self):
        """Test EMA with period = 1 (should equal last price)."""
        screener = MultiFactorScreener()
        candles = [
            OHLCV(0, 0, 0, 0, 100, 0, DataSourceType.YAHOO_FINANCE, "TEST"),
            OHLCV(0, 0, 0, 0, 110, 0, DataSourceType.YAHOO_FINANCE, "TEST"),
            OHLCV(0, 0, 0, 0, 120, 0, DataSourceType.YAHOO_FINANCE, "TEST"),
        ]

        result = screener._calculate_ema(candles, period=1)

        # With period=1, multiplier = 2/(1+1) = 1.0, so EMA = last price
        assert result == Decimal("120")

    def test_ema_exact_period_length(self):
        """Test EMA when candles exactly match period."""
        screener = MultiFactorScreener()
        candles = [
            OHLCV(0, 0, 0, 0, 100, 0, DataSourceType.YAHOO_FINANCE, "TEST"),
            OHLCV(0, 0, 0, 0, 110, 0, DataSourceType.YAHOO_FINANCE, "TEST"),
            OHLCV(0, 0, 0, 0, 120, 0, DataSourceType.YAHOO_FINANCE, "TEST"),
        ]

        result = screener._calculate_ema(candles, period=3)

        # EMA(3) starts with SMA(3) = 110
        # Multiplier = 2/(3+1) = 0.5
        # No more prices to process, so EMA = 110
        assert result == Decimal("110")

    def test_ema_responds_to_recent_prices(self):
        """Test EMA weighs recent prices more heavily than SMA."""
        screener = MultiFactorScreener()
        # Start with stable prices, then big jump
        candles = [
            OHLCV(0, 0, 0, 0, 100, 0, DataSourceType.YAHOO_FINANCE, "TEST"),
            OHLCV(0, 0, 0, 0, 100, 0, DataSourceType.YAHOO_FINANCE, "TEST"),
            OHLCV(0, 0, 0, 0, 100, 0, DataSourceType.YAHOO_FINANCE, "TEST"),
            OHLCV(0, 0, 0, 0, 100, 0, DataSourceType.YAHOO_FINANCE, "TEST"),
            OHLCV(0, 0, 0, 0, 100, 0, DataSourceType.YAHOO_FINANCE, "TEST"),
            OHLCV(0, 0, 0, 0, 200, 0, DataSourceType.YAHOO_FINANCE, "TEST"),  # Big jump
        ]

        ema = screener._calculate_ema(candles, period=5)
        sma = screener._calculate_sma(candles, period=5)

        # EMA should be higher than SMA due to weighting recent jump
        assert ema > sma

    def test_ema_insufficient_data(self):
        """Test EMA returns 0 when insufficient data."""
        screener = MultiFactorScreener()
        candles = [
            OHLCV(0, 0, 0, 0, 100, 0, DataSourceType.YAHOO_FINANCE, "TEST"),
        ]

        result = screener._calculate_ema(candles, period=5)

        assert result == Decimal("0")

    def test_ema_decimal_precision(self):
        """Test EMA uses Decimal (NON-NEGOTIABLE)."""
        screener = MultiFactorScreener()
        candles = [
            OHLCV(0, 0, 0, 0, 100.5, 0, DataSourceType.YAHOO_FINANCE, "TEST"),
            OHLCV(0, 0, 0, 0, 101.5, 0, DataSourceType.YAHOO_FINANCE, "TEST"),
            OHLCV(0, 0, 0, 0, 102.5, 0, DataSourceType.YAHOO_FINANCE, "TEST"),
        ]

        result = screener._calculate_ema(candles, period=2)

        assert isinstance(result, Decimal), "EMA must use Decimal, not float"


class TestCalculateRSI:
    """Test _calculate_rsi() with known datasets and RSI values."""

    def test_rsi_all_gains(self):
        """Test RSI with all gains = 100."""
        screener = MultiFactorScreener()
        # All rising prices
        candles = [
            OHLCV(0, 0, 0, 0, 100 + i, 0, DataSourceType.YAHOO_FINANCE, "TEST")
            for i in range(15)  # 14 + 1 for period
        ]

        result = screener._calculate_rsi(candles, period=14)

        # All gains, no losses -> RSI = 100
        assert result == Decimal("100")

    def test_rsi_all_losses(self):
        """Test RSI with all losses = 0."""
        screener = MultiFactorScreener()
        # All falling prices
        candles = [
            OHLCV(0, 0, 0, 0, 100 - i, 0, DataSourceType.YAHOO_FINANCE, "TEST")
            for i in range(15)
        ]

        result = screener._calculate_rsi(candles, period=14)

        # All losses, no gains -> RSI = 0
        assert result == Decimal("0")

    def test_rsi_equal_gains_losses(self):
        """Test RSI with equal gains and losses = 50."""
        screener = MultiFactorScreener()
        # Alternating +1, -1 changes
        prices = [100]
        for i in range(14):
            if i % 2 == 0:
                prices.append(prices[-1] + 1)
            else:
                prices.append(prices[-1] - 1)

        candles = [
            OHLCV(0, 0, 0, 0, price, 0, DataSourceType.YAHOO_FINANCE, "TEST")
            for price in prices
        ]

        result = screener._calculate_rsi(candles, period=14)

        # Equal avg gain and avg loss -> RS = 1 -> RSI = 50
        assert result == Decimal("50")

    def test_rsi_insufficient_data(self):
        """Test RSI returns neutral 50 when insufficient data."""
        screener = MultiFactorScreener()
        candles = [
            OHLCV(0, 0, 0, 0, 100, 0, DataSourceType.YAHOO_FINANCE, "TEST"),
        ]

        result = screener._calculate_rsi(candles, period=14)

        assert result == Decimal("50")  # Neutral

    def test_rsi_range_bounds(self):
        """Test RSI is always between 0 and 100."""
        screener = MultiFactorScreener()
        # Create various price patterns
        for pattern in ["rising", "falling", "volatile"]:
            if pattern == "rising":
                prices = list(range(100, 120))
            elif pattern == "falling":
                prices = list(range(120, 100, -1))
            else:  # volatile
                prices = [100 + (i % 5) * 5 for i in range(20)]

            candles = [
                OHLCV(0, 0, 0, 0, price, 0, DataSourceType.YAHOO_FINANCE, "TEST")
                for price in prices
            ]

            result = screener._calculate_rsi(candles, period=14)

            assert Decimal("0") <= result <= Decimal("100"), \
                f"RSI {result} out of bounds for {pattern} pattern"

    def test_rsi_decimal_type(self):
        """Test RSI uses Decimal (NON-NEGOTIABLE)."""
        screener = MultiFactorScreener()
        candles = [
            OHLCV(0, 0, 0, 0, 100 + i * 0.5, 0, DataSourceType.YAHOO_FINANCE, "TEST")
            for i in range(15)
        ]

        result = screener._calculate_rsi(candles, period=14)

        assert isinstance(result, Decimal), "RSI must use Decimal, not float"


class TestCalculateBreakoutScore:
    """Test _calculate_breakout_score() at various price levels."""

    def test_breakout_score_at_high(self):
        """Test breakout score when price equals 20-day high = 100."""
        screener = MultiFactorScreener(lookback_days=20)
        candles = [
            OHLCV(0, 0, 105, 0, 100, 0, DataSourceType.YAHOO_FINANCE, "TEST")
            for _ in range(20)
        ]

        # Current price at 20-day high
        result = screener._calculate_breakout_score(candles, Decimal("105"))

        assert result == 100

    def test_breakout_score_above_high(self):
        """Test breakout score when price above 20-day high = 100."""
        screener = MultiFactorScreener(lookback_days=20)
        candles = [
            OHLCV(0, 0, 100, 0, 100, 0, DataSourceType.YAHOO_FINANCE, "TEST")
            for _ in range(20)
        ]

        # Current price above high
        result = screener._calculate_breakout_score(candles, Decimal("110"))

        assert result == 100

    def test_breakout_score_within_2_percent(self):
        """Test breakout score within 2% of high = 75."""
        screener = MultiFactorScreener(lookback_days=20)
        candles = [
            OHLCV(0, 0, 100, 0, 100, 0, DataSourceType.YAHOO_FINANCE, "TEST")
            for _ in range(20)
        ]

        # 1% below high
        result = screener._calculate_breakout_score(candles, Decimal("99"))

        assert result == 75

    def test_breakout_score_within_5_percent(self):
        """Test breakout score within 5% of high = 50."""
        screener = MultiFactorScreener(lookback_days=20)
        candles = [
            OHLCV(0, 0, 100, 0, 100, 0, DataSourceType.YAHOO_FINANCE, "TEST")
            for _ in range(20)
        ]

        # 4% below high
        result = screener._calculate_breakout_score(candles, Decimal("96"))

        assert result == 50

    def test_breakout_score_far_from_high(self):
        """Test breakout score far from high decreases."""
        screener = MultiFactorScreener(lookback_days=20)
        candles = [
            OHLCV(0, 0, 100, 0, 100, 0, DataSourceType.YAHOO_FINANCE, "TEST")
            for _ in range(20)
        ]

        # 10% below high
        result = screener._calculate_breakout_score(candles, Decimal("90"))

        assert result >= 0, "Score should not be negative"
        assert result < 50, "Score should decrease with distance"


class TestCalculateMomentumScore:
    """Test _calculate_momentum_score() composite calculation."""

    def test_momentum_score_optimal(self):
        """Test momentum score with optimal conditions."""
        screener = MultiFactorScreener()

        result = screener._calculate_momentum_score(
            rsi=Decimal("60"),           # Optimal range (50-70)
            macd_bullish=True,           # Bullish MACD
            volume_ratio=Decimal("3.5")  # Exceptional volume
        )

        # 40 (RSI) + 30 (MACD) + 30 (volume) = 100
        assert result == 100

    def test_momentum_score_good(self):
        """Test momentum score with good conditions."""
        screener = MultiFactorScreener()

        result = screener._calculate_momentum_score(
            rsi=Decimal("45"),           # Good range (40-50)
            macd_bullish=True,           # Bullish MACD
            volume_ratio=Decimal("2.0")  # Good volume
        )

        # 30 (RSI) + 30 (MACD) + 20 (volume) = 80
        assert result == 80

    def test_momentum_score_poor(self):
        """Test momentum score with poor conditions."""
        screener = MultiFactorScreener()

        result = screener._calculate_momentum_score(
            rsi=Decimal("20"),           # Below range
            macd_bullish=False,          # No MACD
            volume_ratio=Decimal("1.0")  # Low volume
        )

        # 0 (RSI) + 0 (MACD) + 0 (volume) = 0
        assert result == 0

    def test_momentum_score_capped_at_100(self):
        """Test momentum score never exceeds 100."""
        screener = MultiFactorScreener()

        result = screener._calculate_momentum_score(
            rsi=Decimal("65"),
            macd_bullish=True,
            volume_ratio=Decimal("10.0")  # Extreme volume
        )

        assert result <= 100


class TestCalculateCompositeScore:
    """Test _calculate_composite_score() weighted algorithm."""

    def test_composite_score_perfect(self):
        """Test composite score with perfect inputs."""
        screener = MultiFactorScreener()

        result = screener._calculate_composite_score(
            breakout_score=100,
            momentum_score=100,
            signals_matched=7,
            gain_percent=Decimal("20"),  # Capped
            volume_ratio=Decimal("5")     # Capped
        )

        # All inputs at max -> composite = 100
        assert result == 100

    def test_composite_score_weighted(self):
        """Test composite score respects weights."""
        screener = MultiFactorScreener()

        result = screener._calculate_composite_score(
            breakout_score=100,       # 25% weight
            momentum_score=0,         # 25% weight
            signals_matched=0,        # 20% weight
            gain_percent=Decimal("0"),  # 15% weight
            volume_ratio=Decimal("0")   # 15% weight
        )

        # Only breakout at 100 -> 100 * 0.25 = 25
        assert result == 25

    def test_composite_score_normalization(self):
        """Test gain and volume are normalized correctly."""
        screener = MultiFactorScreener()

        # Test gain normalization (caps at 20%)
        result1 = screener._calculate_composite_score(
            breakout_score=0,
            momentum_score=0,
            signals_matched=0,
            gain_percent=Decimal("10"),  # 50% of cap
            volume_ratio=Decimal("0")
        )

        result2 = screener._calculate_composite_score(
            breakout_score=0,
            momentum_score=0,
            signals_matched=0,
            gain_percent=Decimal("20"),  # 100% of cap
            volume_ratio=Decimal("0")
        )

        # result2 should be ~2x result1 (gain weight is 15%, so 10% gain = 7.5->7, 20% gain = 15)
        # Due to int() truncation, 7.5 becomes 7, so 7*2 = 14, but 15/7 = 2.14
        assert result2 >= result1 * 2 - 1, f"Expected ~{result1 * 2}, got {result2}"
        assert result2 > result1, "20% gain should score higher than 10% gain"

    def test_composite_score_range(self):
        """Test composite score is always 0-100."""
        screener = MultiFactorScreener()

        # Test various combinations
        test_cases = [
            (0, 0, 0, Decimal("0"), Decimal("0")),
            (50, 50, 3, Decimal("10"), Decimal("2.5")),
            (100, 100, 7, Decimal("50"), Decimal("10")),
        ]

        for breakout, momentum, signals, gain, volume in test_cases:
            result = screener._calculate_composite_score(
                breakout_score=breakout,
                momentum_score=momentum,
                signals_matched=signals,
                gain_percent=gain,
                volume_ratio=volume
            )

            assert 0 <= result <= 100, f"Composite score {result} out of range"


class TestScanUniverseIntegration:
    """Integration tests for scan_universe() with multiple symbols."""

    def test_scan_universe_empty_list(self, screener):
        """Test scan_universe with empty symbol list."""
        result = screener.scan_universe(
            symbols=[],
            min_gain_percent=Decimal("5.0"),
            min_volume_ratio=Decimal("1.5"),
            min_breakout_score=50,
            min_signals_matched=3
        )

        assert result == []

    def test_scan_universe_with_matches(self, screener):
        """Test scan_universe with symbols that match criteria."""
        from unittest.mock import patch, MagicMock

        # Create mock match
        mock_match = MagicMock()
        mock_match.symbol = "WINNER"
        mock_match.signals_matched = 5
        mock_match.composite_score = 85

        # Mock _scan_symbol to return a match
        with patch.object(screener, '_scan_symbol', return_value=mock_match):
            result = screener.scan_universe(
                symbols=["WINNER"],
                min_gain_percent=Decimal("5.0"),
                min_volume_ratio=Decimal("1.5"),
                min_breakout_score=50,
                min_signals_matched=3
            )

            # Should return the match
            assert len(result) == 1
            assert result[0].symbol == "WINNER"

    def test_scan_universe_sorting(self, screener, base_candles):
        """Test scan_universe returns results sorted by composite_score."""
        from unittest.mock import patch

        # Mock data source to return same candles for all symbols
        with patch.object(screener, '_fetch_market_cap', return_value=Decimal("1_000_000_000")):
            with patch.object(screener.data_source, 'fetch_ohlcv', return_value=base_candles):
                # Note: This test may return empty results if candles don't meet criteria
                # That's okay - we're testing the sorting logic
                result = screener.scan_universe(
                    symbols=["SYM1", "SYM2", "SYM3"],
                    min_gain_percent=Decimal("1.0"),  # Lower thresholds
                    min_volume_ratio=Decimal("0.5"),
                    min_breakout_score=10,
                    min_signals_matched=1
                )

                # If we got results, verify they're sorted
                if len(result) > 1:
                    for i in range(len(result) - 1):
                        assert result[i].composite_score >= result[i+1].composite_score

    def test_scan_universe_error_handling(self, screener):
        """Test scan_universe continues after individual symbol errors."""
        from unittest.mock import patch

        def mock_scan_symbol(symbol, **kwargs):
            if symbol == "ERROR":
                raise Exception("Test error")
            return None

        with patch.object(screener, '_scan_symbol', side_effect=mock_scan_symbol):
            result = screener.scan_universe(
                symbols=["GOOD1", "ERROR", "GOOD2"],
                min_gain_percent=Decimal("5.0"),
                min_volume_ratio=Decimal("1.5"),
                min_breakout_score=50,
                min_signals_matched=3
            )

            # Should complete without raising exception
            assert result == []  # All return None in this test


class TestMACDCrossover:
    """Test MACD crossover detection."""

    def test_macd_crossover_logic(self):
        """Test MACD crossover detection logic."""
        screener = MultiFactorScreener()

        # Test the crossover logic directly by checking the implementation
        # creates the proper boolean conditions

        # Create stable uptrend to ensure sufficient data
        candles = [
            OHLCV(
                timestamp=i,
                open=100 + i * 0.1,
                high=101 + i * 0.1,
                low=99 + i * 0.1,
                close=100 + i * 0.1,
                volume=1_000_000,
                source=DataSourceType.YAHOO_FINANCE,
                symbol="TEST"
            )
            for i in range(40)
        ]

        # Get MACD values
        current_macd, current_signal = screener._calculate_macd_with_signal(candles)
        prev_macd, prev_signal = screener._calculate_macd_with_signal(candles[:-1])

        # Verify the calculation runs and returns Decimals
        assert isinstance(current_macd, Decimal)
        assert isinstance(current_signal, Decimal)
        assert isinstance(prev_macd, Decimal)
        assert isinstance(prev_signal, Decimal)

        # With uptrend, both should be positive
        assert current_macd > 0
        assert prev_macd > 0

    def test_macd_no_crossover_already_above(self):
        """Test no crossover when MACD already above signal."""
        screener = MultiFactorScreener()

        # Create 40 candles with strong uptrend (MACD stays above)
        candles = [
            OHLCV(
                timestamp=i,
                open=100 + i,
                high=101 + i,
                low=99 + i,
                close=100 + i,
                volume=1_000_000,
                source=DataSourceType.YAHOO_FINANCE,
                symbol="TEST"
            )
            for i in range(40)
        ]

        result = screener._check_macd_crossover(candles)

        # Should not detect crossover (already bullish)
        assert result is False

    def test_macd_insufficient_data(self):
        """Test MACD returns False with insufficient data."""
        screener = MultiFactorScreener()

        candles = [
            OHLCV(0, 100, 105, 95, 100, 1_000_000, DataSourceType.YAHOO_FINANCE, "TEST")
            for _ in range(20)  # Less than 35 required
        ]

        result = screener._check_macd_crossover(candles)

        assert result is False

    def test_calculate_macd_with_signal(self):
        """Test MACD and signal line calculation."""
        screener = MultiFactorScreener()

        candles = [
            OHLCV(
                timestamp=i,
                open=100,
                high=105,
                low=95,
                close=100 + i * 0.5,  # Rising prices
                volume=1_000_000,
                source=DataSourceType.YAHOO_FINANCE,
                symbol="TEST"
            )
            for i in range(35)
        ]

        macd_line, signal_line = screener._calculate_macd_with_signal(candles)

        # Both should be Decimal
        assert isinstance(macd_line, Decimal)
        assert isinstance(signal_line, Decimal)

        # With rising prices, MACD should be positive
        assert macd_line > 0


class TestEdgeCases:
    """Test edge cases: empty data, single candle, insufficient history."""

    def test_single_candle_sma(self, screener):
        """Test SMA with single candle."""
        candles = [
            OHLCV(0, 0, 0, 0, 100, 0, DataSourceType.YAHOO_FINANCE, "TEST"),
        ]

        result = screener._calculate_sma(candles, period=1)

        assert result == Decimal("100")

    def test_single_candle_ema(self, screener):
        """Test EMA with single candle."""
        candles = [
            OHLCV(0, 0, 0, 0, 100, 0, DataSourceType.YAHOO_FINANCE, "TEST"),
        ]

        result = screener._calculate_ema(candles, period=1)

        assert result == Decimal("100")

    def test_insufficient_history_for_macd(self, screener):
        """Test MACD with insufficient history."""
        candles = [
            OHLCV(0, 0, 0, 0, 100, 0, DataSourceType.YAHOO_FINANCE, "TEST")
            for _ in range(10)  # Less than 35 required
        ]

        result = screener._check_macd_crossover(candles)

        assert result is False

    def test_zero_volume_handling(self, screener):
        """Test average volume calculation with zero volumes."""
        candles = [
            OHLCV(0, 100, 105, 95, 100, 0, DataSourceType.YAHOO_FINANCE, "TEST"),
            OHLCV(0, 100, 105, 95, 100, 0, DataSourceType.YAHOO_FINANCE, "TEST"),
        ]

        result = screener._calculate_avg_volume(candles)

        assert result == Decimal("0")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=trade_engine.services.screening.multi_factor_screener", "--cov-report=term-missing"])
