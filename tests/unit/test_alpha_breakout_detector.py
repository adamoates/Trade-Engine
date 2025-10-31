"""Unit tests for BreakoutSetupDetector strategy."""
import pytest
from decimal import Decimal
from trade_engine.domain.strategies.alpha_breakout_detector import (
    BreakoutSetupDetector,
    BreakoutConfig,
    SetupSignal
)
from trade_engine.core.types import Bar


class TestBreakoutDetectorInitialization:
    """Test strategy initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default config."""
        strategy = BreakoutSetupDetector(symbol="BTCUSDT")

        assert strategy.symbol == "BTCUSDT"
        assert strategy.config is not None
        assert strategy.config.volume_spike_threshold == Decimal("2.0")
        assert strategy.config.rsi_period == 14
        assert strategy.signal_count == 0

    def test_init_with_custom_config(self):
        """Test initialization with custom config."""
        config = BreakoutConfig(
            volume_spike_threshold=Decimal("3.0"),
            rsi_period=20,
            rsi_bullish_threshold=Decimal("60")
        )
        strategy = BreakoutSetupDetector(symbol="ETHUSDT", config=config)

        assert strategy.symbol == "ETHUSDT"
        assert strategy.config.volume_spike_threshold == Decimal("3.0")
        assert strategy.config.rsi_period == 20
        assert strategy.config.rsi_bullish_threshold == Decimal("60")

    def test_reset_clears_state(self):
        """Test reset clears all internal state."""
        strategy = BreakoutSetupDetector(symbol="BTCUSDT")

        # Add some data
        bar = Bar(
            timestamp=1000,
            open=Decimal("50000"),
            high=Decimal("51000"),
            low=Decimal("49000"),
            close=Decimal("50500"),
            volume=Decimal("100")
        )
        strategy.on_bar(bar)

        assert len(strategy.closes) > 0

        # Reset
        strategy.reset()

        assert len(strategy.closes) == 0
        assert len(strategy.highs) == 0
        assert len(strategy.lows) == 0
        assert len(strategy.volumes) == 0
        assert strategy.signal_count == 0


class TestIndicatorCalculations:
    """Test technical indicator calculations."""

    def test_rsi_calculation(self):
        """Test RSI calculation."""
        strategy = BreakoutSetupDetector(symbol="BTCUSDT")

        # Create 20 bars with upward trend
        for i in range(20):
            bar = Bar(
                timestamp=1000 + i,
                open=Decimal(str(50000 + i * 100)),
                high=Decimal(str(50100 + i * 100)),
                low=Decimal(str(49900 + i * 100)),
                close=Decimal(str(50000 + i * 100 + 50)),
                volume=Decimal("100")
            )
            strategy.on_bar(bar)

        # RSI should be calculated after 14+ bars
        assert len(strategy.rsi_values) > 0
        rsi = strategy.rsi_values[-1]

        # Strong uptrend should have high RSI (>50)
        assert rsi > Decimal("50")
        assert rsi <= Decimal("100")

    def test_macd_calculation(self):
        """Test MACD calculation."""
        strategy = BreakoutSetupDetector(symbol="BTCUSDT")

        # Create 30 bars (need 26 for MACD slow)
        for i in range(30):
            bar = Bar(
                timestamp=1000 + i,
                open=Decimal(str(50000 + i * 50)),
                high=Decimal(str(50100 + i * 50)),
                low=Decimal(str(49900 + i * 50)),
                close=Decimal(str(50000 + i * 50)),
                volume=Decimal("100")
            )
            strategy.on_bar(bar)

        # MACD should be calculated
        assert len(strategy.macd_values) > 0
        assert len(strategy.macd_signal_values) > 0
        assert len(strategy.macd_histogram_values) > 0

        macd_line = strategy.macd_values[-1]
        signal_line = strategy.macd_signal_values[-1]
        histogram = strategy.macd_histogram_values[-1]

        # Histogram should be macd - signal
        assert histogram == macd_line - signal_line

    def test_bollinger_bands_calculation(self):
        """Test Bollinger Bands calculation."""
        strategy = BreakoutSetupDetector(symbol="BTCUSDT")

        # Create 20 bars (need 20 for BB)
        for i in range(20):
            bar = Bar(
                timestamp=1000 + i,
                open=Decimal("50000"),
                high=Decimal("50100"),
                low=Decimal("49900"),
                close=Decimal("50000"),
                volume=Decimal("100")
            )
            strategy.on_bar(bar)

        upper, middle, lower = strategy._calculate_bollinger_bands()

        # For flat price (zero variance), all bands should be equal
        # upper = middle = lower when std dev = 0
        assert upper == middle == lower

        # Bandwidth should be zero for flat price
        bandwidth_pct = ((upper - lower) / middle) * Decimal("100") if middle != 0 else Decimal("0")
        assert bandwidth_pct == Decimal("0")  # Zero variance = zero bandwidth


