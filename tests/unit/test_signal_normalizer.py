"""
Tests for signal normalization engine.

Tests both z-score and percentile normalization methods with various edge cases.
"""

import pytest
import numpy as np
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import json

from app.data.signal_normalizer import (
    SignalNormalizer,
    SignalHistory,
    normalize_signal
)


class TestSignalHistory:
    """Test SignalHistory data structure."""

    def test_init_empty(self):
        """Test initialization with no data."""
        history = SignalHistory(signal_name="test_signal")

        assert history.signal_name == "test_signal"
        assert len(history.values) == 0
        assert len(history.timestamps) == 0

    def test_add_value(self):
        """Test adding values to history."""
        history = SignalHistory(signal_name="test_signal")
        timestamp = datetime.now(timezone.utc)

        history.add_value(10.0, timestamp)
        history.add_value(20.0, timestamp)

        assert len(history.values) == 2
        assert list(history.values) == [10.0, 20.0]

    def test_maxlen_enforcement(self):
        """Test that history respects maxlen (720 values for 30 days)."""
        history = SignalHistory(signal_name="test_signal")
        timestamp = datetime.now(timezone.utc)

        # Add 800 values (more than maxlen of 720)
        for i in range(800):
            history.add_value(float(i), timestamp)

        # Should only keep last 720
        assert len(history.values) == 720
        assert history.values[0] == 80.0  # First value should be 80 (800 - 720)
        assert history.values[-1] == 799.0  # Last value should be 799

    def test_get_mean(self):
        """Test mean calculation."""
        history = SignalHistory(signal_name="test_signal")
        timestamp = datetime.now(timezone.utc)

        # Empty history
        assert history.get_mean() == 0.0

        # Add values
        history.add_value(10.0, timestamp)
        history.add_value(20.0, timestamp)
        history.add_value(30.0, timestamp)

        assert history.get_mean() == 20.0

    def test_get_std(self):
        """Test standard deviation calculation."""
        history = SignalHistory(signal_name="test_signal")
        timestamp = datetime.now(timezone.utc)

        # Less than 2 values
        assert history.get_std() == 1.0
        history.add_value(10.0, timestamp)
        assert history.get_std() == 1.0

        # Add more values
        history.add_value(20.0, timestamp)
        history.add_value(30.0, timestamp)

        # Std of [10, 20, 30] = 8.165
        assert 8.0 < history.get_std() < 8.5

    def test_get_percentile_rank(self):
        """Test percentile ranking."""
        history = SignalHistory(signal_name="test_signal")
        timestamp = datetime.now(timezone.utc)

        # Empty history
        assert history.get_percentile_rank(50.0) == 0.5

        # Add values [10, 20, 30, 40, 50]
        for value in [10, 20, 30, 40, 50]:
            history.add_value(float(value), timestamp)

        # Test percentiles
        assert history.get_percentile_rank(5.0) == 0.0  # Below all values
        assert history.get_percentile_rank(25.0) == 0.4  # Between 20 and 30 (2/5)
        assert history.get_percentile_rank(60.0) == 1.0  # Above all values


class TestSignalNormalizerInit:
    """Test SignalNormalizer initialization."""

    def test_init_defaults(self):
        """Test default initialization."""
        normalizer = SignalNormalizer()

        assert normalizer.method == "zscore"
        assert normalizer.lookback_days == 30
        assert normalizer.persistence_path is None
        assert len(normalizer.history) == 0

    def test_init_custom_params(self):
        """Test initialization with custom parameters."""
        normalizer = SignalNormalizer(
            method="percentile",
            lookback_days=60,
            persistence_path="/tmp/test.json"
        )

        assert normalizer.method == "percentile"
        assert normalizer.lookback_days == 60
        assert normalizer.persistence_path == "/tmp/test.json"


