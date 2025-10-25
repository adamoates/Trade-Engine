"""
Bollinger Bands Breakout Alpha Model.

Bollinger Bands are a volatility indicator consisting of:
- Middle Band: Simple Moving Average (typically 20 periods)
- Upper Band: Middle Band + (2 × Standard Deviation)
- Lower Band: Middle Band - (2 × Standard Deviation)

Signals:
- Bullish Breakout: Price closes above upper band (potential upward momentum)
- Bearish Breakout: Price closes below lower band (potential downward momentum)
- Band Squeeze: Bands contract (low volatility, often precedes breakouts)

Based on the 2025 Crypto Profit Matrix research:
- "Bollinger Bands can signal breakouts when price moves outside the bands"
- "The squeeze (when bands narrow) indicates low volatility and often precedes
   significant price movements"
"""

from datetime import datetime
from typing import List, Dict, Optional, Tuple
from loguru import logger
import math

from trade_engine.services.data.types import OHLCV
from trade_engine.services.strategies.types import (
    AlphaModel,
    Insight,
    InsightDirection,
    InsightType
)


class BollingerAlpha(AlphaModel):
    """
    Generate insights based on Bollinger Band breakouts.

    This model detects when price breaks out of the normal volatility range
    defined by the Bollinger Bands, signaling potential momentum in the
    breakout direction.
    """

    def __init__(
        self,
        period: int = 20,
        num_std_dev: float = 2.0,
        confidence: float = 0.7,
        insight_duration_seconds: int = 86400  # 24 hours default
    ):
        """
        Initialize Bollinger Band Alpha Model.

        Args:
            period: Number of periods for SMA and std dev (default: 20)
            num_std_dev: Number of standard deviations for bands (default: 2.0)
            confidence: Base confidence level for insights (0.0 to 1.0)
            insight_duration_seconds: How long insights remain valid
        """
        if period < 2:
            raise ValueError(f"Period must be at least 2, got {period}")

        if num_std_dev <= 0:
            raise ValueError(
                f"Standard deviation multiplier must be positive, got {num_std_dev}"
            )

        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0 and 1, got {confidence}")

        self.period = period
        self.num_std_dev = num_std_dev
        self.base_confidence = confidence
        self.insight_duration_seconds = insight_duration_seconds

    @property
    def name(self) -> str:
        return f"Bollinger_{self.period}_{self.num_std_dev}"

    def _calculate_sma(self, prices: List[float], period: int) -> Optional[float]:
        """
        Calculate Simple Moving Average.

        Args:
            prices: List of closing prices (most recent last)
            period: Number of periods for SMA

        Returns:
            SMA value or None if insufficient data
        """
        if len(prices) < period:
            return None

        return sum(prices[-period:]) / period

    def _calculate_std_dev(self, prices: List[float], period: int) -> Optional[float]:
        """
        Calculate standard deviation.

        Args:
            prices: List of closing prices (most recent last)
            period: Number of periods for std dev

        Returns:
            Standard deviation or None if insufficient data
        """
        if len(prices) < period:
            return None

        recent_prices = prices[-period:]
        mean = sum(recent_prices) / period

        # Calculate variance
        variance = sum((price - mean) ** 2 for price in recent_prices) / period

        # Standard deviation is square root of variance
        return math.sqrt(variance)

    def _calculate_bands(
        self,
        prices: List[float]
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Calculate Bollinger Bands (lower, middle, upper).

        Args:
            prices: List of closing prices

        Returns:
            Tuple of (lower_band, middle_band, upper_band) or (None, None, None)
        """
        middle_band = self._calculate_sma(prices, self.period)
        std_dev = self._calculate_std_dev(prices, self.period)

        if middle_band is None or std_dev is None:
            return None, None, None

        upper_band = middle_band + (self.num_std_dev * std_dev)
        lower_band = middle_band - (self.num_std_dev * std_dev)

        return lower_band, middle_band, upper_band

    def _detect_breakout(
        self,
        current_price: float,
        upper_band: float,
        lower_band: float
    ) -> Optional[InsightDirection]:
        """
        Detect if a breakout occurred.

        Args:
            current_price: Current closing price
            upper_band: Upper Bollinger Band value
            lower_band: Lower Bollinger Band value

        Returns:
            InsightDirection.UP for bullish breakout,
            InsightDirection.DOWN for bearish breakout,
            None for no breakout
        """
        # Bullish breakout: price above upper band
        if current_price > upper_band:
            return InsightDirection.UP

        # Bearish breakout: price below lower band
        if current_price < lower_band:
            return InsightDirection.DOWN

        return None

    def generate_insights(
        self,
        data: Dict[str, List[OHLCV]],
        current_time: datetime
    ) -> List[Insight]:
        """
        Generate Bollinger Band breakout insights for each symbol.

        Args:
            data: Dictionary mapping symbol -> OHLCV candles (sorted by time)
            current_time: Current simulation or real-world time

        Returns:
            List of Insights (predictions)
        """
        insights = []

        for symbol, candles in data.items():
            # Need enough data for the period
            if len(candles) < self.period:
                logger.debug(
                    f"Insufficient data for {symbol}: need {self.period} bars, "
                    f"have {len(candles)}"
                )
                continue

            # Extract closing prices
            close_prices = [candle.close for candle in candles]

            # Calculate Bollinger Bands
            lower_band, middle_band, upper_band = self._calculate_bands(close_prices)

            if lower_band is None or middle_band is None or upper_band is None:
                continue

            # Get current price
            current_price = close_prices[-1]

            # Detect breakout
            direction = self._detect_breakout(
                current_price,
                upper_band,
                lower_band
            )

            if direction is not None:
                # Calculate magnitude based on distance from band
                if direction == InsightDirection.UP:
                    # Distance above upper band, normalized by price
                    magnitude = (current_price - upper_band) / current_price
                else:
                    # Distance below lower band, normalized by price
                    magnitude = (lower_band - current_price) / current_price

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
                    f"Price={current_price:.4f}, Upper={upper_band:.4f}, "
                    f"Lower={lower_band:.4f}, Middle={middle_band:.4f}"
                )

        return insights