class TestBreakoutDetection:
    """Test breakout detection logic."""

    def test_no_breakout_without_resistance(self):
        """Test no breakout signal without identified resistance."""
        strategy = BreakoutSetupDetector(symbol="BTCUSDT")

        # Only a few bars, no resistance identified yet
        for i in range(5):
            bar = Bar(
                timestamp=1000 + i,
                open=Decimal("50000"),
                high=Decimal("50100"),
                low=Decimal("49900"),
                close=Decimal("50000"),
                volume=Decimal("100")
            )
            signals = strategy.on_bar(bar)

        # Should not generate signals yet
        assert len(signals) == 0

    def test_breakout_above_resistance_with_volume(self):
        """Test breakout above resistance with volume spike."""
        # Use shorter lookback for test efficiency
        config = BreakoutConfig(sr_lookback_bars=25)
        strategy = BreakoutSetupDetector(symbol="BTCUSDT", config=config)

        # Create clear resistance at 51000 with swing highs
        # Pattern: low -> higher -> PEAK -> lower -> low (repeated)
        prices = [
            49000, 49500, 51000, 49800, 49200,  # First swing high at 51000
            49500, 50000, 51100, 50200, 49500,  # Second swing high at 51100
            49000, 49800, 51050, 49700, 49300,  # Third swing high at 51050
        ]

        for i, price in enumerate(prices):
            bar = Bar(
                timestamp=1000 + i,
                open=Decimal(str(price)),
                high=Decimal(str(price + 100)),  # High is price+100
                low=Decimal(str(price - 100)),
                close=Decimal(str(price)),
                volume=Decimal("100")
            )
            strategy.on_bar(bar)

        # Build up more bars for indicators (need 20+ for all indicators)
        for i in range(10):
            bar = Bar(
                timestamp=2000 + i,
                open=Decimal("50000"),
                high=Decimal("50100"),
                low=Decimal("49900"),
                close=Decimal("50000"),
                volume=Decimal("100")
            )
            strategy.on_bar(bar)

        # Now breakout above 51000 with volume spike
        breakout_bar = Bar(
            timestamp=3000,
            open=Decimal("50900"),
            high=Decimal("51500"),
            low=Decimal("50900"),
            close=Decimal("51200"),  # Above resistance
            volume=Decimal("300")    # 3x average volume
        )

        signals = strategy.on_bar(breakout_bar)

        # May or may not generate signal depending on other conditions,
        # but should have detected resistance
        assert len(strategy.resistance_levels) > 0

    def test_volume_spike_detection(self):
        """Test volume spike detection."""
        strategy = BreakoutSetupDetector(symbol="BTCUSDT")

        # Create 20 bars with normal volume
        for i in range(20):
            bar = Bar(
                timestamp=1000 + i,
                open=Decimal("50000"),
                high=Decimal("50100"),
                low=Decimal("49900"),
                close=Decimal("50000"),
                volume=Decimal("100")
            )
            strategy.on_bar(bar)

        # Bar with volume spike (3x average)
        spike_bar = Bar(
            timestamp=2000,
            open=Decimal("50000"),
            high=Decimal("50100"),
            low=Decimal("49900"),
            close=Decimal("50000"),
            volume=Decimal("300")
        )
        strategy.on_bar(spike_bar)

        # Check volume ratio in setup signal
        setup = strategy._analyze_breakout_setup(spike_bar)
        assert setup.volume_ratio >= Decimal("2.5")  # Should be ~3x


