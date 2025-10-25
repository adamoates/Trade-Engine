"""
RSI Divergence Alpha Model.

Detects bullish and bearish divergences between price and RSI momentum.
This is considered one of the most powerful reversal signals in technical analysis.

Bullish Divergence: Price makes lower lows, but RSI makes higher lows
                     (momentum weakening in downtrend -> potential reversal up)

Bearish Divergence: Price makes higher highs, but RSI makes lower highs
                     (momentum weakening in uptrend -> potential reversal down)

Based on the 2025 Crypto Profit Matrix research:
- RSI divergence highlighted as "most powerful signal" (Section 3.1)
- Traditional thresholds: oversold < 30, overbought > 70
- Requires confirmation from extremes (overbought/oversold zones)
"""

from datetime import datetime
from typing import List, Dict, Optional
from loguru import logger

from trade_engine.services.data.types import OHLCV
from trade_engine.services.strategies.types import (
    AlphaModel,
    Insight,
    InsightDirection,
    InsightType
)


class RSIDivergenceAlpha(AlphaModel):
    """
    Generate insights based on RSI divergences.

    This alpha model identifies potential trend reversals by detecting
    divergences between price action and the RSI momentum indicator.
    """

    def __init__(
        self,
        rsi_period: int = 14,
        overbought_threshold: float = 70,
        oversold_threshold: float = 30,
        lookback_periods: int = 5,
        confidence: float = 0.8,
        insight_duration_seconds: int = 86400  # 24 hours default
    ):
        """
        Initialize RSI Divergence Alpha Model.

        Args:
            rsi_period: Period for RSI calculation (default: 14)
            overbought_threshold: RSI level considered overbought (default: 70)
            oversold_threshold: RSI level considered oversold (default: 30)
            lookback_periods: How many periods to look back for divergence (default: 5)
            confidence: Base confidence level for insights (0.0 to 1.0)
            insight_duration_seconds: How long insights remain valid
        """
        if rsi_period < 2:
            raise ValueError(f"RSI period must be at least 2, got {rsi_period}")

        if not 0 <= oversold_threshold < overbought_threshold <= 100:
            raise ValueError(
                f"Overbought threshold ({overbought_threshold}) must be greater than "
                f"oversold threshold ({oversold_threshold}), and both must be between 0 and 100"
            )

        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0 and 1, got {confidence}")

        self.rsi_period = rsi_period
        self.overbought_threshold = overbought_threshold
        self.oversold_threshold = oversold_threshold
        self.lookback_periods = lookback_periods
        self.base_confidence = confidence
        self.insight_duration_seconds = insight_duration_seconds

    @property
    def name(self) -> str:
        return f"RSI_Divergence_{self.rsi_period}_{self.lookback_periods}"

    def _calculate_rsi(self, prices: List[float], period: int) -> Optional[float]:
        """
        Calculate Relative Strength Index.

        RSI = 100 - (100 / (1 + RS))
        where RS = Average Gain / Average Loss over the period

        Args:
            prices: List of closing prices (most recent last)
            period: Number of periods for RSI calculation

        Returns:
            RSI value (0-100) or None if insufficient data
        """
        if len(prices) < period + 1:
            return None

        # Calculate price changes
        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]

        # Separate gains and losses
        gains = [max(delta, 0) for delta in deltas]
        losses = [abs(min(delta, 0)) for delta in deltas]

        # Calculate initial average gain and loss (simple average)
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        # Avoid division by zero
        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0

        # Calculate RS and RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _detect_divergence(
        self,
        prices: List[float],
        rsi_values: List[float],
        current_rsi: float
    ) -> Optional[InsightDirection]:
        """
        Detect bullish or bearish divergence.

        Args:
            prices: Recent price values
            rsi_values: Corresponding RSI values
            current_rsi: Current RSI value

        Returns:
            InsightDirection.UP for bullish divergence,
            InsightDirection.DOWN for bearish divergence,
            None for no divergence
        """
        if len(prices) < 2 or len(rsi_values) < 2:
            return None

        # Find trend in prices (higher highs/lower lows)
        price_trend = prices[-1] - prices[0]

        # Find trend in RSI (higher highs/lower lows)
        rsi_trend = rsi_values[-1] - rsi_values[0]

        # Bullish Divergence: Price making lower lows, RSI making higher lows
        # Only trigger in oversold zone
        if price_trend < 0 and rsi_trend > 0 and current_rsi <= self.oversold_threshold:
            # Verify it's a real divergence by checking intermediate points
            price_making_lower_lows = all(
                prices[i] <= prices[i - 1] for i in range(1, len(prices))
            ) or prices[-1] < min(prices[:-1])

            rsi_making_higher_lows = rsi_values[-1] > min(rsi_values[:-1])

            if price_making_lower_lows or rsi_making_higher_lows:
                return InsightDirection.UP

        # Bearish Divergence: Price making higher highs, RSI making lower highs
        # Only trigger in overbought zone
        if price_trend > 0 and rsi_trend < 0 and current_rsi >= self.overbought_threshold:
            # Verify it's a real divergence by checking intermediate points
            price_making_higher_highs = all(
                prices[i] >= prices[i - 1] for i in range(1, len(prices))
            ) or prices[-1] > max(prices[:-1])

            rsi_making_lower_highs = rsi_values[-1] < max(rsi_values[:-1])

            if price_making_higher_highs or rsi_making_lower_highs:
                return InsightDirection.DOWN

        return None

    def generate_insights(
        self,
        data: Dict[str, List[OHLCV]],
        current_time: datetime
    ) -> List[Insight]:
        """
        Generate RSI divergence insights for each symbol.

        Args:
            data: Dictionary mapping symbol -> OHLCV candles (sorted by time)
            current_time: Current simulation or real-world time

        Returns:
            List of Insights (predictions)
        """
        insights = []

        for symbol, candles in data.items():
            # Need enough data for RSI + lookback
            required_bars = self.rsi_period + self.lookback_periods + 1
            if len(candles) < required_bars:
                logger.debug(
                    f"Insufficient data for {symbol}: need {required_bars} bars, "
                    f"have {len(candles)}"
                )
                continue

            # Extract closing prices
            close_prices = [candle.close for candle in candles]

            # Calculate RSI values for lookback period
            rsi_values = []
            prices_for_divergence = []

            for i in range(len(close_prices) - self.lookback_periods, len(close_prices)):
                rsi = self._calculate_rsi(close_prices[:i + 1], self.rsi_period)
                if rsi is None:
                    continue
                rsi_values.append(rsi)
                prices_for_divergence.append(close_prices[i])

            if len(rsi_values) < self.lookback_periods:
                continue

            current_rsi = rsi_values[-1]

            # Detect divergence
            direction = self._detect_divergence(
                prices=prices_for_divergence,
                rsi_values=rsi_values,
                current_rsi=current_rsi
            )

            if direction is not None:
                # Calculate magnitude based on how far from neutral (50) RSI is
                # More extreme RSI = stronger signal
                magnitude = abs(current_rsi - 50) / 50.0

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
                    f"RSI={current_rsi:.2f}, magnitude={magnitude:.4f}"
                )

        return insights
