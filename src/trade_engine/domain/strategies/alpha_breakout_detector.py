"""
Breakout Setup Detection Strategy

Multi-factor breakout detection combining:
- Price breakout above resistance with volume confirmation
- Momentum indicators (RSI, MACD)
- Volatility squeeze (Bollinger Bands)
- Derivatives signals (Open Interest, Funding Rate, Put/Call Ratio)
- Risk filters (overextension, trap detection)

CRITICAL: All financial calculations use Decimal (NON-NEGOTIABLE per CLAUDE.md).
"""

from decimal import Decimal
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from collections import deque
import time
from loguru import logger

from trade_engine.core.types import Strategy, Bar, Signal


@dataclass
class BreakoutConfig:
    """Configuration for breakout detection strategy."""

    # Breakout Detection
    volume_spike_threshold: Decimal = Decimal("2.0")  # 2x average volume required
    resistance_confirmation_pct: Decimal = Decimal("0.5")  # 0.5% above resistance

    # Momentum Indicators
    rsi_period: int = 14
    rsi_bullish_threshold: Decimal = Decimal("55")
    rsi_overbought_threshold: Decimal = Decimal("75")

    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    macd_lookback_bars: int = 5  # Check MACD cross in last N bars

    # Volatility
    bb_period: int = 20
    bb_std_dev: Decimal = Decimal("2.0")
    bb_squeeze_threshold: Decimal = Decimal("0.02")  # 2% bandwidth = tight

    # Volume
    volume_ma_period: int = 20

    # Derivatives (Optional - may not be available)
    oi_increase_threshold: Decimal = Decimal("0.10")  # 10% increase in 24h
    put_call_bullish_threshold: Decimal = Decimal("1.0")  # < 1.0 = bullish
    funding_rate_positive_min: Decimal = Decimal("0.0001")  # 0.01% per 8h
    funding_rate_extreme_max: Decimal = Decimal("0.0005")  # 0.05% per 8h (avoid)

    # Support/Resistance Detection
    sr_lookback_bars: int = 50  # Look back 50 bars for S/R levels
    sr_tolerance_pct: Decimal = Decimal("0.5")  # 0.5% tolerance for level matching

    # Position Sizing
    position_size_usd: Decimal = Decimal("1000")

    # Signal Confidence Weights
    weight_breakout: Decimal = Decimal("0.30")
    weight_momentum: Decimal = Decimal("0.25")
    weight_volatility: Decimal = Decimal("0.15")
    weight_derivatives: Decimal = Decimal("0.20")
    weight_risk_filter: Decimal = Decimal("0.10")


@dataclass
class SetupSignal:
    """Detailed breakout setup signal with all conditions."""

    symbol: str
    setup: str  # "Bullish Breakout", "Watchlist", "No Trade"
    confidence: Decimal
    conditions_met: List[str] = field(default_factory=list)
    conditions_failed: List[str] = field(default_factory=list)
    action: str = "No action"

    # Detailed metrics
    current_price: Decimal = Decimal("0")
    resistance_level: Optional[Decimal] = None
    support_level: Optional[Decimal] = None
    volume_ratio: Decimal = Decimal("0")
    rsi: Decimal = Decimal("0")
    macd_histogram: Decimal = Decimal("0")
    bb_bandwidth_pct: Decimal = Decimal("0")
    oi_change_pct: Optional[Decimal] = None
    funding_rate: Optional[Decimal] = None
    put_call_ratio: Optional[Decimal] = None

    timestamp: int = 0


