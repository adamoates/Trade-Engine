"""
Moving Average Crossover Alpha Model.

Classic technical strategy: generates buy signal when fast MA crosses above
slow MA, and sell signal when fast MA crosses below slow MA.

Example:
    Fast MA = 10-period SMA
    Slow MA = 30-period SMA

    Signal: LONG when SMA(10) > SMA(30) and previously SMA(10) <= SMA(30)
    Signal: SHORT when SMA(10) < SMA(30) and previously SMA(10) >= SMA(30)
"""

from datetime import datetime
from typing import List, Dict, Optional
from loguru import logger

from mft.services.data.types import OHLCV
from mft.services.strategies.types import (
    AlphaModel,
    Insight,
    InsightDirection,
    InsightType
)


class MovingAverageCrossoverAlpha(AlphaModel):
    """
    Generate insights based on moving average crossovers.

    This is a classic technical analysis strategy that generates
    signals when a fast-moving average crosses a slow-moving average.
    """

    def __init__(
        self,
        fast_period: int = 10,
        slow_period: int = 30,
        confidence: float = 0.7,
        insight_duration_seconds: int = 86400  # 24 hours default
    ):
        """
        Initialize MA Crossover Alpha Model.

        Args:
            fast_period: Period for fast moving average
            slow_period: Period for slow moving average
            confidence: Base confidence level for insights (0.0 to 1.0)
            insight_duration_seconds: How long insights remain valid
        """
        if fast_period >= slow_period:
            raise ValueError(
                f"Fast period ({fast_period}) must be less than "
                f"slow period ({slow_period})"
            )

        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0 and 1, got {confidence}")

        self.fast_period = fast_period
        self.slow_period = slow_period
        self.base_confidence = confidence
        self.insight_duration_seconds = insight_duration_seconds

    @property
    def name(self) -> str:
        return f"MA_Crossover_{self.fast_period}_{self.slow_period}"

    def _calculate_sma(self, prices: List[float], period: int) -> Optional[float]:
        """
        Calculate Simple Moving Average.

        Args:
            prices: List of prices (most recent last)
            period: Number of periods for SMA

        Returns:
            SMA value or None if insufficient data
        """
        if len(prices) < period:
            return None

        return sum(prices[-period:]) / period

    def _detect_crossover(
        self,
        fast_ma_current: float,
        slow_ma_current: float,
        fast_ma_prev: Optional[float],
        slow_ma_prev: Optional[float]
    ) -> Optional[InsightDirection]:
        """
        Detect if a crossover occurred.

        Args:
            fast_ma_current: Current fast MA value
            slow_ma_current: Current slow MA value
            fast_ma_prev: Previous fast MA value
            slow_ma_prev: Previous slow MA value

        Returns:
            InsightDirection.UP for bullish cross,
            InsightDirection.DOWN for bearish cross,
            None for no crossover
        """
        if fast_ma_prev is None or slow_ma_prev is None:
            return None

        # Bullish crossover: fast crosses above slow
        if fast_ma_current > slow_ma_current and fast_ma_prev <= slow_ma_prev:
            return InsightDirection.UP

        # Bearish crossover: fast crosses below slow
        if fast_ma_current < slow_ma_current and fast_ma_prev >= slow_ma_prev:
            return InsightDirection.DOWN

        return None

    def generate_insights(
        self,
        data: Dict[str, List[OHLCV]],
        current_time: datetime
    ) -> List[Insight]:
        """
        Generate MA crossover insights for each symbol.

        Args:
            data: Dictionary mapping symbol -> OHLCV candles (sorted by time)
            current_time: Current simulation or real-world time

        Returns:
            List of Insights (predictions)
        """
        insights = []

        for symbol, candles in data.items():
            if len(candles) < self.slow_period + 1:
                logger.debug(
                    f"Insufficient data for {symbol}: need {self.slow_period + 1} bars, "
                    f"have {len(candles)}"
                )
                continue

            # Extract closing prices
            close_prices = [candle.close for candle in candles]

            # Calculate current MAs
            fast_ma_current = self._calculate_sma(close_prices, self.fast_period)
            slow_ma_current = self._calculate_sma(close_prices, self.slow_period)

            # Calculate previous MAs (using data up to previous bar)
            fast_ma_prev = self._calculate_sma(close_prices[:-1], self.fast_period)
            slow_ma_prev = self._calculate_sma(close_prices[:-1], self.slow_period)

            if fast_ma_current is None or slow_ma_current is None:
                continue

            # Detect crossover
            direction = self._detect_crossover(
                fast_ma_current,
                slow_ma_current,
                fast_ma_prev,
                slow_ma_prev
            )

            if direction is not None:
                # Calculate magnitude as % difference between MAs
                magnitude = abs(fast_ma_current - slow_ma_current) / slow_ma_current

                insight = Insight(
                    symbol=symbol,
                    direction=direction,
                    magnitude=magnitude,
                    confidence=self.base_confidence,
                    period_seconds=self.insight_duration_seconds,
                    insight_type=InsightType.PRICE,
                    source=self.name,
                    generated_time=current_time
                )

                insights.append(insight)

                logger.info(
                    f"{self.name} generated {direction.value} signal for {symbol}: "
                    f"fast_ma={fast_ma_current:.2f}, slow_ma={slow_ma_current:.2f}, "
                    f"magnitude={magnitude:.4f}"
                )

        return insights