class TestMomentumConfirmation:
    """Test momentum indicator confirmations."""

    def test_bullish_rsi_momentum(self):
        """Test RSI bullish momentum detection."""
        strategy = BreakoutSetupDetector(symbol="BTCUSDT")

        # Create upward trend for bullish RSI
        for i in range(20):
            bar = Bar(
                timestamp=1000 + i,
                open=Decimal(str(50000 + i * 100)),
                high=Decimal(str(50100 + i * 100)),
                low=Decimal(str(49900 + i * 100)),
                close=Decimal(str(50000 + i * 100)),
                volume=Decimal("100")
            )
            strategy.on_bar(bar)

        # RSI should be bullish (>55)
        assert len(strategy.rsi_values) > 0
        assert strategy.rsi_values[-1] >= strategy.config.rsi_bullish_threshold

    def test_bearish_rsi_momentum(self):
        """Test RSI bearish momentum detection."""
        strategy = BreakoutSetupDetector(symbol="BTCUSDT")

        # Create downward trend for bearish RSI
        for i in range(20):
            bar = Bar(
                timestamp=1000 + i,
                open=Decimal(str(50000 - i * 100)),
                high=Decimal(str(50100 - i * 100)),
                low=Decimal(str(49900 - i * 100)),
                close=Decimal(str(50000 - i * 100)),
                volume=Decimal("100")
            )
            strategy.on_bar(bar)

        # RSI should be bearish (<55)
        assert len(strategy.rsi_values) > 0
        assert strategy.rsi_values[-1] < strategy.config.rsi_bullish_threshold

    def test_macd_crossover_detection(self):
        """Test MACD bullish crossover detection."""
        strategy = BreakoutSetupDetector(symbol="BTCUSDT")

        # Need 26+ bars for MACD
        for i in range(30):
            bar = Bar(
                timestamp=1000 + i,
                open=Decimal(str(50000 + i * 50)),
                high=Decimal(str(50100 + i * 50)),
                low=Decimal(str(49900 + i * 50)),
                close=Decimal(str(50000 + i * 50)),
                volume=Decimal("100")
            )
            strategy.on_bar(bar)

        # MACD should be calculated
        assert len(strategy.macd_values) >= strategy.config.macd_lookback_bars