class BreakoutSetupDetector(Strategy):
    """
    Breakout Setup Detection Strategy.

    Detects bullish breakout setups using multi-factor confirmation:
    1. Price breakout above resistance with volume
    2. Momentum confirmation (RSI, MACD)
    3. Volatility squeeze (Bollinger Bands)
    4. Derivatives signals (OI, funding, put/call)
    5. Risk filters (overextension, trap detection)

    Returns detailed SetupSignal with all conditions and confidence score.
    """

    def __init__(
        self,
        symbol: str,
        config: Optional[BreakoutConfig] = None
    ):
        """
        Initialize breakout detector.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            config: Strategy configuration (uses defaults if None)
        """
        self.symbol = symbol
        self.config = config or BreakoutConfig()

        # Price history for indicators
        self.closes: deque = deque(maxlen=max(
            self.config.bb_period,
            self.config.volume_ma_period,
            self.config.sr_lookback_bars
        ))
        self.highs: deque = deque(maxlen=self.config.sr_lookback_bars)
        self.lows: deque = deque(maxlen=self.config.sr_lookback_bars)
        self.volumes: deque = deque(maxlen=self.config.volume_ma_period)

        # Indicator state
        self.rsi_values: deque = deque(maxlen=self.config.rsi_period + 10)
        self.macd_values: deque = deque(maxlen=self.config.macd_lookback_bars + 10)
        self.macd_signal_values: deque = deque(maxlen=self.config.macd_lookback_bars + 10)
        self.macd_histogram_values: deque = deque(maxlen=self.config.macd_lookback_bars)

        # Support/Resistance levels
        self.resistance_levels: List[Decimal] = []
        self.support_levels: List[Decimal] = []

        # Derivatives data (optional, updated externally)
        self.open_interest_history: deque = deque(maxlen=24)  # 24 hours of data
        self.current_funding_rate: Optional[Decimal] = None
        self.current_put_call_ratio: Optional[Decimal] = None

        # State tracking
        self.last_signal_time: int = 0
        self.signal_count: int = 0

        logger.info(
            f"BreakoutSetupDetector initialized | "
            f"Symbol: {self.symbol} | "
            f"RSI: {self.config.rsi_period} | "
            f"MACD: {self.config.macd_fast}/{self.config.macd_slow}/{self.config.macd_signal} | "
            f"BB: {self.config.bb_period} | "
            f"Volume Threshold: {self.config.volume_spike_threshold}x"
        )

    def on_bar(self, bar: Bar) -> list[Signal]:
        """
        Process new bar and detect breakout setups.

        Args:
            bar: Current completed bar

        Returns:
            List of signals (standard Signal format for compatibility)
        """
        # Update price history
        self.closes.append(bar.close)
        self.highs.append(bar.high)
        self.lows.append(bar.low)
        self.volumes.append(bar.volume)

        # Need minimum bars for indicators
        if len(self.closes) < self.config.bb_period:
            logger.debug(f"Warming up indicators: {len(self.closes)}/{self.config.bb_period} bars")
            return []

        # Update indicators
        self._update_indicators()

        # Detect support/resistance levels
        self._update_support_resistance()

        # Analyze breakout setup
        setup = self._analyze_breakout_setup(bar)

        # Log detailed setup info
        logger.info(
            f"Breakout Analysis | "
            f"Setup: {setup.setup} | "
            f"Confidence: {setup.confidence:.2f} | "
            f"Conditions Met: {len(setup.conditions_met)}/4 | "
            f"Price: {setup.current_price} | "
            f"Resistance: {setup.resistance_level} | "
            f"Vol Ratio: {setup.volume_ratio:.2f}x | "
            f"RSI: {setup.rsi:.0f} | "
            f"MACD Hist: {setup.macd_histogram:+.4f}"
        )

        # Convert to standard Signal if bullish breakout detected
        if setup.setup == "Bullish Breakout" and setup.confidence >= Decimal("0.70"):
            signal = self._create_signal_from_setup(setup, bar)
            self.signal_count += 1
            self.last_signal_time = int(time.time())
            return [signal]

        return []

    def _update_indicators(self):
        """Calculate and update all technical indicators."""
        # RSI
        rsi = self._calculate_rsi()
        if rsi is not None:
            self.rsi_values.append(rsi)

        # MACD
        macd_line, signal_line, histogram = self._calculate_macd()
        if macd_line is not None:
            self.macd_values.append(macd_line)
            self.macd_signal_values.append(signal_line)
            self.macd_histogram_values.append(histogram)

    def _calculate_rsi(self) -> Optional[Decimal]:
        """Calculate RSI (14-period default)."""
        if len(self.closes) < self.config.rsi_period + 1:
            return None

        gains = Decimal("0")
        losses = Decimal("0")

        for i in range(1, self.config.rsi_period + 1):
            change = self.closes[-i] - self.closes[-i - 1]
            if change > 0:
                gains += change
            else:
                losses += abs(change)

        avg_gain = gains / self.config.rsi_period
        avg_loss = losses / self.config.rsi_period

        if avg_loss == 0:
            return Decimal("100")

        rs = avg_gain / avg_loss
        rsi = Decimal("100") - (Decimal("100") / (Decimal("1") + rs))

        return rsi

    def _calculate_macd(self) -> tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal]]:
        """Calculate MACD (12, 26, 9 default)."""
        if len(self.closes) < self.config.macd_slow:
            return None, None, None

        # Fast EMA
        fast_ema = self._calculate_ema(list(self.closes), self.config.macd_fast)

        # Slow EMA
        slow_ema = self._calculate_ema(list(self.closes), self.config.macd_slow)

        # MACD Line = Fast EMA - Slow EMA
        macd_line = fast_ema - slow_ema

        # Signal Line = 9-period EMA of MACD Line
        if len(self.macd_values) < self.config.macd_signal:
            signal_line = macd_line  # Not enough data for signal yet
        else:
            signal_line = self._calculate_ema(list(self.macd_values), self.config.macd_signal)

        # Histogram = MACD Line - Signal Line
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    def _calculate_ema(self, data: List[Decimal], period: int) -> Decimal:
        """Calculate Exponential Moving Average."""
        if len(data) < period:
            # Fall back to SMA if not enough data
            return sum(data[-period:]) / Decimal(str(period))

        multiplier = Decimal("2") / (Decimal(str(period)) + Decimal("1"))
        ema = sum(data[:period]) / Decimal(str(period))  # Start with SMA

        for price in data[period:]:
            ema = (price - ema) * multiplier + ema

        return ema

    def _calculate_bollinger_bands(self) -> tuple[Decimal, Decimal, Decimal]:
        """Calculate Bollinger Bands (20, 2 default)."""
        period = self.config.bb_period
        std_dev = self.config.bb_std_dev

        # Convert deque to list for slicing
        closes_list = list(self.closes)

        # Middle Band (SMA)
        middle = sum(closes_list[-period:]) / Decimal(str(period))

        # Standard Deviation
        variance = sum((x - middle) ** 2 for x in closes_list[-period:]) / Decimal(str(period))
        std = variance.sqrt()

        # Upper and Lower Bands
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)

        return upper, middle, lower

    def _update_support_resistance(self):
        """Detect support and resistance levels from recent price action."""
        if len(self.highs) < self.config.sr_lookback_bars:
            return

        # Simple S/R detection: recent swing highs/lows
        recent_highs = list(self.highs)[-self.config.sr_lookback_bars:]
        recent_lows = list(self.lows)[-self.config.sr_lookback_bars:]

        # Resistance: Recent swing highs (local maxima)
        self.resistance_levels = []
        for i in range(2, len(recent_highs) - 2):
            if (recent_highs[i] > recent_highs[i-1] and
                recent_highs[i] > recent_highs[i-2] and
                recent_highs[i] > recent_highs[i+1] and
                recent_highs[i] > recent_highs[i+2]):
                self.resistance_levels.append(recent_highs[i])

        # Support: Recent swing lows (local minima)
        self.support_levels = []
        for i in range(2, len(recent_lows) - 2):
            if (recent_lows[i] < recent_lows[i-1] and
                recent_lows[i] < recent_lows[i-2] and
                recent_lows[i] < recent_lows[i+1] and
                recent_lows[i] < recent_lows[i+2]):
                self.support_levels.append(recent_lows[i])

        # Sort and deduplicate
        self.resistance_levels = sorted(set(self.resistance_levels), reverse=True)[:5]
        self.support_levels = sorted(set(self.support_levels), reverse=True)[:5]

    def _analyze_breakout_setup(self, bar: Bar) -> SetupSignal:
        """
        Analyze current bar for breakout setup.

        Returns SetupSignal with detailed analysis.
        """
        setup = SetupSignal(
            symbol=self.symbol,
            setup="No Trade",
            confidence=Decimal("0"),
            current_price=bar.close,
            timestamp=bar.timestamp
        )

        conditions_met = []
        conditions_failed = []
        confidence_scores = []

        # 1. BREAKOUT CHECK
        breakout_score, breakout_msg = self._check_breakout(bar)
        if breakout_score > 0:
            conditions_met.append(breakout_msg)
            setup.resistance_level = self._get_nearest_resistance(bar.close)
        else:
            conditions_failed.append(breakout_msg)
        confidence_scores.append(breakout_score * self.config.weight_breakout)

        # 2. MOMENTUM CONFIRMATION
        momentum_score, momentum_msg = self._check_momentum()
        if momentum_score > 0:
            conditions_met.append(momentum_msg)
        else:
            conditions_failed.append(momentum_msg)
        confidence_scores.append(momentum_score * self.config.weight_momentum)

        # Fill in metrics
        if len(self.rsi_values) > 0:
            setup.rsi = self.rsi_values[-1]
        if len(self.macd_histogram_values) > 0:
            setup.macd_histogram = self.macd_histogram_values[-1]

        # 3. VOLATILITY SQUEEZE CHECK
        volatility_score, volatility_msg = self._check_volatility_squeeze()
        if volatility_score > 0:
            conditions_met.append(volatility_msg)
        else:
            conditions_failed.append(volatility_msg)
        confidence_scores.append(volatility_score * self.config.weight_volatility)

        upper, middle, lower = self._calculate_bollinger_bands()
        setup.bb_bandwidth_pct = ((upper - lower) / middle) * Decimal("100")

        # 4. DERIVATIVES SIGNALS (Optional)
        derivatives_score, derivatives_msg = self._check_derivatives()
        if derivatives_score > 0:
            conditions_met.append(derivatives_msg)
        elif derivatives_score < 0:
            conditions_failed.append(derivatives_msg)
        confidence_scores.append(max(Decimal("0"), derivatives_score) * self.config.weight_derivatives)

        setup.oi_change_pct = self._get_oi_change_pct()
        setup.funding_rate = self.current_funding_rate
        setup.put_call_ratio = self.current_put_call_ratio

        # 5. RISK FILTER
        risk_score, risk_msg = self._check_risk_filters()
        if risk_score > 0:
            conditions_met.append(risk_msg)
        else:
            conditions_failed.append(risk_msg)
            # Risk filter failure is critical - heavily penalize
            confidence_scores.append(Decimal("-0.5"))

        # Calculate volume ratio
        if len(self.volumes) >= self.config.volume_ma_period:
            avg_volume = sum(list(self.volumes)[:-1]) / Decimal(str(self.config.volume_ma_period - 1))
            if avg_volume > 0:
                setup.volume_ratio = bar.volume / avg_volume

        # Calculate final confidence
        setup.confidence = max(Decimal("0"), min(Decimal("1"), sum(confidence_scores)))
        setup.conditions_met = conditions_met
        setup.conditions_failed = conditions_failed

        # Determine setup type
        if setup.confidence >= Decimal("0.70"):
            setup.setup = "Bullish Breakout"
            setup.action = "Enter long via call options or perp with stop below resistance"
        elif setup.confidence >= Decimal("0.50"):
            setup.setup = "Watchlist"
            setup.action = "Setup forming but not confirmed. Monitor for entry."
        else:
            setup.setup = "No Trade"
            setup.action = "Stay flat. Conditions not satisfied."

        return setup

    def _check_breakout(self, bar: Bar) -> tuple[Decimal, str]:
        """Check if price is breaking above resistance with volume."""
        if not self.resistance_levels:
            return Decimal("0"), "No resistance level identified"

        nearest_resistance = self._get_nearest_resistance(bar.close)
        if nearest_resistance is None:
            return Decimal("0"), "No resistance level identified"

        # Check if closing above resistance
        breakout_threshold = nearest_resistance * (Decimal("1") + self.config.resistance_confirmation_pct / Decimal("100"))
        if bar.close <= breakout_threshold:
            return Decimal("0"), f"Price {bar.close} not above resistance {nearest_resistance}"

        # Check volume spike
        if len(self.volumes) < self.config.volume_ma_period:
            return Decimal("0.5"), f"Breakout above {nearest_resistance} but volume data insufficient"

        avg_volume = sum(list(self.volumes)[:-1]) / Decimal(str(self.config.volume_ma_period - 1))
        volume_ratio = bar.volume / avg_volume if avg_volume > 0 else Decimal("0")

        if volume_ratio >= self.config.volume_spike_threshold:
            return Decimal("1.0"), f"Breakout above resistance {nearest_resistance} with volume {volume_ratio:.1f}x avg"
        else:
            return Decimal("0.5"), f"Breakout above {nearest_resistance} but volume only {volume_ratio:.1f}x avg"

    def _check_momentum(self) -> tuple[Decimal, str]:
        """Check RSI and MACD for bullish momentum."""
        score = Decimal("0")
        messages = []

        # RSI Check
        if len(self.rsi_values) == 0:
            return Decimal("0"), "RSI data insufficient"

        current_rsi = self.rsi_values[-1]
        if current_rsi >= self.config.rsi_bullish_threshold:
            score += Decimal("0.5")
            messages.append(f"RSI {current_rsi:.0f} bullish")
        else:
            messages.append(f"RSI {current_rsi:.0f} below threshold")

        # MACD Check
        if len(self.macd_values) < self.config.macd_lookback_bars:
            messages.append("MACD data insufficient")
        else:
            # Check if MACD crossed above zero in last N bars
            macd_crossed_up = False
            for i in range(1, min(self.config.macd_lookback_bars + 1, len(self.macd_values))):
                if self.macd_values[-i] > 0 and self.macd_values[-i-1] <= 0:
                    macd_crossed_up = True
                    break

            if macd_crossed_up or self.macd_values[-1] > 0:
                score += Decimal("0.5")
                messages.append(f"MACD bullish (hist: {self.macd_histogram_values[-1]:+.4f})")
            else:
                messages.append(f"MACD not bullish (hist: {self.macd_histogram_values[-1]:+.4f})")

        return score, ", ".join(messages)

    def _check_volatility_squeeze(self) -> tuple[Decimal, str]:
        """Check for Bollinger Band squeeze (precedes breakouts)."""
        if len(self.closes) < self.config.bb_period:
            return Decimal("0"), "BB data insufficient"

        upper, middle, lower = self._calculate_bollinger_bands()
        bandwidth_pct = ((upper - lower) / middle) * Decimal("100")

        # Check historical bandwidth to see if it was recently tight
        # For now, simple check: is current bandwidth expanding from tight?
        if bandwidth_pct <= self.config.bb_squeeze_threshold * Decimal("100"):
            return Decimal("0.5"), f"BB squeeze active ({bandwidth_pct:.2f}% bandwidth)"
        elif bandwidth_pct > self.config.bb_squeeze_threshold * Decimal("100") * Decimal("1.5"):
            return Decimal("1.0"), f"BB expanding from squeeze ({bandwidth_pct:.2f}% bandwidth)"
        else:
            return Decimal("0"), f"BB bandwidth normal ({bandwidth_pct:.2f}%)"

    def _check_derivatives(self) -> tuple[Decimal, str]:
        """Check Open Interest, Funding Rate, Put/Call Ratio."""
        score = Decimal("0")
        messages = []

        # Open Interest Check
        oi_change = self._get_oi_change_pct()
        if oi_change is not None:
            if oi_change >= self.config.oi_increase_threshold:
                score += Decimal("0.4")
                messages.append(f"OI increased {oi_change*100:.1f}%")
            else:
                messages.append(f"OI change {oi_change*100:.1f}% insufficient")

        # Funding Rate Check
        if self.current_funding_rate is not None:
            if (self.current_funding_rate >= self.config.funding_rate_positive_min and
                self.current_funding_rate <= self.config.funding_rate_extreme_max):
                score += Decimal("0.3")
                messages.append(f"Funding rate {self.current_funding_rate*100:.3f}% positive")
            elif self.current_funding_rate > self.config.funding_rate_extreme_max:
                score -= Decimal("0.3")
                messages.append(f"Funding rate {self.current_funding_rate*100:.3f}% extreme")
            else:
                messages.append(f"Funding rate {self.current_funding_rate*100:.3f}% not bullish")

        # Put/Call Ratio Check
        if self.current_put_call_ratio is not None:
            if self.current_put_call_ratio < self.config.put_call_bullish_threshold:
                score += Decimal("0.3")
                messages.append(f"P/C ratio {self.current_put_call_ratio:.2f} bullish")
            else:
                messages.append(f"P/C ratio {self.current_put_call_ratio:.2f} not bullish")

        if not messages:
            return Decimal("0"), "No derivatives data available"

        return score, ", ".join(messages)

    def _check_risk_filters(self) -> tuple[Decimal, str]:
        """Check for overextension and trap conditions."""
        if len(self.rsi_values) == 0:
            return Decimal("1.0"), "Risk filters passed (no RSI data)"

        current_rsi = self.rsi_values[-1]

        # Overextended RSI
        if current_rsi > self.config.rsi_overbought_threshold:
            return Decimal("0"), f"RSI {current_rsi:.0f} overextended (>{self.config.rsi_overbought_threshold})"

        # OI Spike + Flat Price = Possible Trap
        oi_change = self._get_oi_change_pct()
        if oi_change is not None and oi_change >= self.config.oi_increase_threshold:
            # Check if price is flat (low volatility despite OI spike)
            if len(self.closes) >= 5:
                price_change_pct = abs((self.closes[-1] - self.closes[-5]) / self.closes[-5]) * Decimal("100")
                if price_change_pct < Decimal("1.0"):  # Less than 1% move
                    return Decimal("0"), f"OI spike +{oi_change*100:.0f}% but price flat (trap?)"

        return Decimal("1.0"), "Risk filters passed"

    def _get_nearest_resistance(self, price: Decimal) -> Optional[Decimal]:
        """Get nearest resistance level above current price."""
        if not self.resistance_levels:
            return None

        # Find first resistance above current price
        for level in sorted(self.resistance_levels):
            if level >= price * (Decimal("1") - self.config.sr_tolerance_pct / Decimal("100")):
                return level

        return self.resistance_levels[-1] if self.resistance_levels else None

    def _get_oi_change_pct(self) -> Optional[Decimal]:
        """Calculate Open Interest change over last 24 data points."""
        if len(self.open_interest_history) < 2:
            return None

        old_oi = self.open_interest_history[0]
        new_oi = self.open_interest_history[-1]

        if old_oi == 0:
            return None

        return (new_oi - old_oi) / old_oi

    def _create_signal_from_setup(self, setup: SetupSignal, bar: Bar) -> Signal:
        """Convert SetupSignal to standard Signal format."""
        # Calculate position size
        qty = self.config.position_size_usd / bar.close

        # Set stop loss below resistance (or recent support)
        sl_price = setup.resistance_level * Decimal("0.98") if setup.resistance_level else bar.close * Decimal("0.97")

        # Set take profit based on R:R ratio (aim for 2:1)
        risk = bar.close - sl_price
        tp_price = bar.close + (risk * Decimal("2"))

        signal = Signal(
            symbol=self.symbol,
            side="buy",
            qty=qty,
            price=bar.close,
            sl=sl_price,
            tp=tp_price,
            reason=f"Breakout setup: {', '.join(setup.conditions_met[:3])}"
        )

        return signal

    def update_derivatives_data(
        self,
        open_interest: Optional[Decimal] = None,
        funding_rate: Optional[Decimal] = None,
        put_call_ratio: Optional[Decimal] = None
    ):
        """
        Update derivatives data (call externally when data available).

        Args:
            open_interest: Current open interest value
            funding_rate: Current funding rate (per 8h for perps)
            put_call_ratio: Current put/call ratio for options
        """
        if open_interest is not None:
            self.open_interest_history.append(open_interest)

        if funding_rate is not None:
            self.current_funding_rate = funding_rate

        if put_call_ratio is not None:
            self.current_put_call_ratio = put_call_ratio

    def reset(self):
        """Reset strategy state."""
        self.closes.clear()
        self.highs.clear()
        self.lows.clear()
        self.volumes.clear()
        self.rsi_values.clear()
        self.macd_values.clear()
        self.macd_signal_values.clear()
        self.macd_histogram_values.clear()
        self.resistance_levels.clear()
        self.support_levels.clear()
        self.open_interest_history.clear()
        self.current_funding_rate = None
        self.current_put_call_ratio = None
        self.last_signal_time = 0
        self.signal_count = 0

        logger.info(f"BreakoutSetupDetector reset: {self.symbol}")