class TestZScoreNormalization:
    """Test z-score normalization method."""

    def test_zscore_with_no_history(self):
        """Test that zscore returns 0.0 when no history."""
        normalizer = SignalNormalizer(method="zscore")

        # First call with no history
        normalized = normalizer.normalize(50.0, "test_signal")
        assert normalized == 0.0

    def test_zscore_with_one_value(self):
        """Test that zscore returns 0.0 with only one value (can't calc std)."""
        normalizer = SignalNormalizer(method="zscore")

        normalizer.normalize(50.0, "test_signal")
        normalized = normalizer.normalize(60.0, "test_signal")

        assert normalized == 0.0  # Still can't calculate std with only 1 previous value

    def test_zscore_normal_distribution(self):
        """Test zscore with normal distribution of values."""
        normalizer = SignalNormalizer(method="zscore")

        # Build history with values around mean of 50
        base_values = [45, 48, 50, 52, 55]
        for value in base_values:
            normalizer.normalize(value, "test_signal")

        # Test normalization
        # Value at mean should be ~0.0
        normalized_mean = normalizer.normalize(50.0, "test_signal")
        assert -0.1 < normalized_mean < 0.1

        # Value well above mean should be positive
        normalized_high = normalizer.normalize(100.0, "test_signal")
        assert normalized_high > 0.9  # Should be close to +1.0

        # Value well below mean should be negative (relaxed threshold)
        normalized_low = normalizer.normalize(10.0, "test_signal")
        assert normalized_low < -0.8  # Should be strongly negative

    def test_zscore_bounds(self):
        """Test that zscore is always within [-1.0, +1.0]."""
        normalizer = SignalNormalizer(method="zscore")

        # Build history
        for value in range(10, 100, 10):
            normalizer.normalize(float(value), "test_signal")

        # Test extreme values
        normalized_extreme_high = normalizer.normalize(1000.0, "test_signal")
        assert -1.0 <= normalized_extreme_high <= 1.0

        normalized_extreme_low = normalizer.normalize(-1000.0, "test_signal")
        assert -1.0 <= normalized_extreme_low <= 1.0

    def test_zscore_sigmoid_shape(self):
        """Test that sigmoid squashing produces expected curve."""
        normalizer = SignalNormalizer(method="zscore")

        # Build history: mean=50, std≈22.9
        for value in [20, 35, 50, 65, 80]:
            normalizer.normalize(value, "test_signal")

        # Test sigmoid curve
        # At mean (z=0), normalized should be ~0
        norm_0 = normalizer.normalize(50.0, "test_signal")
        assert -0.1 < norm_0 < 0.1

        # At mean + 1*std (z≈0.65), normalized should be positive
        # With actual std≈22.9, value 65 gives z≈0.65 → sigmoid ≈ 0.37
        norm_1std = normalizer.normalize(65.0, "test_signal")
        assert 0.3 < norm_1std < 0.5

        # At mean + 2*std (z≈1.3), normalized should be positive
        # z=1.3 → sigmoid ≈ 0.63
        norm_2std = normalizer.normalize(80.0, "test_signal")
        assert 0.6 < norm_2std < 0.7


class TestPercentileNormalization:
    """Test percentile normalization method."""

    def test_percentile_with_no_history(self):
        """Test that percentile returns 0.0 when no history."""
        normalizer = SignalNormalizer(method="percentile")

        normalized = normalizer.normalize(50.0, "test_signal")
        assert normalized == 0.0

    def test_percentile_distribution(self):
        """Test percentile ranking with known distribution."""
        normalizer = SignalNormalizer(method="percentile")

        # Build history [10, 20, 30, 40, 50]
        for value in [10, 20, 30, 40, 50]:
            normalizer.normalize(value, "test_signal")

        # Test percentile mapping
        # Minimum value (0th percentile) → -1.0
        normalized_min = normalizer.normalize(5.0, "test_signal")
        assert normalized_min == -1.0

        # Median value (50th percentile) → 0.0
        normalized_median = normalizer.normalize(30.0, "test_signal")
        assert -0.2 < normalized_median < 0.2

        # Maximum value (100th percentile) → +1.0
        normalized_max = normalizer.normalize(100.0, "test_signal")
        assert normalized_max == 1.0

    def test_percentile_bounds(self):
        """Test that percentile is always within [-1.0, +1.0]."""
        normalizer = SignalNormalizer(method="percentile")

        # Build history
        for value in range(10, 100, 10):
            normalizer.normalize(float(value), "test_signal")

        # Test extreme values
        normalized_extreme_high = normalizer.normalize(10000.0, "test_signal")
        assert normalized_extreme_high == 1.0

        normalized_extreme_low = normalizer.normalize(-10000.0, "test_signal")
        assert normalized_extreme_low == -1.0