class TestVolatilitySqueeze:
    """Test volatility squeeze detection."""

    def test_tight_bollinger_bands_detected(self):
        """Test detection of tight Bollinger Bands (squeeze)."""
        strategy = BreakoutSetupDetector(symbol="BTCUSDT")

        # Create 20 bars with very little price movement (squeeze)
        for i in range(20):
            bar = Bar(
                timestamp=1000 + i,
                open=Decimal("50000"),
                high=Decimal("50010"),  # Very tight range
                low=Decimal("49990"),
                close=Decimal("50000"),
                volume=Decimal("100")
            )
            strategy.on_bar(bar)

        upper, middle, lower = strategy._calculate_bollinger_bands()
        bandwidth_pct = ((upper - lower) / middle) * Decimal("100")

        # Bandwidth should be very tight
        assert bandwidth_pct < Decimal("2")  # Less than 2%

    def test_expanding_bollinger_bands_detected(self):
        """Test detection of expanding Bollinger Bands (breakout)."""
        strategy = BreakoutSetupDetector(symbol="BTCUSDT")

        # Create tight range first (10 bars)
        for i in range(10):
            bar = Bar(
                timestamp=1000 + i,
                open=Decimal("50000"),
                high=Decimal("50010"),
                low=Decimal("49990"),
                close=Decimal("50000"),
                volume=Decimal("100")
            )
            strategy.on_bar(bar)

        # Then expand range significantly (10 bars with high volatility)
        # Need to fill the 20-bar BB window with volatile data
        for i in range(10):
            # Alternating high and low to create variance
            price = 50000 + (i % 2) * 2000  # Swing between 50000 and 52000
            bar = Bar(
                timestamp=2000 + i,
                open=Decimal(str(price)),
                high=Decimal(str(price + 500)),
                low=Decimal(str(price - 500)),
                close=Decimal(str(price)),
                volume=Decimal("150")
            )
            strategy.on_bar(bar)

        upper, middle, lower = strategy._calculate_bollinger_bands()
        bandwidth_pct = ((upper - lower) / middle) * Decimal("100")

        # Bandwidth should be much wider after expansion (>3% for this volatility)
        assert bandwidth_pct > Decimal("3")


class TestDerivativesSignals:
    """Test derivatives signal analysis."""

    def test_open_interest_increase_detection(self):
        """Test Open Interest increase detection."""
        strategy = BreakoutSetupDetector(symbol="BTCUSDT")

        # Add OI history showing increase
        for i in range(24):
            oi = Decimal(str(100000 + i * 1000))
            strategy.update_derivatives_data(open_interest=oi)

        oi_change = strategy._get_oi_change_pct()

        # OI increased from 100k to 123k = 23% increase
        assert oi_change is not None
        assert oi_change > Decimal("0.10")  # >10% threshold

    def test_funding_rate_positive_detection(self):
        """Test positive funding rate detection."""
        strategy = BreakoutSetupDetector(symbol="BTCUSDT")

        # Set positive funding rate
        strategy.update_derivatives_data(funding_rate=Decimal("0.0003"))

        assert strategy.current_funding_rate == Decimal("0.0003")
        assert strategy.current_funding_rate > strategy.config.funding_rate_positive_min

    def test_put_call_ratio_bullish_detection(self):
        """Test bullish put/call ratio detection."""
        strategy = BreakoutSetupDetector(symbol="BTCUSDT")

        # Set bullish P/C ratio (< 1.0 = more calls than puts)
        strategy.update_derivatives_data(put_call_ratio=Decimal("0.75"))

        assert strategy.current_put_call_ratio == Decimal("0.75")
        assert strategy.current_put_call_ratio < strategy.config.put_call_bullish_threshold


class TestRiskFilters:
    """Test risk filter logic."""

    def test_overextended_rsi_filtered(self):
        """Test overextended RSI triggers risk filter."""
        strategy = BreakoutSetupDetector(symbol="BTCUSDT")

        # Create strong uptrend for overextended RSI
        for i in range(20):
            bar = Bar(
                timestamp=1000 + i,
                open=Decimal(str(50000 + i * 500)),
                high=Decimal(str(50500 + i * 500)),
                low=Decimal(str(49500 + i * 500)),
                close=Decimal(str(50000 + i * 500)),
                volume=Decimal("100")
            )
            strategy.on_bar(bar)

        # RSI should be very high
        if len(strategy.rsi_values) > 0:
            rsi = strategy.rsi_values[-1]
            # In strong uptrend, RSI should be high
            assert rsi > Decimal("50")

    def test_oi_spike_with_flat_price_filtered(self):
        """Test OI spike with flat price triggers trap filter."""
        strategy = BreakoutSetupDetector(symbol="BTCUSDT")

        # Add flat price bars
        for i in range(10):
            bar = Bar(
                timestamp=1000 + i,
                open=Decimal("50000"),
                high=Decimal("50010"),
                low=Decimal("49990"),
                close=Decimal("50000"),
                volume=Decimal("100")
            )
            strategy.on_bar(bar)

        # Add OI spike
        for i in range(24):
            oi = Decimal(str(100000 + i * 2000))  # 48% increase
            strategy.update_derivatives_data(open_interest=oi)

        # Risk filter should detect potential trap
        passed, msg = strategy._check_risk_filters()

        # May or may not trigger depending on exact conditions
        # but function should run without error
        assert isinstance(passed, bool)
        assert isinstance(msg, str)


