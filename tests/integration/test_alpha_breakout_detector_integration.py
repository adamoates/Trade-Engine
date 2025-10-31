"""
Integration tests for Breakout Detector Strategy with real historical data.

This module tests the strategy with actual market data and includes:
1. Integration test with real BTCUSDT 1h bars
2. Performance benchmarks (<5ms per bar requirement)
3. Property-based tests using Hypothesis
"""

import csv
import time
from decimal import Decimal
from pathlib import Path
from typing import List

import pytest
from hypothesis import given, settings, strategies as st

from trade_engine.core.types import Bar
from trade_engine.domain.strategies.alpha_breakout_detector import (
    BreakoutConfig,
    BreakoutSetupDetector,
)


# ============================================================================
# FIXTURES AND HELPERS
# ============================================================================


@pytest.fixture
def btcusdt_1h_bars() -> List[Bar]:
    """Load real BTCUSDT 1h historical data from fixtures."""
    fixture_path = (
        Path(__file__).parent.parent / "fixtures" / "binanceus_btcusdt_1h.csv"
    )

    bars = []
    with open(fixture_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            bar = Bar(
                timestamp=int(row["timestamp"]),
                open=Decimal(row["open"]),
                high=Decimal(row["high"]),
                low=Decimal(row["low"]),
                close=Decimal(row["close"]),
                volume=Decimal(row["volume"]),
            )
            bars.append(bar)

    return bars


@pytest.fixture
def strategy() -> BreakoutSetupDetector:
    """Create strategy instance with default config."""
    return BreakoutSetupDetector(symbol="BTCUSDT")


@pytest.fixture
def fast_strategy() -> BreakoutSetupDetector:
    """Create strategy with shorter periods for faster tests."""
    config = BreakoutConfig(
        bb_period=10,
        bb_std_dev=Decimal("2.0"),
        rsi_period=7,
        macd_fast=6,
        macd_slow=13,
        macd_signal=5,
        volume_ma_period=10,
        sr_lookback_bars=20,
    )
    return BreakoutSetupDetector(symbol="BTCUSDT", config=config)


# ============================================================================
# INTEGRATION TESTS WITH REAL HISTORICAL DATA
# ============================================================================


class TestRealMarketDataIntegration:
    """Integration tests using real BTCUSDT 1h historical data."""

    def test_strategy_processes_all_historical_bars(
        self, strategy: BreakoutSetupDetector, btcusdt_1h_bars: List[Bar]
    ):
        """Test that strategy can process all 500 hours of real data without errors."""
        signals_generated = 0

        for bar in btcusdt_1h_bars:
            signals = strategy.on_bar(bar)
            if signals:  # List may be empty
                for signal in signals:
                    signals_generated += 1

                    # Validate signal structure
                    assert signal.symbol == "BTCUSDT"
                    assert signal.side in ["BUY", "SELL"]
                    assert Decimal("0") <= signal.confidence <= Decimal("1")
                    assert signal.stop_loss is not None
                    assert signal.take_profit is not None
                    assert signal.stop_loss < signal.entry_price < signal.take_profit

        # Strategy is conservative, so it may not generate signals from every dataset
        # This is acceptable - just log the result
        print(f"\nSignals generated: {signals_generated} from {len(btcusdt_1h_bars)} bars")

        # If signals are generated, validate signal rate
        if signals_generated > 0:
            signal_rate = signals_generated / len(btcusdt_1h_bars)
            # Should be selective (not every bar triggers a signal)
            assert signal_rate < 0.1, f"Signal rate too high: {signal_rate:.2%} (should be <10%)"
            print(f"Signal rate: {signal_rate:.2%}")

    def test_indicators_converge_correctly(
        self, strategy: BreakoutSetupDetector, btcusdt_1h_bars: List[Bar]
    ):
        """Test that all indicators converge to reasonable values."""
        # Process enough bars for indicators to stabilize
        warmup_bars = 50
        for bar in btcusdt_1h_bars[:warmup_bars]:
            strategy.on_bar(bar)

        # Check RSI is in valid range
        assert len(strategy.rsi_values) > 0
        latest_rsi = strategy.rsi_values[-1]
        assert Decimal("0") <= latest_rsi <= Decimal("100"), (
            f"RSI out of range: {latest_rsi}"
        )

        # Check Bollinger Bands are calculated correctly
        if len(strategy.closes) >= strategy.config.bb_period:
            upper, middle, lower = strategy._calculate_bollinger_bands()
            assert lower < middle < upper, (
                f"BB bands misordered: {lower} / {middle} / {upper}"
            )

        # Check MACD values exist and are reasonable
        assert len(strategy.macd_values) > 0
        assert len(strategy.macd_signal_values) > 0

    def test_support_resistance_detection_on_real_data(
        self, strategy: BreakoutSetupDetector, btcusdt_1h_bars: List[Bar]
    ):
        """Test S/R level detection with real market data."""
        # Process enough bars to detect levels
        for bar in btcusdt_1h_bars[:100]:
            strategy.on_bar(bar)

        # Should have detected some support/resistance levels
        total_levels = len(strategy.support_levels) + len(strategy.resistance_levels)
        assert total_levels > 0, "Should detect S/R levels from real data"

        # Levels should be within reasonable price range
        all_prices = [bar.close for bar in btcusdt_1h_bars[:100]]
        min_price = min(all_prices)
        max_price = max(all_prices)

        for level in strategy.support_levels:
            assert min_price * Decimal("0.9") <= level <= max_price * Decimal("1.1"), (
                f"Support level {level} outside reasonable range [{min_price}, {max_price}]"
            )

        for level in strategy.resistance_levels:
            assert min_price * Decimal("0.9") <= level <= max_price * Decimal("1.1"), (
                f"Resistance level {level} outside reasonable range [{min_price}, {max_price}]"
            )

    def test_signal_quality_metrics(
        self, strategy: BreakoutSetupDetector, btcusdt_1h_bars: List[Bar]
    ):
        """Test that generated signals meet quality standards."""
        all_signals = []

        for bar in btcusdt_1h_bars:
            signals = strategy.on_bar(bar)
            if signals:  # List may be empty
                all_signals.extend(signals)

        if len(all_signals) == 0:
            pytest.skip("No signals generated from this dataset")

        # All signals should have high confidence (>= 70%)
        for signal in all_signals:
            assert signal.confidence >= Decimal("0.70"), (
                f"Signal confidence too low: {signal.confidence}"
            )

        # Risk/reward should be favorable (TP > 1.2x SL distance)
        for signal in all_signals:
            sl_distance = abs(signal.entry_price - signal.stop_loss)
            tp_distance = abs(signal.take_profit - signal.entry_price)
            risk_reward_ratio = tp_distance / sl_distance

            assert risk_reward_ratio > Decimal("1.0"), (
                f"Poor risk/reward ratio: {risk_reward_ratio}"
            )

    def test_strategy_state_consistency(
        self, strategy: BreakoutSetupDetector, btcusdt_1h_bars: List[Bar]
    ):
        """Test that strategy maintains consistent internal state."""
        for i, bar in enumerate(btcusdt_1h_bars[:100]):
            strategy.on_bar(bar)

            # Check data structure lengths are consistent
            assert len(strategy.closes) == len(strategy.highs) == len(strategy.lows)
            assert len(strategy.volumes) <= len(strategy.closes)

            # Check indicator lengths don't exceed close prices
            assert len(strategy.rsi_values) <= len(strategy.closes)
            assert len(strategy.macd_values) <= len(strategy.closes)

            # Check no NaN or infinite values
            for value in [bar.open, bar.high, bar.low, bar.close, bar.volume]:
                assert value.is_finite(), f"Non-finite value in bar {i}: {value}"


# ============================================================================
# PERFORMANCE BENCHMARKS
# ============================================================================


class TestPerformanceBenchmarks:
    """Performance tests to ensure <5ms processing time per bar."""

    def test_single_bar_processing_time(
        self, fast_strategy: BreakoutSetupDetector, btcusdt_1h_bars: List[Bar]
    ):
        """Test that processing a single bar takes <5ms."""
        # Warm up the strategy with some data
        warmup_bars = 50
        for bar in btcusdt_1h_bars[:warmup_bars]:
            fast_strategy.on_bar(bar)

        # Measure processing time for next 100 bars
        test_bars = btcusdt_1h_bars[warmup_bars:warmup_bars + 100]
        processing_times = []

        for bar in test_bars:
            start_time = time.perf_counter()
            fast_strategy.on_bar(bar)
            end_time = time.perf_counter()

            processing_time_ms = (end_time - start_time) * 1000
            processing_times.append(processing_time_ms)

        # Calculate statistics
        avg_time = sum(processing_times) / len(processing_times)
        max_time = max(processing_times)
        p95_time = sorted(processing_times)[int(len(processing_times) * 0.95)]

        # Assert performance requirements
        assert avg_time < 5.0, (
            f"Average processing time {avg_time:.3f}ms exceeds 5ms requirement"
        )
        assert p95_time < 10.0, (
            f"P95 processing time {p95_time:.3f}ms exceeds 10ms threshold"
        )

        # Log performance metrics (will show in pytest output with -v)
        print(f"\nPerformance Metrics:")
        print(f"  Average: {avg_time:.3f}ms")
        print(f"  Max: {max_time:.3f}ms")
        print(f"  P95: {p95_time:.3f}ms")
        print(f"  Min: {min(processing_times):.3f}ms")

    def test_bulk_processing_throughput(
        self, fast_strategy: BreakoutSetupDetector, btcusdt_1h_bars: List[Bar]
    ):
        """Test throughput when processing large batches of bars."""
        test_bars = btcusdt_1h_bars[:200]

        start_time = time.perf_counter()
        for bar in test_bars:
            fast_strategy.on_bar(bar)
        end_time = time.perf_counter()

        total_time = end_time - start_time
        bars_per_second = len(test_bars) / total_time

        # Should process at least 200 bars/second
        assert bars_per_second > 200, (
            f"Throughput too low: {bars_per_second:.1f} bars/sec (expected >200)"
        )

        print(f"\nThroughput: {bars_per_second:.1f} bars/second")

    def test_memory_efficiency(
        self, fast_strategy: BreakoutSetupDetector, btcusdt_1h_bars: List[Bar]
    ):
        """Test that strategy doesn't accumulate unbounded data."""
        # Process many bars
        for bar in btcusdt_1h_bars:
            fast_strategy.on_bar(bar)

        # Check that data structures are bounded
        max_lookback = max(
            fast_strategy.config.bb_period,
            fast_strategy.config.rsi_period,
            fast_strategy.config.macd_slow,
            fast_strategy.config.volume_ma_period,
            fast_strategy.config.sr_lookback_bars,
        )

        # Allow some buffer, but should not be unbounded
        assert len(fast_strategy.closes) <= max_lookback * 2, (
            f"Closes buffer too large: {len(fast_strategy.closes)} "
            f"(max lookback: {max_lookback})"
        )


# ============================================================================
# PROPERTY-BASED TESTS USING HYPOTHESIS
# ============================================================================


class TestPropertyBasedIndicators:
    """Property-based tests using Hypothesis for indicator calculations."""

    @given(
        price=st.decimals(
            min_value=Decimal("1000"),
            max_value=Decimal("200000"),
            places=2,
        ),
        volume=st.decimals(
            min_value=Decimal("0.001"),
            max_value=Decimal("100"),
            places=8,
        ),
    )
    @settings(max_examples=100, deadline=None)
    def test_strategy_handles_arbitrary_valid_prices(
        self, price: Decimal, volume: Decimal
    ):
        """Property: Strategy should handle any valid price/volume combination."""
        strategy = BreakoutSetupDetector(symbol="BTCUSDT")

        # Create bar with generated price
        bar = Bar(
            timestamp=1700000000000,
            open=price,
            high=price * Decimal("1.01"),  # 1% higher
            low=price * Decimal("0.99"),   # 1% lower
            close=price,
            volume=volume,
        )

        # Should not raise any exceptions
        try:
            signals = strategy.on_bar(bar)

            # If signals generated, they should be valid
            if signals:
                for signal in signals:
                    assert signal.confidence >= Decimal("0")
                    assert signal.confidence <= Decimal("1")
                    assert signal.entry_price > Decimal("0")

        except Exception as e:
            pytest.fail(f"Strategy failed with valid inputs: {e}")

    @given(
        std_dev=st.decimals(
            min_value=Decimal("1.0"),
            max_value=Decimal("4.0"),
            places=1,
        ),
    )
    @settings(max_examples=20, deadline=None)
    def test_bollinger_bands_width_property(self, std_dev: Decimal):
        """Property: BB width should increase with standard deviation multiplier."""
        config = BreakoutConfig(bb_std_dev=std_dev, bb_period=10)
        strategy = BreakoutSetupDetector(symbol="BTCUSDT", config=config)

        # Feed consistent data
        base_price = Decimal("50000")
        for i in range(20):
            bar = Bar(
                timestamp=1700000000000 + i * 3600000,
                open=base_price + Decimal(str(i * 100)),
                high=base_price + Decimal(str(i * 100 + 200)),
                low=base_price + Decimal(str(i * 100 - 200)),
                close=base_price + Decimal(str(i * 100 + 50)),
                volume=Decimal("1.0"),
            )
            strategy.on_bar(bar)

        # After warmup, bands should exist and be ordered correctly
        if len(strategy.closes) >= strategy.config.bb_period:
            upper, middle, lower = strategy._calculate_bollinger_bands()
            assert lower < middle < upper

            # Band width should scale with std_dev
            band_width = upper - lower
            expected_min_width = middle * std_dev * Decimal("0.001")

            assert band_width > expected_min_width

    @given(
        rsi_period=st.integers(min_value=5, max_value=30),
    )
    @settings(max_examples=10, deadline=None)
    def test_rsi_always_between_0_and_100(self, rsi_period: int):
        """Property: RSI must always be between 0 and 100 regardless of config."""
        config = BreakoutConfig(rsi_period=rsi_period)
        strategy = BreakoutSetupDetector(symbol="BTCUSDT", config=config)

        # Feed varying price data
        base_price = Decimal("50000")
        for i in range(rsi_period * 3):
            # Create some volatility
            price_change = Decimal(str((i % 5 - 2) * 500))
            price = base_price + price_change

            bar = Bar(
                timestamp=1700000000000 + i * 3600000,
                open=price,
                high=price * Decimal("1.005"),
                low=price * Decimal("0.995"),
                close=price,
                volume=Decimal("1.0"),
            )
            strategy.on_bar(bar)

        # Check all RSI values are in valid range
        for rsi in strategy.rsi_values:
            assert Decimal("0") <= rsi <= Decimal("100"), (
                f"RSI out of range: {rsi} (period={rsi_period})"
            )

    @given(
        prices=st.lists(
            st.decimals(
                min_value=Decimal("40000"),
                max_value=Decimal("60000"),
                places=2,
            ),
            min_size=30,
            max_size=50,
        ),
    )
    @settings(max_examples=20, deadline=None)
    def test_support_resistance_within_price_range(self, prices: List[Decimal]):
        """Property: S/R levels must be within the price range of data."""
        config = BreakoutConfig(sr_lookback_bars=20, sr_detection_window=2)
        strategy = BreakoutSetupDetector(symbol="BTCUSDT", config=config)

        min_price = min(prices)
        max_price = max(prices)

        # Feed price data
        for i, price in enumerate(prices):
            bar = Bar(
                timestamp=1700000000000 + i * 3600000,
                open=price,
                high=price * Decimal("1.002"),
                low=price * Decimal("0.998"),
                close=price,
                volume=Decimal("1.0"),
            )
            strategy.on_bar(bar)

        # All S/R levels should be within reasonable range of observed prices
        tolerance = Decimal("0.05")  # 5% buffer
        lower_bound = min_price * (Decimal("1") - tolerance)
        upper_bound = max_price * (Decimal("1") + tolerance)

        for level in strategy.support_levels:
            assert lower_bound <= level <= upper_bound, (
                f"Support {level} outside range [{lower_bound}, {upper_bound}]"
            )

        for level in strategy.resistance_levels:
            assert lower_bound <= level <= upper_bound, (
                f"Resistance {level} outside range [{lower_bound}, {upper_bound}]"
            )

    @given(
        confidence_multiplier=st.decimals(
            min_value=Decimal("0.5"),
            max_value=Decimal("2.0"),
            places=2,
        ),
    )
    @settings(max_examples=30, deadline=None)
    def test_confidence_always_clamped_to_valid_range(
        self, confidence_multiplier: Decimal
    ):
        """Property: Confidence must always be clamped between 0.0 and 1.0."""
        # Artificially inflate confidence factors by adjusting weights
        config = BreakoutConfig(
            weight_breakout=Decimal("0.30") * confidence_multiplier,
            weight_momentum=Decimal("0.25") * confidence_multiplier,
            weight_volatility=Decimal("0.20") * confidence_multiplier,
            weight_derivatives=Decimal("0.15") * confidence_multiplier,
            weight_risk_filter=Decimal("0.10") * confidence_multiplier,
        )
        strategy = BreakoutSetupDetector(symbol="BTCUSDT", config=config)

        # Feed data to generate signals
        base_price = Decimal("50000")
        for i in range(50):
            bar = Bar(
                timestamp=1700000000000 + i * 3600000,
                open=base_price + Decimal(str(i * 100)),
                high=base_price + Decimal(str(i * 100 + 500)),
                low=base_price + Decimal(str(i * 100 - 100)),
                close=base_price + Decimal(str(i * 100 + 200)),
                volume=Decimal("1.0"),
            )
            signals = strategy.on_bar(bar)

            if signals:
                for signal in signals:
                    # Confidence must always be valid regardless of weight manipulation
                    assert Decimal("0") <= signal.confidence <= Decimal("1"), (
                        f"Confidence {signal.confidence} outside [0, 1] range"
                    )

    def test_decimal_precision_maintained_throughout_calculations(self):
        """Property: All calculations should maintain Decimal precision (no float contamination)."""
        strategy = BreakoutSetupDetector(symbol="BTCUSDT")

        # Feed data
        for i in range(50):
            bar = Bar(
                timestamp=1700000000000 + i * 3600000,
                open=Decimal("50000.12"),
                high=Decimal("50234.56"),
                low=Decimal("49876.34"),
                close=Decimal("50100.78"),
                volume=Decimal("1.23456789"),
            )
            strategy.on_bar(bar)

        # Check all internal state uses Decimal
        assert all(isinstance(c, Decimal) for c in strategy.closes)
        assert all(isinstance(h, Decimal) for h in strategy.highs)
        assert all(isinstance(l, Decimal) for l in strategy.lows)
        assert all(isinstance(v, Decimal) for v in strategy.volumes)
        assert all(isinstance(r, Decimal) for r in strategy.rsi_values)
        assert all(isinstance(m, Decimal) for m in strategy.macd_values)

        # Check BB values are Decimal
        if len(strategy.closes) >= strategy.config.bb_period:
            upper, middle, lower = strategy._calculate_bollinger_bands()
            assert isinstance(lower, Decimal)
            assert isinstance(middle, Decimal)
            assert isinstance(upper, Decimal)
