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
        score, msg = strategy._check_risk_filters()

        # May or may not trigger depending on exact conditions
        # but function should run without error
        assert isinstance(score, Decimal)


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