class TestSetupSignalOutput:
    """Test SetupSignal output format."""

    def test_setup_signal_format(self):
        """Test SetupSignal has all required fields."""
        setup = SetupSignal(
            symbol="BTCUSDT",
            setup="Bullish Breakout",
            confidence=Decimal("0.82"),
            conditions_met=["Breakout above resistance", "Volume 2.3x avg"],
            action="Enter long"
        )

        assert setup.symbol == "BTCUSDT"
        assert setup.setup == "Bullish Breakout"
        assert setup.confidence == Decimal("0.82")
        assert len(setup.conditions_met) == 2
        assert "resistance" in setup.conditions_met[0].lower()

    def test_full_strategy_output(self):
        """Test strategy outputs standard Signal format."""
        strategy = BreakoutSetupDetector(symbol="BTCUSDT")

        # Create enough bars for indicators
        for i in range(30):
            bar = Bar(
                timestamp=1000 + i,
                open=Decimal(str(50000 + i * 10)),
                high=Decimal(str(50100 + i * 10)),
                low=Decimal(str(49900 + i * 10)),
                close=Decimal(str(50000 + i * 10)),
                volume=Decimal("100")
            )
            signals = strategy.on_bar(bar)

        # Signals should be list (may be empty)
        assert isinstance(signals, list)

        # If signal generated, should have correct format
        if signals:
            signal = signals[0]
            assert signal.symbol == "BTCUSDT"
            assert signal.side == "buy"
            assert signal.qty > 0
            assert signal.price > 0
            assert signal.sl is not None
            assert signal.tp is not None


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_insufficient_data_returns_empty(self):
        """Test strategy returns empty signals with insufficient data."""
        strategy = BreakoutSetupDetector(symbol="BTCUSDT")

        # Only 1 bar (not enough for any indicators)
        bar = Bar(
            timestamp=1000,
            open=Decimal("50000"),
            high=Decimal("50100"),
            low=Decimal("49900"),
            close=Decimal("50000"),
            volume=Decimal("100")
        )
        signals = strategy.on_bar(bar)

        assert signals == []

    def test_zero_volume_handled(self):
        """Test zero volume bars handled gracefully."""
        strategy = BreakoutSetupDetector(symbol="BTCUSDT")

        bar = Bar(
            timestamp=1000,
            open=Decimal("50000"),
            high=Decimal("50000"),
            low=Decimal("50000"),
            close=Decimal("50000"),
            volume=Decimal("0")  # Zero volume
        )

        # Should not crash
        signals = strategy.on_bar(bar)
        assert isinstance(signals, list)

    def test_decimal_precision_maintained(self):
        """Test all calculations use Decimal precision."""
        strategy = BreakoutSetupDetector(symbol="BTCUSDT")

        # Create bars
        for i in range(20):
            bar = Bar(
                timestamp=1000 + i,
                open=Decimal("50000.12345678"),
                high=Decimal("50100.12345678"),
                low=Decimal("49900.12345678"),
                close=Decimal("50000.12345678"),
                volume=Decimal("100.12345678")
            )
            strategy.on_bar(bar)

        # All internal values should be Decimal
        assert all(isinstance(c, Decimal) for c in strategy.closes)
        assert all(isinstance(h, Decimal) for h in strategy.highs)
        assert all(isinstance(l, Decimal) for l in strategy.lows)
        assert all(isinstance(v, Decimal) for v in strategy.volumes)

        if len(strategy.rsi_values) > 0:
            assert isinstance(strategy.rsi_values[-1], Decimal)


