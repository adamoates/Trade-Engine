"""
Signal normalization engine for converting raw on-chain signals to [-1.0, +1.0] range.

This module implements the normalization strategies from the quantitative analysis:
- Z-score normalization with sigmoid squashing
- Percentile ranking normalization
- Rolling 30-day historical lookback

All raw signals (gas prices, funding rates, whale transfers, etc.) are normalized
to a common scale before being combined into the final trading signal.
"""

import numpy as np
from typing import Dict, List, Optional, Literal
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
from loguru import logger


NormalizationMethod = Literal["zscore", "percentile"]


@dataclass
class SignalHistory:
    """Historical data for a single signal."""
    signal_name: str
    values: deque = field(default_factory=lambda: deque(maxlen=720))  # 30 days * 24 hours
    timestamps: deque = field(default_factory=lambda: deque(maxlen=720))

    def add_value(self, value: float, timestamp: datetime):
        """Add new value to history."""
        self.values.append(value)
        self.timestamps.append(timestamp)

    def get_values(self) -> List[float]:
        """Get all historical values as list."""
        return list(self.values)

    def get_mean(self) -> float:
        """Calculate mean of historical values."""
        if not self.values:
            return 0.0
        return float(np.mean(self.values))

    def get_std(self) -> float:
        """Calculate standard deviation of historical values."""
        if len(self.values) < 2:
            return 1.0  # Avoid division by zero
        std = float(np.std(self.values))
        return std if std > 0 else 1.0

    def get_percentile_rank(self, value: float) -> float:
        """Get percentile rank of value within historical data."""
        if not self.values:
            return 0.5  # Neutral if no history

        values_array = np.array(self.values)
        percentile = (values_array < value).sum() / len(values_array)
        return float(percentile)