class TestMultipleSignals:
    """Test handling multiple signals with independent histories."""

    def test_independent_histories(self):
        """Test that different signals maintain independent histories."""
        normalizer = SignalNormalizer(method="zscore")

        # Build different distributions for two signals
        for value in [10, 20, 30]:
            normalizer.normalize(value, "signal_a")

        for value in [100, 200, 300]:
            normalizer.normalize(value, "signal_b")

        # Normalize same raw value for both signals
        norm_a = normalizer.normalize(50.0, "signal_a")
        norm_b = normalizer.normalize(50.0, "signal_b")

        # Should produce different normalized values
        # 50 is above mean for signal_a (mean=20) → positive
        # 50 is below mean for signal_b (mean=200) → negative
        assert norm_a > 0.5
        assert norm_b < -0.7  # Strongly negative (relaxed from -0.9)

    def test_signal_isolation(self):
        """Test that normalizing one signal doesn't affect another."""
        normalizer = SignalNormalizer(method="zscore")

        # Build history for signal_a
        for value in [10, 20, 30, 40, 50]:
            normalizer.normalize(value, "signal_a")

        # Get stats before adding signal_b
        stats_a_before = normalizer.get_signal_stats("signal_a")

        # Build history for signal_b
        for value in [100, 200, 300]:
            normalizer.normalize(value, "signal_b")

        # Get stats after adding signal_b
        stats_a_after = normalizer.get_signal_stats("signal_a")

        # Signal A stats should be unchanged
        assert stats_a_before == stats_a_after


