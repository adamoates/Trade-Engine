"""
Market Regime Detection using ADX (Average Directional Index).

The ADX indicator measures trend strength, helping distinguish between:
- TRENDING markets (ADX > threshold): Use trend-following strategies (MA Crossover)
- RANGING markets (ADX < threshold): Use mean-reversion strategies (RSI Divergence)

Based on the 2025 Crypto Profit Matrix research:
- "The truly adept trader of 2025 is a 'market chameleon,' capable of accurately
   identifying the current market regime and deploying the appropriate strategic arsenal."
- "Tools like the Average Directional Index (ADX) become indispensable in making
   this critical determination."

Standard ADX interpretation:
- ADX < 20: Weak or absent trend (ranging/sideways market)
- ADX 20-25: Emerging trend
- ADX 25-50: Strong trend
- ADX 50+: Very strong trend
- ADX 75+: Extremely strong trend (rare)
"""

from enum import Enum
from typing import List, Dict, Optional
from loguru import logger

from trade_engine.services.data.types import OHLCV


class MarketRegime(str, Enum):
    """Market regime classification."""
    TRENDING = "trending"
    RANGING = "ranging"
    UNKNOWN = "unknown"


class MarketRegimeDetector:
    """
    Detect market regime using ADX indicator.

    The ADX (Average Directional Index) measures the strength of a trend,
    regardless of direction. It's calculated from the +DI and -DI (Directional
    Indicators) which measure upward and downward price movement.
    """

    def __init__(
        self,
        adx_period: int = 14,
        trending_threshold: float = 25,
        strong_trend_threshold: float = 50
    ):
        """
        Initialize Market Regime Detector.

        Args:
            adx_period: Period for ADX calculation (default: 14)
            trending_threshold: ADX value above which market is considered trending (default: 25)
            strong_trend_threshold: ADX value indicating very strong trend (default: 50)
        """
        if adx_period < 2:
            raise ValueError(f"ADX period must be at least 2, got {adx_period}")

        if trending_threshold >= strong_trend_threshold:
            raise ValueError(
                f"Trending threshold ({trending_threshold}) must be less than "
                f"strong trend threshold ({strong_trend_threshold})"
            )

        self.adx_period = adx_period
        self.trending_threshold = trending_threshold
        self.strong_trend_threshold = strong_trend_threshold

    def _calculate_true_range(self, candles: List[OHLCV]) -> List[float]:
        """
        Calculate True Range for each candle.

        TR = max(high - low, |high - prev_close|, |low - prev_close|)

        Args:
            candles: List of OHLCV candles

        Returns:
            List of True Range values
        """
        tr_values = []

        for i in range(len(candles)):
            high = candles[i].high
            low = candles[i].low

            if i == 0:
                # First candle: TR = high - low
                tr = high - low
            else:
                prev_close = candles[i - 1].close
                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close)
                )

            tr_values.append(tr)

        return tr_values

    def _calculate_directional_movement(self, candles: List[OHLCV]) -> tuple:
        """
        Calculate +DM (Positive Directional Movement) and -DM (Negative Directional Movement).

        +DM = max(current_high - previous_high, 0) if it's greater than -DM, else 0
        -DM = max(previous_low - current_low, 0) if it's greater than +DM, else 0

        Args:
            candles: List of OHLCV candles

        Returns:
            Tuple of (+DM list, -DM list)
        """
        plus_dm = []
        minus_dm = []

        for i in range(len(candles)):
            if i == 0:
                plus_dm.append(0.0)
                minus_dm.append(0.0)
            else:
                high_diff = candles[i].high - candles[i - 1].high
                low_diff = candles[i - 1].low - candles[i].low

                if high_diff > low_diff and high_diff > 0:
                    plus_dm.append(high_diff)
                    minus_dm.append(0.0)
                elif low_diff > high_diff and low_diff > 0:
                    plus_dm.append(0.0)
                    minus_dm.append(low_diff)
                else:
                    plus_dm.append(0.0)
                    minus_dm.append(0.0)

        return plus_dm, minus_dm

    def _smooth_values(self, values: List[float], period: int) -> List[float]:
        """
        Apply Wilder's smoothing to a list of values.

        Wilder's smoothing: smoothed[i] = (smoothed[i-1] * (period - 1) + current) / period

        Args:
            values: List of values to smooth
            period: Smoothing period

        Returns:
            List of smoothed values
        """
        if len(values) < period:
            return []

        smoothed = []

        # First smoothed value is the average of the first 'period' values
        first_smooth = sum(values[:period]) / period
        smoothed.append(first_smooth)

        # Apply Wilder's smoothing to subsequent values
        for i in range(period, len(values)):
            new_smooth = (smoothed[-1] * (period - 1) + values[i]) / period
            smoothed.append(new_smooth)

        return smoothed

    def _calculate_adx(self, candles: List[OHLCV], period: int) -> Optional[float]:
        """
        Calculate ADX (Average Directional Index).

        Process:
        1. Calculate True Range (TR)
        2. Calculate +DM and -DM
        3. Smooth TR, +DM, and -DM using Wilder's smoothing
        4. Calculate +DI = (smoothed +DM / smoothed TR) * 100
        5. Calculate -DI = (smoothed -DM / smoothed TR) * 100
        6. Calculate DX = |+DI - -DI| / (+DI + -DI) * 100
        7. Calculate ADX = smoothed DX

        Args:
            candles: List of OHLCV candles
            period: ADX period

        Returns:
            ADX value or None if insufficient data
        """
        # Need at least 2 * period bars for reliable ADX
        if len(candles) < period * 2:
            return None

        # Step 1: Calculate True Range
        tr_values = self._calculate_true_range(candles)

        # Step 2: Calculate Directional Movements
        plus_dm, minus_dm = self._calculate_directional_movement(candles)

        # Step 3: Smooth values using Wilder's smoothing
        smoothed_tr = self._smooth_values(tr_values, period)
        smoothed_plus_dm = self._smooth_values(plus_dm, period)
        smoothed_minus_dm = self._smooth_values(minus_dm, period)

        if not smoothed_tr or not smoothed_plus_dm or not smoothed_minus_dm:
            return None

        # Step 4 & 5: Calculate +DI and -DI
        dx_values = []
        for i in range(len(smoothed_tr)):
            if smoothed_tr[i] == 0:
                continue

            plus_di = (smoothed_plus_dm[i] / smoothed_tr[i]) * 100
            minus_di = (smoothed_minus_dm[i] / smoothed_tr[i]) * 100

            # Step 6: Calculate DX
            di_sum = plus_di + minus_di
            if di_sum == 0:
                continue

            dx = abs(plus_di - minus_di) / di_sum * 100
            dx_values.append(dx)

        if len(dx_values) < period:
            return None

        # Step 7: Calculate ADX (smoothed DX)
        smoothed_dx = self._smooth_values(dx_values, period)

        if not smoothed_dx:
            return None

        # Return the most recent ADX value
        return smoothed_dx[-1]

    def _classify_regime(self, adx: Optional[float]) -> MarketRegime:
        """
        Classify market regime based on ADX value.

        Args:
            adx: ADX value

        Returns:
            Market regime classification
        """
        if adx is None:
            return MarketRegime.UNKNOWN

        if adx > self.trending_threshold:
            return MarketRegime.TRENDING
        else:
            return MarketRegime.RANGING

    def detect_regime(self, data: Dict[str, List[OHLCV]], symbol: str) -> MarketRegime:
        """
        Detect market regime for a specific symbol.

        Args:
            data: Dictionary mapping symbol -> OHLCV candles
            symbol: Symbol to analyze

        Returns:
            Market regime classification
        """
        if symbol not in data:
            logger.debug(f"Symbol {symbol} not found in data")
            return MarketRegime.UNKNOWN

        candles = data[symbol]
        adx = self._calculate_adx(candles, self.adx_period)

        if adx is None:
            logger.debug(
                f"Insufficient data for {symbol}: need {self.adx_period * 2} bars, "
                f"have {len(candles)}"
            )
            return MarketRegime.UNKNOWN

        regime = self._classify_regime(adx)

        logger.info(
            f"Market regime for {symbol}: {regime.value} (ADX={adx:.2f})"
        )

        return regime

    def detect_regimes_for_all(self, data: Dict[str, List[OHLCV]]) -> Dict[str, MarketRegime]:
        """
        Detect market regimes for all symbols.

        Args:
            data: Dictionary mapping symbol -> OHLCV candles

        Returns:
            Dictionary mapping symbol -> MarketRegime
        """
        regimes = {}

        for symbol in data.keys():
            regime = self.detect_regime(data, symbol)
            regimes[symbol] = regime

        return regimes

    def get_adx(self, data: Dict[str, List[OHLCV]], symbol: str) -> Optional[float]:
        """
        Get raw ADX value for a symbol.

        Args:
            data: Dictionary mapping symbol -> OHLCV candles
            symbol: Symbol to analyze

        Returns:
            ADX value or None if insufficient data
        """
        if symbol not in data:
            return None

        candles = data[symbol]
        return self._calculate_adx(candles, self.adx_period)
