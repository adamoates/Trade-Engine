"""
MACD (Moving Average Convergence Divergence) Alpha Model.

The MACD is a trend-following momentum indicator that shows the relationship
between two exponential moving averages (EMAs). It consists of:
- MACD Line: Fast EMA (12) - Slow EMA (26)
- Signal Line: 9-period EMA of the MACD Line
- Histogram: MACD Line - Signal Line

Signals:
- Bullish Crossover: MACD line crosses above signal line (buy)
- Bearish Crossover: MACD line crosses below signal line (sell)
- Histogram: Shows momentum strength and direction

Based on the 2025 Crypto Profit Matrix research:
- "The MACD is a versatile indicator... A bullish crossover (MACD line crosses
   above the signal line) is a buy signal, while a bearish crossover is a sell signal.
   The histogram provides a visual representation of momentum."
"""

from datetime import datetime
from typing import List, Dict, Optional
from loguru import logger

from app.data.types import OHLCV
from app.strategies.types import (
    AlphaModel,
    Insight,
    InsightDirection,
    InsightType
)


class MACDAlpha(AlphaModel):
    """
    Generate insights based on MACD crossovers.

    This is a classic momentum indicator that combines trend-following
    and momentum characteristics. It's particularly effective in trending
    markets and provides clear entry/exit signals.
    """

    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        confidence: float = 0.75,
        insight_duration_seconds: int = 86400  # 24 hours default
    ):
        """
        Initialize MACD Alpha Model.

        Args:
            fast_period: Period for fast EMA (default: 12)
            slow_period: Period for slow EMA (default: 26)
            signal_period: Period for signal line EMA (default: 9)
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
        self.signal_period = signal_period
        self.base_confidence = confidence
        self.insight_duration_seconds = insight_duration_seconds

    @property
    def name(self) -> str:
        return f"MACD_{self.fast_period}_{self.slow_period}_{self.signal_period}"

    def _calculate_ema(self, prices: List[float], period: int) -> Optional[List[float]]:
        """
        Calculate Exponential Moving Average.

        EMA gives more weight to recent prices using a smoothing factor:
        multiplier = 2 / (period + 1)
        EMA = (price - previous_EMA) * multiplier + previous_EMA

        Args:
            prices: List of closing prices (most recent last)
            period: Number of periods for EMA

        Returns:
            List of EMA values (same length as prices) or None if insufficient data
        """
        if len(prices) < period:
            return None

        ema_values = []
        multiplier = 2 / (period + 1)

        # First EMA is the simple average of the first 'period' values
        first_ema = sum(prices[:period]) / period
        ema_values.append(first_ema)

        # Calculate EMA for remaining prices
        for i in range(period, len(prices)):
            ema = (prices[i] - ema_values[-1]) * multiplier + ema_values[-1]
            ema_values.append(ema)

        # Pad with None values at the beginning to match prices length
        return [None] * (period - 1) + ema_values

    def _calculate_macd_line(self, prices: List[float]) -> Optional[List[float]]:
        """
        Calculate MACD line (Fast EMA - Slow EMA).

        Args:
            prices: List of closing prices

        Returns:
            MACD line values or None if insufficient data
        """
        fast_ema = self._calculate_ema(prices, self.fast_period)
        slow_ema = self._calculate_ema(prices, self.slow_period)

        if fast_ema is None or slow_ema is None:
            return None

        # Calculate MACD line where both EMAs are available
        macd_line = []
        for i in range(len(prices)):
            if fast_ema[i] is not None and slow_ema[i] is not None:
                macd_line.append(fast_ema[i] - slow_ema[i])
            else:
                macd_line.append(None)

        return macd_line

    def _calculate_signal_line(self, macd_line: List[float]) -> Optional[List[float]]:
        """
        Calculate signal line (EMA of MACD line).

        Args:
            macd_line: MACD line values

        Returns:
            Signal line values or None if insufficient data
        """
        # Filter out None values for EMA calculation
        valid_macd = [m for m in macd_line if m is not None]

        if len(valid_macd) < self.signal_period:
            return None

        signal_ema = self._calculate_ema(valid_macd, self.signal_period)

        if signal_ema is None:
            return None

        # Reconstruct signal line with None padding to match macd_line length
        signal_line = [None] * len(macd_line)
        valid_idx = 0

        for i in range(len(macd_line)):
            if macd_line[i] is not None:
                if valid_idx < len(signal_ema) and signal_ema[valid_idx] is not None:
                    signal_line[i] = signal_ema[valid_idx]
                valid_idx += 1

        return signal_line

    def _detect_crossover(
        self,
        macd_current: float,
        signal_current: float,
        macd_prev: Optional[float],
        signal_prev: Optional[float]
    ) -> Optional[InsightDirection]:
        """
        Detect if a MACD crossover occurred.

        Args:
            macd_current: Current MACD line value
            signal_current: Current signal line value
            macd_prev: Previous MACD line value
            signal_prev: Previous signal line value

        Returns:
            InsightDirection.UP for bullish cross,
            InsightDirection.DOWN for bearish cross,
            None for no crossover
        """
        if macd_prev is None or signal_prev is None:
            return None

        # Bullish crossover: MACD crosses above signal
        if macd_current > signal_current and macd_prev <= signal_prev:
            return InsightDirection.UP

        # Bearish crossover: MACD crosses below signal
        if macd_current < signal_current and macd_prev >= signal_prev:
            return InsightDirection.DOWN

        return None

    def generate_insights(
        self,
        data: Dict[str, List[OHLCV]],
        current_time: datetime
    ) -> List[Insight]:
        """
        Generate MACD crossover insights for each symbol.

        Args:
            data: Dictionary mapping symbol -> OHLCV candles (sorted by time)
            current_time: Current simulation or real-world time

        Returns:
            List of Insights (predictions)
        """
        insights = []

        for symbol, candles in data.items():
            # Need enough data for slow EMA + signal EMA
            required_bars = self.slow_period + self.signal_period
            if len(candles) < required_bars:
                logger.debug(
                    f"Insufficient data for {symbol}: need {required_bars} bars, "
                    f"have {len(candles)}"
                )
                continue

            # Extract closing prices
            close_prices = [candle.close for candle in candles]

            # Calculate MACD line
            macd_line = self._calculate_macd_line(close_prices)
            if macd_line is None:
                continue

            # Calculate signal line
            signal_line = self._calculate_signal_line(macd_line)
            if signal_line is None:
                continue

            # Get current and previous values
            macd_current = macd_line[-1]
            signal_current = signal_line[-1]
            macd_prev = macd_line[-2] if len(macd_line) > 1 else None
            signal_prev = signal_line[-2] if len(signal_line) > 1 else None

            if macd_current is None or signal_current is None:
                continue

            # Detect crossover
            direction = self._detect_crossover(
                macd_current,
                signal_current,
                macd_prev,
                signal_prev
            )

            if direction is not None:
                # Calculate histogram (MACD - Signal) as magnitude
                histogram = abs(macd_current - signal_current)

                # Normalize histogram relative to current price for magnitude
                current_price = close_prices[-1]
                magnitude = histogram / current_price if current_price > 0 else 0

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
                    f"MACD={macd_current:.4f}, Signal={signal_current:.4f}, "
                    f"Histogram={histogram:.4f}"
                )

        return insights