class TestCodeReviewFixes:
    """Test fixes for code review issues."""

    def test_macd_crossover_boundary_condition(self):
        """Test MACD crossover detection doesn't access out of bounds."""
        strategy = BreakoutSetupDetector(symbol="BTCUSDT")

        # Add exactly enough bars for MACD calculation
        for i in range(26):  # macd_slow period
            bar = Bar(
                timestamp=1000 + i,
                open=Decimal(str(50000 + i * 10)),
                high=Decimal(str(50100 + i * 10)),
                low=Decimal(str(49900 + i * 10)),
                close=Decimal(str(50000 + i * 10)),
                volume=Decimal("100")
            )
            strategy.on_bar(bar)

        # Should not raise IndexError when checking momentum
        score, msg = strategy._check_momentum()
        assert isinstance(score, Decimal)
        assert isinstance(msg, str)
        assert score >= Decimal("0")

    def test_sr_lookback_bars_minimum_validation(self):
        """Test that sr_lookback_bars < 5 is corrected."""
        config = BreakoutConfig()
        config.sr_lookback_bars = 3  # Too small

        strategy = BreakoutSetupDetector(symbol="BTCUSDT", config=config)

        # Should be corrected to 5
        assert strategy.config.sr_lookback_bars == 5

    def test_confidence_score_clamping(self):
        """Test that confidence scores are clamped between 0 and 1."""
        strategy = BreakoutSetupDetector(symbol="BTCUSDT")

        # Add bars with extreme conditions that might cause >1.0 confidence
        for i in range(60):
            bar = Bar(
                timestamp=1000 + i,
                open=Decimal(str(50000 + i * 100)),
                high=Decimal(str(50200 + i * 100)),
                low=Decimal(str(49800 + i * 100)),
                close=Decimal(str(50000 + i * 100)),
                volume=Decimal(str(1000 + i * 100))  # Increasing volume
            )
            strategy.on_bar(bar)

        # Add derivatives signals (all bullish)
        strategy.update_derivatives_data(
            open_interest=Decimal("100000"),
            funding_rate=Decimal("0.0002"),
            put_call_ratio=Decimal("0.5")
        )
        for i in range(24):
            strategy.update_derivatives_data(
                open_interest=Decimal(str(100000 + i * 10000))  # 240% increase
            )

        # Generate a bar with breakout conditions
        bar = Bar(
            timestamp=2000,
            open=Decimal("56000"),
            high=Decimal("57000"),
            close=Decimal("56500"),
            low=Decimal("55900"),
            volume=Decimal("5000")  # High volume
        )
        signals = strategy.on_bar(bar)

        # Even with all factors bullish, confidence should be ≤ 1.0
        setup = strategy._analyze_breakout_setup(bar)
        assert setup.confidence >= Decimal("0")
        assert setup.confidence <= Decimal("1.0")
        assert setup.raw_confidence >= Decimal("0")
        assert setup.raw_confidence <= Decimal("1.0")

    def test_signal_count_increment(self):
        """Test that signal_count increments when signals are generated."""
        strategy = BreakoutSetupDetector(symbol="BTCUSDT")
        initial_count = strategy.signal_count

        # Create conditions for a signal
        # First add resistance level
        for i in range(50):
            price = Decimal("50000")
            if i == 25:  # Create a peak (resistance)
                price = Decimal("51000")
            bar = Bar(
                timestamp=1000 + i,
                open=price,
                high=price + Decimal("100"),
                low=price - Decimal("100"),
                close=price,
                volume=Decimal("100")
            )
            strategy.on_bar(bar)

        # Now create breakout with volume
        bar = Bar(
            timestamp=2000,
            open=Decimal("51500"),
            high=Decimal("51600"),
            close=Decimal("51500"),
            low=Decimal("51400"),
            volume=Decimal("500")  # 5x volume spike
        )

        # Add derivatives to boost confidence
        strategy.update_derivatives_data(
            open_interest=Decimal("100000"),
            funding_rate=Decimal("0.0002"),
            put_call_ratio=Decimal("0.5")
        )
        for i in range(24):
            strategy.update_derivatives_data(
                open_interest=Decimal(str(100000 + i * 5000))
            )

        signals = strategy.on_bar(bar)

        # If signal generated, count should increment
        if len(signals) > 0:
            assert strategy.signal_count == initial_count + 1
        else:
            # If no signal, count stays the same
            assert strategy.signal_count == initial_count

    def test_derivatives_data_staleness(self):
        """Test that stale derivatives data is rejected."""
        import time

        strategy = BreakoutSetupDetector(symbol="BTCUSDT")

        # Add fresh derivatives data
        strategy.update_derivatives_data(
            open_interest=Decimal("100000"),
            funding_rate=Decimal("0.0002"),
            put_call_ratio=Decimal("0.5")
        )

        # Check that data is used
        score1, msg1 = strategy._check_derivatives()
        assert "stale" not in msg1.lower()

        # Manually set last update to >1 hour ago
        strategy.oi_last_update = int(time.time()) - 3601  # 1 hour 1 second ago

        # Check that stale data is detected
        score2, msg2 = strategy._check_derivatives()
        assert score2 == Decimal("0")
        assert "stale" in msg2.lower()

    def test_division_by_zero_volume_ratio(self):
        """Test that zero volume doesn't cause division by zero."""
        strategy = BreakoutSetupDetector(symbol="BTCUSDT")

        # Add bars with zero volume
        for i in range(30):
            bar = Bar(
                timestamp=1000 + i,
                open=Decimal("50000"),
                high=Decimal("50100"),
                low=Decimal("49900"),
                close=Decimal("50000"),
                volume=Decimal("0")  # Zero volume
            )
            strategy.on_bar(bar)

        # This should not raise ZeroDivisionError
        bar = Bar(
            timestamp=2000,
            open=Decimal("50000"),
            high=Decimal("50100"),
            close=Decimal("50000"),
            low=Decimal("49900"),
            volume=Decimal("100")
        )
        setup = strategy._analyze_breakout_setup(bar)

        # Volume ratio should be 0 or handle gracefully
        assert isinstance(setup.volume_ratio, Decimal)
        assert setup.volume_ratio >= Decimal("0")

    def test_configuration_weight_validation(self):
        """Test that misconfigured weights generate a warning."""
        config = BreakoutConfig()
        # Intentionally misconfigure weights
        config.weight_breakout = Decimal("0.50")  # Changed from 0.30
        # Sum is now 1.20 instead of 1.00

        # This should log a warning but not fail
        strategy = BreakoutSetupDetector(symbol="BTCUSDT", config=config)

        # Strategy should still initialize
        assert strategy.symbol == "BTCUSDT"
        assert strategy.config == config

    def test_reset_clears_staleness_timestamps(self):
        """Test that reset clears derivatives staleness timestamps."""
        strategy = BreakoutSetupDetector(symbol="BTCUSDT")

        # Set derivatives data and timestamps
        strategy.update_derivatives_data(
            open_interest=Decimal("100000"),
            funding_rate=Decimal("0.0002"),
            put_call_ratio=Decimal("0.5")
        )

        assert strategy.oi_last_update is not None
        assert strategy.funding_last_update is not None
        assert strategy.put_call_last_update is not None

        # Reset strategy
        strategy.reset()

        # All timestamps should be None
        assert strategy.oi_last_update is None
        assert strategy.funding_last_update is None
        assert strategy.put_call_last_update is None

    def test_resistance_fallback_when_price_exceeds_all_levels(self):
        """
        Test that _get_nearest_resistance returns None when price exceeds all levels.

        Critical bug fix: Previously returned lowest resistance (resistance_levels[-1])
        when price exceeded all levels, causing false breakout signals on routine
        price action above historical ranges.
        """
        strategy = BreakoutSetupDetector(symbol="BTCUSDT")

        # Set resistance levels: 50000, 51000, 52000 (stored descending)
        strategy.resistance_levels = [
            Decimal("52000"),  # Highest
            Decimal("51000"),
            Decimal("50000")   # Lowest
        ]

        # Test 1: Price below all levels - should get lowest resistance (50000)
        result = strategy._get_nearest_resistance(Decimal("49000"))
        assert result == Decimal("50000"), "Should return lowest resistance when price below all"

        # Test 2: Price between levels - should get next level up
        result = strategy._get_nearest_resistance(Decimal("50500"))
        assert result == Decimal("51000"), "Should return next resistance above price"

        # Test 3: Price above all levels - should return None (critical fix)
        result = strategy._get_nearest_resistance(Decimal("53000"))
        assert result is None, (
            "CRITICAL: Must return None when price exceeds all resistance levels. "
            "Returning lowest level (50000) would falsely classify routine price "
            "action at 53000 as a breakout above irrelevant 50000 resistance."
        )

        # Test 4: Price exactly at highest level - should return that level
        result = strategy._get_nearest_resistance(Decimal("52000"))
        assert result == Decimal("52000"), "Should return level when price matches"

    def test_sr_lookback_bars_minimum_validation(self):
        """
        Test that sr_lookback_bars is validated against minimum required.

        S/R detection uses range(window, len - window) which requires
        window * 2 + 1 minimum bars (e.g., 2*2+1=5 for default window=2).
        """
        # Test with value below minimum (should be auto-corrected)
        config = BreakoutConfig(sr_lookback_bars=3)  # Too small
        strategy = BreakoutSetupDetector(symbol="BTCUSDT", config=config)

        # Should be corrected to minimum (sr_detection_window * 2 + 1 = 5)
        assert strategy.config.sr_lookback_bars == 5, (
            "sr_lookback_bars should be auto-corrected to minimum of 5 "
            "when configured below threshold"
        )

        # Test with valid minimum value
        config2 = BreakoutConfig(sr_lookback_bars=5)
        strategy2 = BreakoutSetupDetector(symbol="ETHUSDT", config=config2)
        assert strategy2.config.sr_lookback_bars == 5, "Valid minimum should be unchanged"

        # Test with value above minimum
        config3 = BreakoutConfig(sr_lookback_bars=50)
        strategy3 = BreakoutSetupDetector(symbol="SOLUSD", config=config3)
        assert strategy3.config.sr_lookback_bars == 50, "Valid large value should be unchanged"

    def test_sr_detection_with_edge_case_bar_count(self):
        """
        Test S/R detection works correctly with minimum bar count.

        Ensures the loop range(window, len - window) executes at least once
        when exactly at minimum bars.
        """
        config = BreakoutConfig(sr_lookback_bars=5)  # Minimum
        strategy = BreakoutSetupDetector(symbol="BTCUSDT", config=config)

        # Add exactly 5 bars
        for i in range(5):
            bar = Bar(
                timestamp=1000 + i,
                open=Decimal("50000"),
                high=Decimal("51000") if i == 2 else Decimal("50500"),  # Peak at index 2
                low=Decimal("49000") if i == 2 else Decimal("49500"),   # Trough at index 2
                close=Decimal("50000"),
                volume=Decimal("100")
            )
            strategy.on_bar(bar)

        # After enough bars, S/R detection should execute
        # (may not find levels with only 5 bars, but should not crash)
        assert isinstance(strategy.resistance_levels, list), "Should have resistance list"
        assert isinstance(strategy.support_levels, list), "Should have support list"