class SignalNormalizer:
    """
    Normalize raw signals to [-1.0, +1.0] range.

    Implements two normalization methods:

    1. Z-Score Normalization (default):
       - Calculate z-score: z = (x - μ) / σ
       - Apply sigmoid squashing: normalized = 2 / (1 + e^(-z)) - 1
       - Maps unbounded z-scores to [-1.0, +1.0] with smooth saturation

    2. Percentile Ranking:
       - Rank value within historical distribution
       - Map percentile to [-1.0, +1.0]: normalized = 2 * percentile - 1
       - 50th percentile → 0, 100th percentile → +1.0, 0th percentile → -1.0

    Example:
        >>> normalizer = SignalNormalizer(method="zscore", lookback_days=30)
        >>>
        >>> # First call with no history returns 0.0 (neutral)
        >>> normalized = normalizer.normalize(50.0, "gas_price")
        >>> print(normalized)  # 0.0
        >>>
        >>> # Build up history over time
        >>> for price in [40, 45, 50, 55, 60, 65, 70]:
        ...     normalizer.normalize(price, "gas_price")
        >>>
        >>> # Now extreme values are properly normalized
        >>> normalizer.normalize(100.0, "gas_price")  # Returns ~0.95 (very high)
        >>> normalizer.normalize(30.0, "gas_price")   # Returns ~-0.85 (very low)
    """

    def __init__(
        self,
        method: NormalizationMethod = "zscore",
        lookback_days: int = 30,
        persistence_path: Optional[str] = None
    ):
        """
        Initialize signal normalizer.

        Args:
            method: Normalization method ("zscore" or "percentile")
            lookback_days: Number of days of history to maintain (default: 30)
            persistence_path: Optional path to save/load history (for persistence across restarts)
        """
        self.method = method
        self.lookback_days = lookback_days
        self.persistence_path = persistence_path

        # History storage: {signal_name: SignalHistory}
        self.history: Dict[str, SignalHistory] = {}

        # Load persisted history if available
        if persistence_path:
            self._load_history()

    def normalize(
        self,
        value: float,
        signal_name: str,
        timestamp: Optional[datetime] = None
    ) -> float:
        """
        Normalize signal value to [-1.0, +1.0] range.

        Args:
            value: Raw signal value to normalize
            signal_name: Identifier for the signal (e.g., "gas_price", "funding_rate")
            timestamp: Optional timestamp for the value (defaults to now)

        Returns:
            Normalized value in [-1.0, +1.0] range

        Example:
            >>> normalizer = SignalNormalizer()
            >>> normalizer.normalize(150.0, "gas_price")  # High gas
            >>> # Returns ~0.8 after building history
        """
        # Handle NaN and infinity
        if np.isnan(value):
            logger.warning(f"NaN value received for {signal_name}, returning 0.0")
            return 0.0

        if np.isinf(value):
            return 1.0 if value > 0 else -1.0

        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        # Initialize history for new signals
        if signal_name not in self.history:
            self.history[signal_name] = SignalHistory(signal_name=signal_name)

        # Get signal history
        signal_history = self.history[signal_name]

        # Normalize based on method
        if self.method == "zscore":
            normalized = self._z_score_normalize(value, signal_history)
        else:  # percentile
            normalized = self._percentile_normalize(value, signal_history)

        # Add value to history AFTER normalization (so we're always predicting future)
        signal_history.add_value(value, timestamp)

        # Persist if configured
        if self.persistence_path:
            self._save_history()

        return normalized

    def _z_score_normalize(self, value: float, signal_history: SignalHistory) -> float:
        """
        Z-score normalization with sigmoid squashing.

        Formula:
            z = (x - μ) / σ
            normalized = 2 / (1 + e^(-z)) - 1

        This maps unbounded z-scores to [-1.0, +1.0]:
        - z = 0 (mean) → normalized = 0.0
        - z = +3 (3 std above mean) → normalized ≈ +0.95
        - z = -3 (3 std below mean) → normalized ≈ -0.95
        - z = ±∞ → normalized → ±1.0 (asymptotic)

        Args:
            value: Raw signal value
            signal_history: Historical data for this signal

        Returns:
            Normalized value in [-1.0, +1.0]
        """
        # Need at least 2 values to calculate std
        if len(signal_history.values) < 2:
            return 0.0  # Neutral until we have enough history

        # Calculate z-score
        mean = signal_history.get_mean()
        std = signal_history.get_std()
        z = (value - mean) / std

        # Apply sigmoid squashing to map to [-1.0, +1.0]
        # Formula: 2 / (1 + e^(-z)) - 1
        try:
            normalized = 2.0 / (1.0 + np.exp(-z)) - 1.0
        except (OverflowError, FloatingPointError):
            # Handle extreme z-scores
            normalized = 1.0 if z > 0 else -1.0

        # Ensure bounds (numerical stability)
        return float(np.clip(normalized, -1.0, 1.0))

    def _percentile_normalize(self, value: float, signal_history: SignalHistory) -> float:
        """
        Percentile ranking normalization.

        Formula:
            percentile = rank(x) / n
            normalized = 2 * percentile - 1

        This maps percentile rank to [-1.0, +1.0]:
        - 0th percentile (minimum) → -1.0
        - 50th percentile (median) → 0.0
        - 100th percentile (maximum) → +1.0

        Args:
            value: Raw signal value
            signal_history: Historical data for this signal

        Returns:
            Normalized value in [-1.0, +1.0]
        """
        # Need at least 1 value for percentile ranking
        if not signal_history.values:
            return 0.0  # Neutral if no history

        # Get percentile rank
        percentile = signal_history.get_percentile_rank(value)

        # Map [0, 1] to [-1, +1]
        normalized = 2.0 * percentile - 1.0

        return float(np.clip(normalized, -1.0, 1.0))

    def get_signal_stats(self, signal_name: str) -> Optional[Dict]:
        """
        Get statistical summary for a signal's history.

        Args:
            signal_name: Name of the signal

        Returns:
            Dict with mean, std, min, max, count, or None if signal not found

        Example:
            >>> stats = normalizer.get_signal_stats("gas_price")
            >>> print(f"Mean: {stats['mean']}, Std: {stats['std']}")
        """
        if signal_name not in self.history:
            return None

        signal_history = self.history[signal_name]

        if not signal_history.values:
            return None

        values = signal_history.get_values()

        return {
            "signal_name": signal_name,
            "mean": float(np.mean(values)),
            "std": float(np.std(values)),
            "min": float(np.min(values)),
            "max": float(np.max(values)),
            "count": len(values),
            "lookback_days": self.lookback_days,
            "method": self.method
        }

    def clear_history(self, signal_name: Optional[str] = None):
        """
        Clear historical data.

        Args:
            signal_name: Clear specific signal, or all signals if None

        Example:
            >>> normalizer.clear_history("gas_price")  # Clear one signal
            >>> normalizer.clear_history()  # Clear all signals
        """
        if signal_name:
            if signal_name in self.history:
                self.history[signal_name] = SignalHistory(signal_name=signal_name)
                logger.info(f"Cleared history for signal: {signal_name}")
        else:
            self.history = {}
            logger.info("Cleared all signal history")

    def _save_history(self):
        """Save history to disk for persistence across restarts."""
        if not self.persistence_path:
            return

        try:
            # Create directory if needed
            Path(self.persistence_path).parent.mkdir(parents=True, exist_ok=True)

            # Serialize history
            data = {}
            for signal_name, signal_history in self.history.items():
                data[signal_name] = {
                    "values": list(signal_history.values),
                    "timestamps": [ts.isoformat() for ts in signal_history.timestamps]
                }

            # Write to file
            with open(self.persistence_path, "w") as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Saved signal history to {self.persistence_path}")

        except Exception as e:
            logger.warning(f"Failed to save signal history: {e}")

    def _load_history(self):
        """Load history from disk if available."""
        if not self.persistence_path or not os.path.exists(self.persistence_path):
            return

        try:
            with open(self.persistence_path, "r") as f:
                data = json.load(f)

            # Deserialize history
            for signal_name, signal_data in data.items():
                signal_history = SignalHistory(signal_name=signal_name)

                # Restore values and timestamps
                for value, timestamp_str in zip(signal_data["values"], signal_data["timestamps"]):
                    timestamp = datetime.fromisoformat(timestamp_str)
                    signal_history.add_value(value, timestamp)

                self.history[signal_name] = signal_history

            logger.info(f"Loaded signal history from {self.persistence_path} ({len(self.history)} signals)")

        except Exception as e:
            logger.warning(f"Failed to load signal history: {e}")


# Convenience function for quick normalization
def normalize_signal(
    value: float,
    signal_name: str,
    method: NormalizationMethod = "zscore"
) -> float:
    """
    Quick helper to normalize a signal value.

    Note: This creates a new normalizer each time, so history is not preserved.
    For production use, create a persistent SignalNormalizer instance.

    Args:
        value: Raw signal value
        signal_name: Signal identifier
        method: Normalization method

    Returns:
        Normalized value in [-1.0, +1.0]

    Example:
        >>> from app.data.signal_normalizer import normalize_signal
        >>> normalized = normalize_signal(150.0, "gas_price", method="zscore")
        >>> # Returns 0.0 on first call (no history)
    """
    normalizer = SignalNormalizer(method=method)
    return normalizer.normalize(value, signal_name)