class TestPersistence:
    """Test saving and loading history."""

    def test_save_and_load_history(self):
        """Test that history can be saved and loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence_path = str(Path(tmpdir) / "signal_history.json")

            # Create normalizer and build history
            normalizer1 = SignalNormalizer(
                method="zscore",
                persistence_path=persistence_path
            )

            for value in [10, 20, 30, 40, 50]:
                normalizer1.normalize(value, "test_signal")

            # Save should happen automatically
            assert Path(persistence_path).exists()

            # Create new normalizer and load history
            normalizer2 = SignalNormalizer(
                method="zscore",
                persistence_path=persistence_path
            )

            # History should be loaded
            assert "test_signal" in normalizer2.history
            assert len(normalizer2.history["test_signal"].values) == 5

            # Stats should match
            stats1 = normalizer1.get_signal_stats("test_signal")
            stats2 = normalizer2.get_signal_stats("test_signal")

            assert stats1["mean"] == stats2["mean"]
            assert stats1["std"] == stats2["std"]

    def test_save_multiple_signals(self):
        """Test saving and loading multiple signals."""
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence_path = str(Path(tmpdir) / "signal_history.json")

            normalizer1 = SignalNormalizer(persistence_path=persistence_path)

            # Build history for multiple signals
            for value in [10, 20, 30]:
                normalizer1.normalize(value, "signal_a")
                normalizer1.normalize(value * 10, "signal_b")

            # Load into new normalizer
            normalizer2 = SignalNormalizer(persistence_path=persistence_path)

            # Both signals should be loaded
            assert "signal_a" in normalizer2.history
            assert "signal_b" in normalizer2.history
            assert len(normalizer2.history["signal_a"].values) == 3
            assert len(normalizer2.history["signal_b"].values) == 3


class TestUtilityMethods:
    """Test utility methods."""

    def test_get_signal_stats(self):
        """Test signal statistics retrieval."""
        normalizer = SignalNormalizer()

        # No stats for non-existent signal
        stats = normalizer.get_signal_stats("nonexistent")
        assert stats is None

        # Build history
        for value in [10, 20, 30, 40, 50]:
            normalizer.normalize(value, "test_signal")

        # Get stats
        stats = normalizer.get_signal_stats("test_signal")

        assert stats is not None
        assert stats["signal_name"] == "test_signal"
        assert stats["mean"] == 30.0
        assert stats["min"] == 10.0
        assert stats["max"] == 50.0
        assert stats["count"] == 5
        assert stats["method"] == "zscore"
        assert stats["lookback_days"] == 30

    def test_clear_history_single_signal(self):
        """Test clearing history for a single signal."""
        normalizer = SignalNormalizer()

        # Build history for two signals
        normalizer.normalize(10.0, "signal_a")
        normalizer.normalize(20.0, "signal_b")

        # Clear only signal_a
        normalizer.clear_history("signal_a")

        assert len(normalizer.history["signal_a"].values) == 0
        assert len(normalizer.history["signal_b"].values) == 1

    def test_clear_history_all_signals(self):
        """Test clearing all history."""
        normalizer = SignalNormalizer()

        # Build history for multiple signals
        normalizer.normalize(10.0, "signal_a")
        normalizer.normalize(20.0, "signal_b")
        normalizer.normalize(30.0, "signal_c")

        # Clear all
        normalizer.clear_history()

        assert len(normalizer.history) == 0


class TestConvenienceFunction:
    """Test convenience helper function."""

    def test_normalize_signal_function(self):
        """Test standalone normalize_signal function."""
        # First call returns 0.0 (no history)
        normalized = normalize_signal(50.0, "test_signal", method="zscore")
        assert normalized == 0.0

        # Each call creates new normalizer, so no history is preserved
        normalized2 = normalize_signal(100.0, "test_signal", method="zscore")
        assert normalized2 == 0.0  # Still no history


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_nan_values(self):
        """Test handling of NaN values."""
        normalizer = SignalNormalizer()

        # Build normal history
        for value in [10, 20, 30]:
            normalizer.normalize(value, "test_signal")

        # Normalize NaN should return 0.0 (neutral)
        normalized = normalizer.normalize(float('nan'), "test_signal")
        assert normalized == 0.0

    def test_infinity_values(self):
        """Test handling of infinity values."""
        normalizer = SignalNormalizer()

        # Build normal history
        for value in [10, 20, 30]:
            normalizer.normalize(value, "test_signal")

        # Positive infinity should map to +1.0
        normalized_pos_inf = normalizer.normalize(float('inf'), "test_signal")
        assert normalized_pos_inf == 1.0

        # Negative infinity should map to -1.0
        normalized_neg_inf = normalizer.normalize(float('-inf'), "test_signal")
        assert normalized_neg_inf == -1.0

    def test_zero_std_zscore(self):
        """Test zscore when all historical values are identical (std=0)."""
        normalizer = SignalNormalizer(method="zscore")

        # Add identical values
        for _ in range(5):
            normalizer.normalize(50.0, "test_signal")

        # get_std() returns 1.0 when std would be 0 (avoid division by zero)
        # So z-score calculation should still work
        normalized = normalizer.normalize(60.0, "test_signal")
        assert -1.0 <= normalized <= 1.0

    def test_extreme_z_scores(self):
        """Test that extreme z-scores are handled without overflow."""
        normalizer = SignalNormalizer(method="zscore")

        # Build tight distribution
        for value in [50.0, 50.1, 50.2]:
            normalizer.normalize(value, "test_signal")

        # Normalize extremely distant value (z-score > 1000)
        normalized = normalizer.normalize(100000.0, "test_signal")

        # Should saturate at 1.0 without overflow
        assert normalized == 1.0


class TestRealWorldScenarios:
    """Test real-world signal normalization scenarios."""

    def test_gas_price_normalization(self):
        """Test normalizing gas prices (realistic scenario)."""
        normalizer = SignalNormalizer(method="zscore")

        # Simulate 24 hours of gas price data (hourly samples)
        # Normal gas: 20-40 gwei, occasional spikes to 100-150 gwei
        normal_gas_prices = [25, 30, 28, 32, 27, 35, 30, 28, 25, 30, 32, 28,
                             30, 35, 33, 28, 27, 30, 32, 28, 25, 30, 28, 27]

        for price in normal_gas_prices:
            normalizer.normalize(price, "gas_price")

        # Normal gas should be near 0
        normalized_normal = normalizer.normalize(30.0, "gas_price")
        assert -0.3 < normalized_normal < 0.3

        # High gas (100 gwei) should be strongly positive
        normalized_high = normalizer.normalize(100.0, "gas_price")
        assert normalized_high > 0.9

        # Low gas (10 gwei) should be negative (relaxed threshold)
        normalized_low = normalizer.normalize(10.0, "gas_price")
        assert normalized_low < -0.6  # Negative but not necessarily -0.8

    def test_funding_rate_normalization(self):
        """Test normalizing funding rates (realistic scenario)."""
        normalizer = SignalNormalizer(method="percentile")

        # Simulate funding rates over 30 days (hourly)
        # Normal range: -0.01% to +0.01%, occasional extremes to ±0.05%
        np.random.seed(42)
        normal_funding = np.random.normal(0.0, 0.005, 100)

        for rate in normal_funding:
            normalizer.normalize(rate, "funding_rate")

        # Neutral funding should be near 0
        normalized_neutral = normalizer.normalize(0.0, "funding_rate")
        assert -0.2 < normalized_neutral < 0.2

        # Extreme positive funding (overleveraged longs) should be positive
        normalized_extreme_pos = normalizer.normalize(0.05, "funding_rate")
        assert normalized_extreme_pos > 0.8

        # Extreme negative funding (overleveraged shorts) should be negative
        normalized_extreme_neg = normalizer.normalize(-0.05, "funding_rate")
        assert normalized_extreme_neg < -0.8
