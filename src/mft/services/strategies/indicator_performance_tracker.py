"""
Indicator Performance Tracker by Asset Class.

This module tracks how well different technical indicators perform across
different asset classes (crypto vs stocks). It addresses the key insight that
while both markets use the same indicators, their effectiveness varies:

Crypto Markets:
- RSI overbought/oversold signals less reliable (extreme sentiment)
- MACD more prone to false signals (high volatility)
- Bollinger Band breakouts more frequent (extreme moves)
- Volume indicators less reliable (fragmented liquidity)

Stock Markets:
- RSI mean reversion works better (fundamentals anchor price)
- MACD crossovers more reliable (trend persistence)
- Support/resistance more respected (institutional trading)
- Volume analysis more reliable (centralized exchanges)

The tracker measures:
1. Signal accuracy (% of profitable signals)
2. Signal reliability (consistency over time)
3. False positive rate
4. Average return per signal
5. Win rate by market regime

This data feeds back into the Asset Class Adapter to continuously improve
parameter tuning based on real performance data.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

from mft.services.strategies.asset_class_adapter import AssetClass


@dataclass
class SignalOutcome:
    """Record of a trading signal and its outcome."""
    timestamp: datetime
    indicator: str  # "MACD", "RSI", "BB", etc.
    asset_class: AssetClass
    symbol: str
    direction: str  # "UP" or "DOWN"
    entry_price: float
    exit_price: Optional[float] = None
    exit_timestamp: Optional[datetime] = None
    profit_loss_pct: Optional[float] = None
    was_profitable: Optional[bool] = None
    market_regime: Optional[str] = None  # "TRENDING", "RANGING"


@dataclass
class IndicatorPerformanceMetrics:
    """Performance metrics for an indicator."""
    indicator_name: str
    asset_class: AssetClass
    total_signals: int = 0
    profitable_signals: int = 0
    losing_signals: int = 0
    pending_signals: int = 0

    # Win rate
    win_rate: float = 0.0  # profitable / total_closed

    # Return metrics
    avg_return_pct: float = 0.0
    avg_winning_return_pct: float = 0.0
    avg_losing_return_pct: float = 0.0
    sharpe_ratio: Optional[float] = None

    # Reliability metrics
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0

    # False signal detection
    false_positive_rate: float = 0.0  # Signals that reversed immediately

    # Regime-specific performance
    trending_win_rate: float = 0.0
    ranging_win_rate: float = 0.0

    # Last updated
    last_update: datetime = field(default_factory=datetime.now)


class IndicatorPerformanceTracker:
    """
    Track and analyze indicator performance by asset class.

    This tracker maintains a rolling history of signal outcomes and computes
    performance metrics that inform strategy adaptation.
    """

    def __init__(self, lookback_days: int = 90):
        """
        Initialize performance tracker.

        Args:
            lookback_days: How many days of history to maintain
        """
        self.lookback_days = lookback_days
        self.signal_history: List[SignalOutcome] = []
        self.metrics_cache: Dict[tuple, IndicatorPerformanceMetrics] = {}

    def record_signal(
        self,
        indicator: str,
        asset_class: AssetClass,
        symbol: str,
        direction: str,
        entry_price: float,
        timestamp: Optional[datetime] = None,
        market_regime: Optional[str] = None
    ) -> None:
        """
        Record a new trading signal.

        Args:
            indicator: Indicator that generated signal
            asset_class: Asset class being traded
            symbol: Symbol
            direction: Signal direction
            entry_price: Entry price
            timestamp: Signal timestamp
            market_regime: Market regime at signal time
        """
        outcome = SignalOutcome(
            timestamp=timestamp or datetime.now(),
            indicator=indicator,
            asset_class=asset_class,
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            market_regime=market_regime
        )

        self.signal_history.append(outcome)
        self._prune_old_signals()

    def record_signal_exit(
        self,
        indicator: str,
        symbol: str,
        exit_price: float,
        exit_timestamp: Optional[datetime] = None
    ) -> None:
        """
        Record the exit/outcome of a signal.

        Args:
            indicator: Indicator that generated signal
            symbol: Symbol
            exit_price: Exit price
            exit_timestamp: Exit timestamp
        """
        exit_time = exit_timestamp or datetime.now()

        # Find most recent pending signal for this indicator+symbol
        for outcome in reversed(self.signal_history):
            if (outcome.indicator == indicator and
                outcome.symbol == symbol and
                outcome.exit_price is None):

                # Calculate profit/loss
                if outcome.direction == "UP":
                    pnl_pct = ((exit_price - outcome.entry_price) / outcome.entry_price) * 100
                else:  # DOWN
                    pnl_pct = ((outcome.entry_price - exit_price) / outcome.entry_price) * 100

                outcome.exit_price = exit_price
                outcome.exit_timestamp = exit_time
                outcome.profit_loss_pct = pnl_pct
                outcome.was_profitable = pnl_pct > 0

                # Invalidate metrics cache
                self.metrics_cache.clear()
                break

    def get_performance_metrics(
        self,
        indicator: str,
        asset_class: AssetClass
    ) -> IndicatorPerformanceMetrics:
        """
        Get performance metrics for an indicator on an asset class.

        Args:
            indicator: Indicator name
            asset_class: Asset class

        Returns:
            Performance metrics
        """
        cache_key = (indicator, asset_class)

        # Check cache
        if cache_key in self.metrics_cache:
            cached = self.metrics_cache[cache_key]
            # Cache valid for 1 hour
            if (datetime.now() - cached.last_update) < timedelta(hours=1):
                return cached

        # Compute metrics
        metrics = self._compute_metrics(indicator, asset_class)
        self.metrics_cache[cache_key] = metrics
        return metrics

    def _compute_metrics(
        self,
        indicator: str,
        asset_class: AssetClass
    ) -> IndicatorPerformanceMetrics:
        """Compute performance metrics from signal history."""
        # Filter relevant signals
        signals = [
            s for s in self.signal_history
            if s.indicator == indicator and s.asset_class == asset_class
        ]

        metrics = IndicatorPerformanceMetrics(
            indicator_name=indicator,
            asset_class=asset_class
        )

        if not signals:
            return metrics

        metrics.total_signals = len(signals)

        # Separate completed vs pending
        completed = [s for s in signals if s.exit_price is not None]
        pending = [s for s in signals if s.exit_price is None]

        metrics.pending_signals = len(pending)

        if not completed:
            return metrics

        # Win/loss counts
        metrics.profitable_signals = sum(1 for s in completed if s.was_profitable)
        metrics.losing_signals = len(completed) - metrics.profitable_signals

        # Win rate
        metrics.win_rate = (metrics.profitable_signals / len(completed)) * 100

        # Return metrics
        returns = [s.profit_loss_pct for s in completed if s.profit_loss_pct is not None]
        if returns:
            metrics.avg_return_pct = statistics.mean(returns)

            winning_returns = [r for r in returns if r > 0]
            if winning_returns:
                metrics.avg_winning_return_pct = statistics.mean(winning_returns)

            losing_returns = [r for r in returns if r <= 0]
            if losing_returns:
                metrics.avg_losing_return_pct = statistics.mean(losing_returns)

            # Sharpe ratio (simplified)
            if len(returns) > 1:
                std_return = statistics.stdev(returns)
                if std_return > 0:
                    metrics.sharpe_ratio = (metrics.avg_return_pct / std_return)

        # Consecutive wins/losses
        current_streak = 0
        current_type = None

        for s in completed:
            if s.was_profitable:
                if current_type == "win":
                    current_streak += 1
                else:
                    current_type = "win"
                    current_streak = 1

                metrics.max_consecutive_wins = max(
                    metrics.max_consecutive_wins,
                    current_streak
                )
            else:
                if current_type == "loss":
                    current_streak += 1
                else:
                    current_type = "loss"
                    current_streak = 1

                metrics.max_consecutive_losses = max(
                    metrics.max_consecutive_losses,
                    current_streak
                )

        # Set current streak
        if current_type == "win":
            metrics.consecutive_wins = current_streak
        elif current_type == "loss":
            metrics.consecutive_losses = current_streak

        # False positive rate (signals that reversed within 1 hour)
        false_positives = 0
        for s in completed:
            if s.exit_timestamp and s.timestamp:
                time_diff = (s.exit_timestamp - s.timestamp).total_seconds() / 3600
                if time_diff < 1.0 and not s.was_profitable:
                    false_positives += 1

        if completed:
            metrics.false_positive_rate = (false_positives / len(completed)) * 100

        # Regime-specific performance
        trending_signals = [s for s in completed if s.market_regime == "TRENDING"]
        if trending_signals:
            trending_wins = sum(1 for s in trending_signals if s.was_profitable)
            metrics.trending_win_rate = (trending_wins / len(trending_signals)) * 100

        ranging_signals = [s for s in completed if s.market_regime == "RANGING"]
        if ranging_signals:
            ranging_wins = sum(1 for s in ranging_signals if s.was_profitable)
            metrics.ranging_win_rate = (ranging_wins / len(ranging_signals)) * 100

        metrics.last_update = datetime.now()
        return metrics

    def get_best_indicators(
        self,
        asset_class: AssetClass,
        top_n: int = 3
    ) -> List[tuple]:
        """
        Get best performing indicators for an asset class.

        Args:
            asset_class: Asset class
            top_n: Number of top indicators to return

        Returns:
            List of (indicator_name, win_rate) tuples
        """
        indicators = set(s.indicator for s in self.signal_history)

        performances = []
        for indicator in indicators:
            metrics = self.get_performance_metrics(indicator, asset_class)
            if metrics.total_signals >= 10:  # Minimum sample size
                performances.append((indicator, metrics.win_rate))

        # Sort by win rate descending
        performances.sort(key=lambda x: x[1], reverse=True)
        return performances[:top_n]

    def get_indicator_effectiveness_score(
        self,
        indicator: str,
        asset_class: AssetClass
    ) -> float:
        """
        Get overall effectiveness score for an indicator (0-100).

        Combines win rate, average return, and reliability.

        Args:
            indicator: Indicator name
            asset_class: Asset class

        Returns:
            Effectiveness score (0-100)
        """
        metrics = self.get_performance_metrics(indicator, asset_class)

        if metrics.total_signals < 5:
            return 50.0  # Neutral score for insufficient data

        # Component scores
        win_rate_score = metrics.win_rate  # Already 0-100

        # Return score (normalize to 0-100)
        # Assume -10% to +10% range maps to 0-100
        return_score = min(100, max(0, (metrics.avg_return_pct + 10) * 5))

        # Reliability score based on Sharpe ratio
        reliability_score = 50.0  # Default
        if metrics.sharpe_ratio is not None:
            # Sharpe > 2 = excellent (100), < 0 = poor (0)
            reliability_score = min(100, max(0, metrics.sharpe_ratio * 50))

        # False positive penalty
        fp_penalty = metrics.false_positive_rate  # 0-100

        # Weighted combination
        effectiveness = (
            win_rate_score * 0.4 +
            return_score * 0.3 +
            reliability_score * 0.2 +
            (100 - fp_penalty) * 0.1
        )

        return effectiveness

    def should_use_indicator(
        self,
        indicator: str,
        asset_class: AssetClass,
        min_effectiveness: float = 50.0
    ) -> bool:
        """
        Determine if an indicator should be used for an asset class.

        Args:
            indicator: Indicator name
            asset_class: Asset class
            min_effectiveness: Minimum effectiveness threshold

        Returns:
            True if indicator should be used
        """
        effectiveness = self.get_indicator_effectiveness_score(indicator, asset_class)
        return effectiveness >= min_effectiveness

    def get_recommended_confidence_adjustment(
        self,
        indicator: str,
        asset_class: AssetClass
    ) -> float:
        """
        Get recommended confidence adjustment multiplier.

        Args:
            indicator: Indicator name
            asset_class: Asset class

        Returns:
            Confidence multiplier (e.g., 1.2 = 20% boost, 0.8 = 20% penalty)
        """
        metrics = self.get_performance_metrics(indicator, asset_class)

        if metrics.total_signals < 10:
            return 1.0  # No adjustment for insufficient data

        # Adjust based on win rate relative to 50% baseline
        win_rate_factor = metrics.win_rate / 50.0

        # Adjust based on consecutive performance
        if metrics.consecutive_wins >= 3:
            win_rate_factor *= 1.1  # Hot streak bonus
        elif metrics.consecutive_losses >= 3:
            win_rate_factor *= 0.9  # Cold streak penalty

        # Cap adjustments
        return min(1.5, max(0.5, win_rate_factor))

    def _prune_old_signals(self) -> None:
        """Remove signals older than lookback period."""
        cutoff_date = datetime.now() - timedelta(days=self.lookback_days)
        self.signal_history = [
            s for s in self.signal_history
            if s.timestamp >= cutoff_date
        ]

    def export_metrics_summary(self) -> Dict[str, any]:
        """
        Export comprehensive metrics summary.

        Returns:
            Dict with all metrics by indicator and asset class
        """
        indicators = set(s.indicator for s in self.signal_history)
        asset_classes = set(s.asset_class for s in self.signal_history)

        summary = {}

        for asset_class in asset_classes:
            summary[asset_class.value] = {}

            for indicator in indicators:
                metrics = self.get_performance_metrics(indicator, asset_class)
                effectiveness = self.get_indicator_effectiveness_score(indicator, asset_class)

                summary[asset_class.value][indicator] = {
                    "total_signals": metrics.total_signals,
                    "win_rate": f"{metrics.win_rate:.1f}%",
                    "avg_return": f"{metrics.avg_return_pct:+.2f}%",
                    "sharpe_ratio": f"{metrics.sharpe_ratio:.2f}" if metrics.sharpe_ratio else "N/A",
                    "effectiveness_score": f"{effectiveness:.1f}/100",
                    "max_win_streak": metrics.max_consecutive_wins,
                    "max_loss_streak": metrics.max_consecutive_losses,
                    "false_positive_rate": f"{metrics.false_positive_rate:.1f}%",
                    "trending_win_rate": f"{metrics.trending_win_rate:.1f}%",
                    "ranging_win_rate": f"{metrics.ranging_win_rate:.1f}%"
                }

        return summary
